"""Final response node for general fallback replies."""

from app.agents.state import AgentState
from app.integrations.gemini import gemini_client
from app.prompts.system import SYSTEM_ANALYST_PERSONA
from app.prompts.memory import MEMORY_CONTEXT_SYSTEM_PROMPT
from app.utils.formatting import bullet_list


async def response_node(state: AgentState) -> AgentState:
    if state.get("response"):
        return state

    memories = state.get("recalled_memories", []) or []
    memory_context = bullet_list(memories[:4])
    prompt = (
        f"Conversation History:\n{state.get('conversation_history', '')}\n\n"
        f"Relevant Memories:\n{memory_context}\n\n"
        f"User Message: {state.get('input_text', '')}\n\n"
        "Reply as a concise senior financial analyst. Keep it useful and conversational."
    )
    state["response"] = await gemini_client.generate_response(
        prompt,
        system_instruction=f"{SYSTEM_ANALYST_PERSONA}\n\n{MEMORY_CONTEXT_SYSTEM_PROMPT}",
    )
    return state
