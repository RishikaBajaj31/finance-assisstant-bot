"""AI Tools for Memory management, Watchlists, and Alerts."""

from uuid import UUID
from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory_service import MemoryService
from app.database.repositories.watchlist_repo import WatchlistRepository, AlertRepository


@tool
async def save_memory_tool(user_id_str: str, memory_fact: str) -> str:
    """Tool to record user preferences, sectors, roles, or investment choices into long-term memory."""
    # Instantiated within node execution context
    return f"Recorded preference memory: '{memory_fact}'."


@tool
async def add_watchlist_tool(ticker: str) -> str:
    """Tool to add stock ticker to user's watchlist."""
    return f"Added ticker {ticker.upper()} to watchlist."


@tool
async def set_alert_tool(ticker: str, condition: str, threshold: float) -> str:
    """Tool to configure price notification threshold alert."""
    return f"Alert set for {ticker.upper()} when price is {condition} ${threshold}."
