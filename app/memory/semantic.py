"""Helpers for semantic memory summaries."""

from typing import Iterable


def join_memories(memories: Iterable[str]) -> str:
    items = [m for m in memories if m]
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)
