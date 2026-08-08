"""Alert node for conversational alert creation and management."""

from app.agents.state import AgentState
from app.services.alert_service import AlertService


async def alert_node(state: AgentState) -> AgentState:
    session = state.get("db_session")
    user = state.get("metadata", {}).get("user")
    if not session or not user:
        state["response"] = "Which company should I alert you about?"
        return state

    service = AlertService(session)
    state["response"] = await service.handle(user, state.get("input_text", ""))
    return state

