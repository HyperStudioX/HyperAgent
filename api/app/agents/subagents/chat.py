"""Chat subagent for general conversation."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import ChatState
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

CHAT_SYSTEM_PROMPT = """You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including answering questions, having conversations, and providing helpful information.

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""


async def chat_node(state: ChatState) -> dict:
    """Process a chat message and generate a response.

    Args:
        state: Current chat state with query

    Returns:
        Dict with response and events
    """
    query = state.get("query", "")
    system_prompt = state.get("system_prompt", CHAT_SYSTEM_PROMPT)

    logger.info("chat_processing", query=query[:50])

    events = [
        {
            "type": "step",
            "step_type": "chat",
            "description": "Generating response...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query),
    ]

    # Add history if present
    history = state.get("messages", [])
    if history:
        for msg in history:
            if msg.get("role") == "user":
                messages.insert(-1, HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages.insert(-1, AIMessage(content=msg.get("content", "")))

    try:
        # Stream the response
        response_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                response_chunks.append(chunk.content)
                events.append({"type": "token", "content": chunk.content})

        response = "".join(response_chunks)

        events.append(
            {
                "type": "step",
                "step_type": "chat",
                "description": "Response generated",
                "status": "completed",
            }
        )

        logger.info("chat_completed", response_length=len(response))

        return {
            "response": response,
            "events": events,
        }

    except Exception as e:
        logger.error("chat_failed", error=str(e))
        events.append(
            {
                "type": "step",
                "step_type": "chat",
                "description": f"Error: {str(e)}",
                "status": "completed",
            }
        )
        return {
            "response": f"I apologize, but I encountered an error: {str(e)}",
            "events": events,
        }


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph.

    Returns:
        Compiled chat graph
    """
    graph = StateGraph(ChatState)

    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
chat_subgraph = create_chat_graph()
