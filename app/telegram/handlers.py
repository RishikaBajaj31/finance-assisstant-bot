"""Telegram update handlers."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from telegram import Update

from app.agents.graph import run_agent
from app.agents.state import AgentState
from app.core.logging import logger
from app.core.exceptions import DocumentParseException
from app.database.repositories.telegram_update_repo import TelegramUpdateRepository
from app.services.document_service import DocumentService
from app.services.memory_service import MemoryService
from app.services.user_service import UserService
from app.telegram.bot import telegram_bot


MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024
SUPPORTED_MIME_TYPES = {"application/pdf"}


def _is_supported_document(document) -> bool:
    filename = (getattr(document, "file_name", "") or "").lower()
    mime_type = (getattr(document, "mime_type", "") or "").lower()
    return mime_type in SUPPORTED_MIME_TYPES or filename.endswith(".pdf")


async def _process_document_upload(message, chat, user, session) -> Dict[str, Any]:
    document = message.document
    filename = document.file_name or "uploaded_report.pdf"
    telegram_file_id = document.file_id
    content_type = document.mime_type or "application/pdf"
    size_bytes = int(document.file_size or 0)

    if not _is_supported_document(document):
        response_text = "I can only process PDF financial reports right now. Please send a PDF."
        await telegram_bot.send_message(chat.id, response_text)
        return {"ok": True, "response": response_text, "telegram_sent": True, "document_processed": False}

    if size_bytes and size_bytes > MAX_DOCUMENT_SIZE_BYTES:
        response_text = "That PDF is too large for now. Please send a file under 20 MB."
        await telegram_bot.send_message(chat.id, response_text)
        return {"ok": True, "response": response_text, "telegram_sent": True, "document_processed": False}

    ack_text = "Got it - I'm processing the report now. I'll let you know when it's ready."
    await telegram_bot.send_message(chat.id, ack_text)

    document_service = DocumentService(session)
    memory_service = MemoryService(session)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix or ".pdf") as tmp:
            temp_path = tmp.name
        await telegram_bot.download_file(telegram_file_id, temp_path)

        processed = await document_service.process_uploaded_document(
            user_id=user.id,
            file_path=temp_path,
            filename=filename,
            telegram_file_id=telegram_file_id,
            content_type=content_type,
            size_bytes=size_bytes or None,
        )

        response_text = f"Done. I've processed {processed.filename}. You can ask me anything about it."
        await memory_service.record_user_message(user.id, f"Uploaded document: {processed.filename}")
        await memory_service.record_assistant_message(user.id, response_text)
        await telegram_bot.send_message(chat.id, response_text)
        logger.info("Processed Telegram document upload for %s", user.telegram_id)
        return {
            "ok": True,
            "response": response_text,
            "telegram_sent": True,
            "document_processed": True,
            "document_id": str(processed.id),
        }
    except DocumentParseException as exc:
        exception_text = str(exc).strip()
        if "scanned" in exception_text.lower() or "image-based" in exception_text.lower():
            response_text = exception_text
        else:
            response_text = "Sorry, I couldn't process that document. Please try another PDF."
        await telegram_bot.send_message(chat.id, response_text)
        return {
            "ok": True,
            "response": response_text,
            "telegram_sent": True,
            "document_processed": False,
            "error": "document_parse_error",
        }
    except Exception as exc:
        logger.warning("Document upload processing failed for %s: %s", filename, exc)
        response_text = "Sorry, I couldn't process that document. Please try another PDF."
        await telegram_bot.send_message(chat.id, response_text)
        return {
            "ok": True,
            "response": response_text,
            "telegram_sent": True,
            "document_processed": False,
            "error": "document_processing_failed",
        }
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass


async def process_update(payload: Optional[Dict[str, Any]], session) -> Dict[str, Any]:
    if not payload:
        return {"ok": True, "skipped": True, "reason": "empty webhook payload"}

    try:
        update = Update.de_json(payload, None)
    except Exception as exc:
        logger.warning("Invalid Telegram webhook payload: %s", exc)
        return {"ok": True, "skipped": True, "reason": "invalid telegram payload"}

    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return {"ok": True, "skipped": True}

    telegram_id = message.from_user.id if message.from_user else chat.id
    username = message.from_user.username if message.from_user else None
    full_name = message.from_user.full_name if message.from_user else None
    update_id = getattr(update, "update_id", None)

    if update_id is not None:
        update_repo = TelegramUpdateRepository(session)
        if not await update_repo.claim_update(update_id):
            logger.info("Skipping duplicate Telegram update %s for %s", update_id, telegram_id)
            return {"ok": True, "skipped": True, "reason": "duplicate telegram update", "telegram_sent": False}

    user_service = UserService(session)
    user = await user_service.get_or_create_user(telegram_id, username=username, full_name=full_name)

    if getattr(message, "document", None):
        return await _process_document_upload(message, chat, user, session)

    if not message.text:
        return {"ok": True, "skipped": True}

    memory_service = MemoryService(session)
    state: AgentState = {
        "telegram_id": telegram_id,
        "user_id": str(user.id),
        "user_name": full_name or username,
        "input_text": message.text,
        "intent": "general",
        "is_onboarded": bool(user.onboarding_complete),
        "conversation_history": "",
        "recalled_memories": [],
        "document_id": None,
        "response": "",
        "metadata": {"chat_id": chat.id, "user": user},
        "db_session": session,
    }

    result = await run_agent(state)
    response_text = result.get("response", "I am here if you want company research, market news, or a briefing.")

    await memory_service.record_user_message(user.id, message.text)
    await memory_service.maybe_store_memory(
        user.id,
        user_message=message.text,
        assistant_message=response_text,
        conversation_history=result.get("conversation_history", ""),
        recalled_memories=result.get("recalled_memories", []),
    )
    await memory_service.record_assistant_message(user.id, response_text)
    telegram_sent = await telegram_bot.send_message(chat.id, response_text)

    logger.info("Processed Telegram update for %s", telegram_id)
    return {"ok": True, "response": response_text, "telegram_sent": telegram_sent}
