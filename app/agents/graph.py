"""LangGraph workflow for the financial assistant."""

from langgraph.graph import END, StateGraph

from app.agents.nodes.memory_node import memory_node
from app.agents.nodes.alert_node import alert_node
from app.agents.nodes.document_node import document_node
from app.agents.nodes.news_node import news_node
from app.agents.nodes.onboarding_node import onboarding_node
from app.agents.nodes.response_node import response_node
from app.agents.nodes.research_node import research_node
from app.agents.nodes.router_node import router_node
from app.agents.nodes.watchlist_node import watchlist_node
from app.agents.state import AgentState


def _route(state: AgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "onboarding":
        return "onboarding"
    if intent == "alert":
        return "alert"
    if intent == "research":
        return "research"
    if intent == "watchlist":
        return "watchlist"
    if intent == "news":
        return "news"
    if intent == "document":
        return "document"
    return "response"


graph = StateGraph(AgentState)
graph.add_node("router", router_node)
graph.add_node("memory", memory_node)
graph.add_node("onboarding", onboarding_node)
graph.add_node("alert", alert_node)
graph.add_node("research", research_node)
graph.add_node("watchlist", watchlist_node)
graph.add_node("news", news_node)
graph.add_node("document", document_node)
graph.add_node("response_node", response_node)

graph.set_entry_point("router")
graph.add_edge("router", "memory")
graph.add_conditional_edges("memory", _route, {
    "onboarding": "onboarding",
    "alert": "alert",
    "research": "research",
    "watchlist": "watchlist",
    "news": "news",
    "document": "document",
    "response": "response_node",
})

graph.add_edge("onboarding", "response_node")
graph.add_edge("alert", "response_node")
graph.add_edge("research", "response_node")
graph.add_edge("watchlist", "response_node")
graph.add_edge("news", "response_node")
graph.add_edge("document", "response_node")
graph.add_edge("response_node", END)

financial_assistant_graph = graph.compile()


async def run_agent(state: AgentState) -> AgentState:
    return await financial_assistant_graph.ainvoke(state)
