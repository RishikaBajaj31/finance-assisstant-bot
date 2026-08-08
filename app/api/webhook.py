"""Telegram webhook endpoint."""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Body, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_session
from app.telegram.handlers import process_update

router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    payload: Optional[Dict[str, Any]] = Body(default=None),
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    session: AsyncSession = Depends(get_session),
):
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET_TOKEN.strip()
    if expected_secret:
        if x_telegram_bot_api_secret_token != expected_secret:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Telegram webhook secret token",
            )
    return await process_update(payload, session)
