"""Chat subagent for general conversation with tool calling support."""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.state import ChatState
from app.agents.tools import web_search
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

# Available tools for the chat agent
CHAT_TOOLS = [web_search]

CHAT_SYSTEM_PROMPT = """You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including answering questions, having conversations, and providing helpful information.

You have access to a web search tool that you can use to find current information when needed. Use it when:
- The user asks about recent events or news
- You need to verify facts or find up-to-date information
- The question requires knowledge beyond your training data

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""


async def agent_node(state: ChatState) -> dict:
    """Process a chat message, potentially calling tools.

    Args:
        state: Current chat state with query and messages

    Returns:
        Dict with updated messages and events
    """
    query = state.get("query", "")
    system_prompt = state.get("system_prompt", CHAT_SYSTEM_PROMPT)
    lc_messages = state.get("lc_messages", [])

    logger.info("chat_agent_processing", query=query[:50])

    events = []

    # Initialize messages if this is the first call
    if not lc_messages:
        events.append(
            {
                "type": "step",
                "step_type": "chat",
                "description": "Processing query...",
                "status": "running",
            }
        )

        lc_messages = [SystemMessage(content=system_prompt)]

        # Add history if present
        history = state.get("messages", [])
        for msg in history:
            if msg.get("role") == "user":
                lc_messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                lc_messages.append(AIMessage(content=msg.get("content", "")))

        # Add current query
        lc_messages.append(HumanMessage(content=query))

    # Get LLM with tools bound
    llm = llm_service.get_llm()
    llm_with_tools = llm.bind_tools(CHAT_TOOLS)

    try:
        # Invoke the model (streaming handled at supervisor level)
        response = await llm_with_tools.ainvoke(lc_messages)
        lc_messages.append(response)

        # Check if there are tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                events.append(
                    {
                        "type": "tool_call",
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                    }
                )
            logger.info(
                "chat_tool_calls",
                tools=[tc["name"] for tc in response.tool_calls],
            )
        else:
            # No tool calls - we have the final response
            events.append(
                {
                    "type": "step",
                    "step_type": "chat",
                    "description": "Response generated",
                    "status": "completed",
                }
            )

        return {
            "lc_messages": lc_messages,
            "events": events,
        }

    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        events.append(
            {
                "type": "step",
                "step_type": "chat",
                "description": f"Error: {str(e)}",
                "status": "completed",
            }
        )
        # Add error as AI message
        error_msg = AIMessage(content=f"I apologize, but I encountered an error: {e}")
        lc_messages.append(error_msg)
        return {
            "lc_messages": lc_messages,
            "events": events,
        }


async def tool_node(state: ChatState) -> dict:
    """Execute tool calls and return results.

    Args:
        state: Current chat state with pending tool calls

    Returns:
        Dict with tool results added to messages
    """
    lc_messages = state.get("lc_messages", [])

    events = [
        {
            "type": "step",
            "step_type": "tool",
            "description": "Executing search...",
            "status": "running",
        }
    ]

    # Get the last AI message with tool calls
    last_message = lc_messages[-1] if lc_messages else None
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"lc_messages": lc_messages, "events": events}

    # Execute each tool call
    tool_executor = ToolNode(CHAT_TOOLS)
    tool_results = await tool_executor.ainvoke({"messages": [last_message]})

    # Add tool results to messages
    for msg in tool_results.get("messages", []):
        lc_messages.append(msg)
        if isinstance(msg, ToolMessage):
            # Emit source events from search results
            events.append(
                {
                    "type": "tool_result",
                    "tool": msg.name,
                    "content": msg.content[:500] if len(msg.content) > 500 else msg.content,
                }
            )

    events.append(
        {
            "type": "step",
            "step_type": "tool",
            "description": "Search completed",
            "status": "completed",
        }
    )

    logger.info("chat_tools_executed", count=len(tool_results.get("messages", [])))

    return {
        "lc_messages": lc_messages,
        "events": events,
    }


def should_continue(state: ChatState) -> Literal["tools", "finalize"]:
    """Determine whether to continue with tools or finalize.

    Args:
        state: Current chat state

    Returns:
        Next node: "tools" if tool calls pending, "finalize" otherwise
    """
    lc_messages = state.get("lc_messages", [])
    if not lc_messages:
        return "finalize"

    last_message = lc_messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "finalize"


async def finalize_node(state: ChatState) -> dict:
    """Extract the final response from messages.

    Args:
        state: Current chat state with completed conversation

    Returns:
        Dict with final response
    """
    lc_messages = state.get("lc_messages", [])

    # Find the last AI message without tool calls
    response = ""
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            response = msg.content
            break

    return {"response": response}


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph with ReAct pattern.

    Graph structure:
    [agent] -> tools? -> [tools] -> [agent] (loop)
            -> finalize -> [finalize] -> END

    Returns:
        Compiled chat graph
    """
    graph = StateGraph(ChatState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("finalize", finalize_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Conditional edge: check for tool calls
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "finalize": "finalize",
        },
    )

    # After tools, go back to agent
    graph.add_edge("tools", "agent")

    # Finalize ends the graph
    graph.add_edge("finalize", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
chat_subgraph = create_chat_graph()
