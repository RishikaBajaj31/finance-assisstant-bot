"""Watchlist helper tools."""

from langchain_core.tools import tool


@tool
async def watchlist_summary_tool(tickers: list[str]) -> str:
    """Summarize a watchlist for the assistant."""
    normalized = [ticker.upper() for ticker in tickers]
    return f"Watchlist tracked: {', '.join(normalized)}"
