"""Helpers to build user context snippets."""

from typing import Any


def build_user_context(user: Any) -> str:
    if not user:
        return ""
    preference = getattr(user, "preferences", None)
    return (
        f"Role: {getattr(user, 'role', None) or 'Unknown'}\n"
        f"Briefing Time: {getattr(user, 'briefing_time', '08:00')}\n"
        f"Sectors: {getattr(preference, 'sectors', []) if preference else []}\n"
        f"Interests: {getattr(preference, 'interests', []) if preference else []}"
    )
