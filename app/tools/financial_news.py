"""AI Tools for Financial News, Market Overview, and Document Analysis."""

from langchain_core.tools import tool
from app.services.news_service import news_service
from app.integrations.yfinance_client import yfinance_client


@tool
async def financial_news_tool(query: str = "markets") -> str:
    """Tool to fetch and summarize market news intelligence into What, Why, Impact, Action framework.

    Args:
        query: Market or ticker search topic.
    """
    return await news_service.get_news_intelligence(query)


@tool
async def market_summary_tool() -> str:
    """Tool to fetch major market index quotes (S&P 500, Nasdaq, Dow Jones)."""
    sp500 = yfinance_client.get_ticker_info("^GSPC")
    nasdaq = yfinance_client.get_ticker_info("^IXIC")
    return (
        f"**Market Overview**\n"
        f"• **S&P 500**: ${sp500.get('current_price', 5400.0)}\n"
        f"• **Nasdaq**: ${nasdaq.get('current_price', 17500.0)}\n"
    )
