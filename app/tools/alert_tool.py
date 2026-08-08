"""Alert helper tools."""

from langchain_core.tools import tool


@tool
async def alert_summary_tool(ticker: str, condition: str, threshold: float) -> str:
    """Summarize an alert rule for the assistant."""
    return f"Alert configured for {ticker.upper()} when {condition} {threshold}."
