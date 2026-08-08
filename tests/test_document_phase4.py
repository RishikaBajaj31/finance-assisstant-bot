import asyncio
import tempfile
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.nodes.router_node import router_node
from app.agents.state import AgentState
from app.core.exceptions import DocumentParseException
from app.database.connection import AsyncSessionLocal, Base, engine
from app.database.migrations.ensure_schema import ensure_schema
from app.database.repositories.document_repo import DocumentRepository
from app.database.repositories.user_repo import UserRepository
from app.integrations.gemini import gemini_client
from app.models.document import Document
from app.services.document_service import DocumentService
from app.services.user_service import UserService
from app.telegram.handlers import process_update
from app.telegram import handlers as telegram_handlers
from app.telegram.bot import telegram_bot


TABLES = [
    "document_chunks",
    "documents",
    "research_history",
    "alerts",
    "watchlists",
    "memories",
    "conversations",
    "user_preferences",
    "users",
]


def run(coro):
    async def wrapper():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(wrapper())


async def reset_db():
    await ensure_schema(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE")


async def create_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        return await UserService(session).get_or_create_user(telegram_id, username="tester", full_name="Test User")


class FakePage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class FakePdf:
    def __init__(self, pages):
        self.pages = [FakePage(page) for page in pages]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_text_update(text: str, telegram_id: int = 2001, chat_id: int = 2001):
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "date": 1754670000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": telegram_id, "is_bot": False, "first_name": "Test", "username": "tester"},
            "text": text,
        },
    }


def make_document_update(
    file_name: str = "Apple_10K.pdf",
    mime_type: str = "application/pdf",
    file_size: int = 1024,
    telegram_id: int = 2002,
    chat_id: int = 2002,
):
    return {
        "update_id": 2,
        "message": {
            "message_id": 11,
            "date": 1754670000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": telegram_id, "is_bot": False, "first_name": "Test", "username": "tester"},
            "document": {
                "file_id": "telegram-file-id-1",
                "file_unique_id": "telegram-file-unique-id-1",
                "file_name": file_name,
                "mime_type": mime_type,
                "file_size": file_size,
            },
        },
    }


def test_document_upload_creates_metadata_and_chunks(monkeypatch):
    async def scenario():
        await reset_db()
        pages = [
            "Apple reported strong revenue growth and margin expansion.",
            "Key risks include supply constraints, regulation, and macro pressure.",
        ]
        monkeypatch.setattr("app.services.document_service.pdfplumber.open", lambda _: FakePdf(pages))
        monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.1] * 768))

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2001, username="tester", full_name="Test User")
            service = DocumentService(session)
            doc = await service.process_uploaded_document(
                user_id=user.id,
                file_path="fake.pdf",
                filename="Apple_10K.pdf",
                telegram_file_id="telegram-file-id-1",
                content_type="application/pdf",
                size_bytes=1024,
            )
            repo = DocumentRepository(session)
            chunks = await repo.get_document_chunks(doc.id)

            assert doc.user_id == user.id
            assert doc.filename == "Apple_10K.pdf"
            assert doc.telegram_file_id == "telegram-file-id-1"
            assert doc.content_type == "application/pdf"
            assert doc.status == "ready"
            assert doc.page_count == 2
            assert doc.processed_at is not None
            assert len(chunks) >= 2
            assert {chunk.page_number for chunk in chunks} == {1, 2}

    run(scenario())


def test_document_upload_marks_failed_for_scanned_pdf(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr("app.services.document_service.pdfplumber.open", lambda _: FakePdf(["", ""]))

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2002, username="tester", full_name="Test User")
            service = DocumentService(session)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                file_path = tmp.name
            try:
                try:
                    await service.process_uploaded_document(user.id, file_path, "Scanned.pdf")
                except DocumentParseException as exc:
                    assert "scanned" in str(exc).lower()

                repo = DocumentRepository(session)
                docs = await repo.get_user_documents(user.id)
                assert docs[0].status == "failed"
                assert docs[0].extraction_error
            finally:
                Path(file_path).unlink(missing_ok=True)

    from pathlib import Path

    run(scenario())


def test_invalid_pdf_marks_failed(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr("app.services.document_service.pdfplumber.open", lambda _: (_ for _ in ()).throw(Exception("bad pdf")))

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2003, username="tester", full_name="Test User")
            service = DocumentService(session)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                file_path = tmp.name
            try:
                try:
                    await service.process_uploaded_document(user.id, file_path, "Broken.pdf")
                except DocumentParseException:
                    pass
                docs = await DocumentRepository(session).get_user_documents(user.id)
                assert docs[0].status == "failed"
            finally:
                Path(file_path).unlink(missing_ok=True)

    from pathlib import Path

    run(scenario())


def test_document_query_uses_context_and_citations(monkeypatch):
    async def scenario():
        await reset_db()
        pages = [
            "Revenue grew 18 percent year over year.",
            "Risks include supply chain pressure and valuation concerns.",
        ]
        monkeypatch.setattr("app.services.document_service.pdfplumber.open", lambda _: FakePdf(pages))
        monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.2] * 768))
        captured = {}

        async def fake_response(prompt, system_instruction=None):
            captured["prompt"] = prompt
            captured["system_instruction"] = system_instruction
            return "Revenue growth looks strong."

        monkeypatch.setattr(gemini_client, "generate_response", fake_response)

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2004, username="tester", full_name="Test User")
            service = DocumentService(session)
            await service.process_uploaded_document(user.id, "fake.pdf", "Apple_10K.pdf")
            answer = await service.query_document(user.id, "What are the biggest risks?")

            assert "Revenue" in captured["prompt"] or "Risks" in captured["prompt"]
            assert "Source:" in answer
            assert "pages 1, 2" in answer.lower()

    run(scenario())


def test_missing_document_information_returns_exact_message(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.3] * 768))

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2005, username="tester", full_name="Test User")
            answer = await DocumentService(session).query_document(user.id, "What are the risks?")
            assert answer == "I don't see an uploaded report yet."

    run(scenario())


def test_multiple_document_comparison(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr("app.services.document_service.pdfplumber.open", lambda _: FakePdf(["One report page."]))
        monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.4] * 768))
        captured = {}

        async def fake_response(prompt, system_instruction=None):
            captured["prompt"] = prompt
            return "The newer report is stronger on growth."

        monkeypatch.setattr(gemini_client, "generate_response", fake_response)

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2006, username="tester", full_name="Test User")
            service = DocumentService(session)
            first = await service.process_uploaded_document(user.id, "fake1.pdf", "Apple_Q1.pdf")
            second = await service.process_uploaded_document(user.id, "fake2.pdf", "Apple_Q2.pdf")
            answer = await service.query_document(user.id, "Compare these two reports.")

            assert "Apple_Q1.pdf" in captured["prompt"]
            assert "Apple_Q2.pdf" in captured["prompt"]
            assert first.id != second.id
            assert "Source:" in answer

    run(scenario())


def test_user_isolation(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.5] * 768))

        async with AsyncSessionLocal() as session:
            user_a = await UserService(session).get_or_create_user(2007, username="tester", full_name="User A")
            user_b = await UserService(session).get_or_create_user(2008, username="tester2", full_name="User B")
            doc_repo = DocumentRepository(session)
            doc = await doc_repo.create_document(user_a.id, "Apple_10K.pdf", "pdf", status="ready")
            await doc_repo.add_chunks(
                doc.id,
                [{"chunk_index": 0, "page_number": 1, "content": "Apple revenue grew strongly.", "embedding": [0.5] * 768}],
            )
            answer = await DocumentService(session).query_document(user_b.id, "Summarize this report.")
            assert answer == "I don't see an uploaded report yet."

    run(scenario())


def test_telegram_document_handler_processes_upload(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(telegram_bot, "download_file", AsyncMock(return_value="/tmp/fake.pdf"))
        monkeypatch.setattr(
            "app.services.document_service.DocumentService.process_uploaded_document",
            AsyncMock(return_value=SimpleNamespace(id=uuid4(), filename="Apple_10K.pdf")),
        )

        payload = make_document_update()
        async with AsyncSessionLocal() as session:
            result = await process_update(payload, session)
            assert result["document_processed"] is True
            assert "processed Apple_10K.pdf" in result["response"]
            assert any("processing the report" in message for message in sent_messages)

    run(scenario())


def test_oversized_file_is_rejected(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        payload = make_document_update(file_size=50 * 1024 * 1024)
        async with AsyncSessionLocal() as session:
            result = await process_update(payload, session)
            assert "too large" in result["response"].lower()
            assert any("too large" in message.lower() for message in sent_messages)

    run(scenario())


def test_unsupported_file_is_rejected(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        payload = make_document_update(file_name="notes.txt", mime_type="text/plain")
        async with AsyncSessionLocal() as session:
            result = await process_update(payload, session)
            assert "only process pdf" in result["response"].lower()
            assert any("pdf" in message.lower() for message in sent_messages)

    run(scenario())


def test_processing_failure_is_graceful(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(telegram_bot, "download_file", AsyncMock(return_value="/tmp/fake.pdf"))
        monkeypatch.setattr(
            "app.services.document_service.DocumentService.process_uploaded_document",
            AsyncMock(side_effect=DocumentParseException("Could not process the PDF.")),
        )

        payload = make_document_update()
        async with AsyncSessionLocal() as session:
            result = await process_update(payload, session)
            assert "couldn't process" in result["response"].lower()
            assert any("couldn't process" in message.lower() for message in sent_messages)

    run(scenario())


def test_document_follow_up_uses_active_context(monkeypatch):
    async def scenario():
        await reset_db()
        monkeypatch.setattr(gemini_client, "generate_response", AsyncMock(return_value="general"))
        monkeypatch.setattr(telegram_bot, "send_message", AsyncMock(return_value=True))
        monkeypatch.setattr(
            "app.services.document_service.DocumentService.query_document",
            AsyncMock(return_value="The biggest risks are margin pressure and regulation."),
        )

        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(2009, username="tester", full_name="Test User")
            await UserRepository(session).update_user_profile(user.id, onboarding_complete=True)
            repo = DocumentRepository(session)
            doc = await repo.create_document(user.id, "NVIDIA_Annual_Report.pdf", "pdf", status="ready")
            await repo.add_chunks(
                doc.id,
                [{"chunk_index": 0, "page_number": 3, "content": "Management discussed AI demand.", "embedding": [0.6] * 768}],
            )

            payload = make_text_update("What are the biggest risks?", telegram_id=2009, chat_id=2009)
            result = await process_update(payload, session)
            assert "margin pressure" in result["response"].lower()

    run(scenario())
