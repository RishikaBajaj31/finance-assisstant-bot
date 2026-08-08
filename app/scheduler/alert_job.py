"""Price alert polling job."""

from app.core.logging import logger
from app.services.alert_service import AlertService
from app.database.connection import AsyncSessionLocal
from app.telegram.bot import telegram_bot


async def run_alert_checks() -> list[dict]:
    async with AsyncSessionLocal() as session:
        service = AlertService(session)
        triggered = await service.evaluate_active_alerts()
        sent = 0
        for item in triggered:
            chat_id = item.get("chat_id")
            message = item.get("message")
            if not chat_id or not message:
                continue
            try:
                sent_ok = await telegram_bot.send_message(chat_id, message)
                if sent_ok:
                    sent += 1
                else:
                    logger.warning("Telegram delivery returned false for alert %s", item.get("alert_id"))
            except Exception as exc:
                logger.warning("Failed to send alert notification for %s: %s", item.get("alert_id"), exc)
        logger.info("Alert job checked %s triggered alerts and sent %s notifications", len(triggered), sent)
        return triggered
