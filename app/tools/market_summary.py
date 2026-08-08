"""Market summary helper tools."""

from langchain_core.tools import tool
from app.integrations.yfinance_client import yfinance_client


@tool
async def market_summary_tool() -> str:
    """Fetch a light-weight market summary."""
    sp500 = yfinance_client.get_ticker_info("^GSPC")
    nasdaq = yfinance_client.get_ticker_info("^IXIC")
    dow = yfinance_client.get_ticker_info("^DJI")
    return (
        f"Market Overview\n"
        f"• S&P 500: {sp500.get('current_price', 0)}\n"
        f"• Nasdaq: {nasdaq.get('current_price', 0)}\n"
        f"• Dow Jones: {dow.get('current_price', 0)}"
    )
