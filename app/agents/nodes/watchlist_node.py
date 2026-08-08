"""Watchlist node for conversational add/remove/list requests."""

from app.agents.state import AgentState
from app.services.watchlist_service import WatchlistService


async def watchlist_node(state: AgentState) -> AgentState:
    session = state.get("db_session")
    user = state.get("metadata", {}).get("user")
    if not session or not user:
        state["response"] = "Which company would you like me to watch?"
        return state

    service = WatchlistService(session)
    response, _ = await service.handle(user.id, state.get("input_text", ""))
    state["response"] = response
    return state
