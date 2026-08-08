"""Telegram formatting helpers."""

from app.utils.formatting import safe_markdown


def format_message(text: str) -> str:
    return safe_markdown(text).strip()
