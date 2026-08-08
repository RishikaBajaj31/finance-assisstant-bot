"""State definition for LangGraph Financial Assistant agent workflow."""

from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """LangGraph execution state passed between graph nodes."""

    telegram_id: int
    user_id: Optional[str]
    user_name: Optional[str]
    input_text: str
    intent: str
    is_onboarded: bool
    conversation_history: str
    recalled_memories: List[str]
    document_id: Optional[str]
    response: str
    metadata: Dict[str, Any]
    db_session: Any
