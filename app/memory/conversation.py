"""Helpers for short-term conversation memory."""

from typing import Iterable


def format_history(turns: Iterable[tuple[str, str]]) -> str:
    return "\n".join(f"{role.capitalize()}: {content}" for role, content in turns)
