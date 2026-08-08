"""Minimal Telegram bot wrapper."""

from pathlib import Path
from typing import Optional

from telegram import Bot
from telegram.error import BadRequest

from app.config import settings
from app.core.logging import logger
from app.telegram.formatter import format_message


class TelegramBot:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self._bot = Bot(token=self.token) if self.token and self.token != "mock-token" else None

    async def send_message(self, chat_id: int, text: str) -> bool:
        if not self._bot:
            logger.info("Telegram bot not configured; skipping outbound message.")
            return False
        try:
            await self._bot.send_message(chat_id=chat_id, text=format_message(text))
            return True
        except BadRequest as exc:
            logger.warning("Telegram send_message failed for chat_id=%s: %s", chat_id, exc)
            return False
        except Exception as exc:
            logger.warning("Unexpected Telegram send_message failure for chat_id=%s: %s", chat_id, exc)
            return False

    async def download_file(self, file_id: str, destination_path: str) -> str:
        if not self._bot:
            raise RuntimeError("Telegram bot is not configured.")
        file = await self._bot.get_file(file_id)
        target = Path(destination_path)
        await file.download_to_drive(custom_path=str(target))
        return str(target)


telegram_bot = TelegramBot()
