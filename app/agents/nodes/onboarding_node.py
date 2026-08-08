"""Onboarding Node for conversational user profile discovery."""

from app.agents.state import AgentState
from app.services.onboarding_service import OnboardingService


async def onboarding_node(state: AgentState) -> AgentState:
    """Handle natural conversational onboarding steps and persistence."""
    session = state.get("db_session")
    user = state.get("metadata", {}).get("user")
    if not session or not user:
        state["response"] = "What best describes your role or background?"
        return state

    service = OnboardingService(session)
    state["response"] = await service.handle(user, state.get("input_text", ""))
    return state
