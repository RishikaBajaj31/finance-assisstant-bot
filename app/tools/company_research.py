"""AI Tool for Company Fundamental Research and Peer Comparison."""

from typing import List, Optional
from langchain_core.tools import tool
from app.services.research_service import research_service


@tool
async def company_research_tool(query: str, tickers: Optional[List[str]] = None) -> str:
    """Tool to research company fundamental data, financials, growth drivers, and compare peers.

    Args:
        query: User research prompt or question.
        tickers: Optional list of stock ticker symbols (e.g. ['NVDA', 'AMD']).
    """
    return await research_service.analyze_company_or_comparison(query, tickers or [])
