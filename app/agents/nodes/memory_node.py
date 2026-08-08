"""Memory node for loading short-term history and semantic context."""

from uuid import UUID

from app.agents.state import AgentState
from app.services.memory_service import MemoryService


async def memory_node(state: AgentState) -> AgentState:
    session = state.get("db_session")
    user_id = state.get("user_id")

    if not session or not user_id:
        state.setdefault("conversation_history", "")
        state.setdefault("recalled_memories", [])
        return state

    service = MemoryService(session)
    parsed_user_id = UUID(str(user_id))
    state["conversation_history"] = await service.get_conversation_history(parsed_user_id)
    state["recalled_memories"] = await service.recall_relevant_memories(
        parsed_user_id,
        state.get("input_text", ""),
    )
    return state
