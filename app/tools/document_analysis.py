"""Document analysis helper tools."""

from langchain_core.tools import tool


@tool
async def document_analysis_tool(question: str) -> str:
    """Fallback helper for document analysis workflows."""
    return f"Document analysis request noted: {question}"
