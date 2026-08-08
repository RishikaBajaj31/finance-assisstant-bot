"""News node for financial market intelligence."""

from app.agents.state import AgentState
from app.services.news_service import news_service


async def news_node(state: AgentState) -> AgentState:
    query = state.get("input_text", "") or "markets"
    state["response"] = await news_service.get_news_intelligence(query=query)
    return state
