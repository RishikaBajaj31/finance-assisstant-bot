"""Response formatting helpers."""

from typing import Iterable


def bullet_list(items: Iterable[str]) -> str:
    return "\n".join(f"• {item}" for item in items if item)


def safe_markdown(text: str) -> str:
    return text.replace("â€¢", "•").replace("ðŸ“Š", "📊").replace("ðŸŽ¯", "🎯").replace("ðŸ’¡", "💡").replace("âš¡", "⚡")
