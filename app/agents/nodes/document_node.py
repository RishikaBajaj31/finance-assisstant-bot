"""Document node for PDF question answering."""

from uuid import UUID

from app.agents.state import AgentState
from app.services.document_service import DocumentService


async def document_node(state: AgentState) -> AgentState:
    session = state.get("db_session")
    user_id = state.get("user_id")
    query = state.get("input_text", "")
    document_id = state.get("document_id")

    if not session or not user_id:
        state["response"] = "I can help with document analysis once your PDF is uploaded and linked to your profile."
        return state

    service = DocumentService(session)
    try:
        parsed_user_id = UUID(str(user_id))
        state["response"] = await service.query_document(parsed_user_id, query)
    except Exception:
        if document_id:
            state["response"] = "I found your document, but I could not analyze it cleanly. Please try uploading it again."
        else:
            state["response"] = "I can analyze PDFs once a document is uploaded."
    return state
