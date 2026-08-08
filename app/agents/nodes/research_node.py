"""Research Node for stock analysis and peer comparisons."""

import re
from app.agents.state import AgentState
from app.services.research_service import research_service


async def research_node(state: AgentState) -> AgentState:
    """Extract ticker symbols and perform fundamental research."""
    text = state.get("input_text", "")

    # Extract uppercase stock tickers (e.g. NVDA, AMD, AAPL)
    found_tickers = re.findall(r"\b[A-Z]{2,5}\b", text)
    known_tickers = ["NVDA", "AMD", "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN"]
    filtered_tickers = [t for t in found_tickers if t in known_tickers] or ["NVDA", "AMD"]

    report = await research_service.analyze_company_or_comparison(text, filtered_tickers)
    state["response"] = report
    return state
