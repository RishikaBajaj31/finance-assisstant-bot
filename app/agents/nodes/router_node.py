"""Router Node for classifying user intent in LangGraph."""

from app.agents.state import AgentState
from app.services.document_service import DocumentService
from app.integrations.gemini import gemini_client
from app.prompts.router import ROUTER_SYSTEM_PROMPT
from app.core.logging import logger


def _looks_like_document_followup(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    hints = (
        "summarize",
        "summary",
        "risk",
        "risks",
        "revenue",
        "guidance",
        "management",
        "compare",
        "difference",
        "changed",
        "what about",
        "what did",
        "what are the",
        "what is management saying",
        "largest points",
        "key points",
        "important points",
        "this report",
        "that report",
        "this one",
        "that one",
        "how did",
        "what changed",
        "what happened",
        "explain this",
        "biggest risks",
        "most important",
        "financial numbers",
    )
    return any(hint in lowered for hint in hints)


async def router_node(state: AgentState) -> AgentState:
    """Classify user query intent into onboarding, alert, watchlist, research, news, document, or general."""
    text = state.get("input_text", "")
    is_onboarded = state.get("is_onboarded", False)
    session = state.get("db_session")
    user = state.get("metadata", {}).get("user")

    if not is_onboarded:
        state["intent"] = "onboarding"
        return state

    if session and user:
        try:
            document_service = DocumentService(session)
            if await document_service.has_document_context(user.id) and _looks_like_document_followup(text):
                state["intent"] = "document"
                logger.info(f"Routed message from Telegram ID {state['telegram_id']} to intent: document")
                return state
        except Exception as exc:
            logger.debug("Document context routing fallback triggered: %s", exc)

    prompt = f"User Message: '{text}'"
    raw_intent = await gemini_client.generate_response(prompt, system_instruction=ROUTER_SYSTEM_PROMPT)
    intent = raw_intent.strip().lower()

    if intent not in ["onboarding", "alert", "watchlist", "research", "news", "document", "general"]:
        lowered = text.lower()
        if any(kw in lowered for kw in ["alert", "notify", "remind", "what alerts", "show my alerts", "cancel my alert", "turn off all my alerts"]):
            intent = "alert"
        elif any(kw in lowered for kw in ["watchlist", "watch", "track", "follow", "remove", "add", "watching"]):
            intent = "watchlist"
        elif any(kw in lowered for kw in ["compare", "vs", "stock", "nvda", "amd", "tsla", "aapl"]):
            intent = "research"
        elif any(kw in lowered for kw in ["news", "headline", "market", "happened"]):
            intent = "news"
        elif any(kw in lowered for kw in ["pdf", "report", "document", "summarize"]):
            intent = "document"
        elif session and user and _looks_like_document_followup(text):
            try:
                document_service = DocumentService(session)
                if await document_service.has_document_context(user.id):
                    intent = "document"
            except Exception:
                intent = "general"
        else:
            intent = "general"

    logger.info(f"Routed message from Telegram ID {state['telegram_id']} to intent: {intent}")
    state["intent"] = intent
    return state
