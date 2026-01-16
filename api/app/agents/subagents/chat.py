"""Chat subagent for general conversation with tool calling support."""

from typing import Literal
import uuid

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.agents.state import ChatState
from app.agents.tools import web_search
from app.agents.tools.search_gate import should_enable_web_search
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import extract_text_from_content, llm_service

logger = get_logger(__name__)

# Available tools for the chat agent
CHAT_TOOLS = [web_search]
MAX_TOOL_ITERATIONS = 5


async def agent_node(state: ChatState) -> dict:
    """Process a chat message, potentially calling tools.

    Args:
        state: Current chat state with query and messages

    Returns:
        Dict with updated messages and events
    """
    query = state.get("query") or ""
    system_prompt = state.get("system_prompt") or CHAT_SYSTEM_PROMPT
    lc_messages = state.get("lc_messages") or []

    logger.info("chat_agent_processing", query=query[:50])

    events = []

    # Initialize messages if this is the first call
    if not lc_messages:
        events.append(
            {
                "type": "stage",
                "name": "chat",
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

    history = state.get("messages", [])
    enable_tools = should_enable_web_search(query, history)
    if state.get("tool_iterations", 0) > 0:
        enable_tools = True

    # Get LLM (optionally with tools bound)
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    model = state.get("model")
    llm = llm_service.get_llm(provider=provider, model=model)
    llm_with_tools = llm.bind_tools(CHAT_TOOLS) if enable_tools else llm

    try:
        # Use astream to enable streaming (supervisor will capture on_chat_model_stream events)
        # We need to accumulate chunks to build the complete response for tool call detection
        response_chunks = []
        async for chunk in llm_with_tools.astream(lc_messages):
            response_chunks.append(chunk)
        
        # Build complete response from chunks
        # The last chunk typically contains tool_calls if any
        if response_chunks:
            # Start with the last chunk (usually has tool_calls)
            response = response_chunks[-1]
            
            # Accumulate all content
            full_content = ""
            all_tool_calls = []
            for chunk in response_chunks:
                if hasattr(chunk, "content") and chunk.content:
                    full_content += extract_text_from_content(chunk.content)
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    all_tool_calls.extend(chunk.tool_calls)

            # Ensure tool calls have ids for ToolNode/ToolMessage compatibility
            normalized_tool_calls = []
            for tool_call in all_tool_calls:
                tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                if not tool_name:
                    continue
                tool_args = tool_call.get("args") or {}
                if tool_name == "web_search" and not tool_args.get("query"):
                    if query:
                        tool_args = {**tool_args, "query": query}
                    else:
                        continue
                tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id")
                if not tool_call_id:
                    tool_call_id = str(uuid.uuid4())
                normalized_tool_calls.append(
                    {
                        **tool_call,
                        "id": tool_call_id,
                        "name": tool_name,
                        "args": tool_args,
                    }
                )
            
            tool_iterations = state.get("tool_iterations", 0)
            use_fallback_response = False
            if normalized_tool_calls and tool_iterations >= MAX_TOOL_ITERATIONS:
                events.append(
                    {
                        "type": "stage",
                        "name": "tool",
                        "description": "Tool limit reached; finishing without more tool calls.",
                        "status": "completed",
                    }
                )
                response = AIMessage(
                    content="I couldn't complete the request after multiple tool attempts. "
                    "Please rephrase or provide more specific details."
                )
                normalized_tool_calls = []
                use_fallback_response = True

            # Update response with accumulated content
            if isinstance(response, AIMessage):
                if not use_fallback_response:
                    response.content = full_content
                response.tool_calls = normalized_tool_calls or []
            else:
                # Create new AIMessage if needed
                response = AIMessage(
                    content=full_content,
                    tool_calls=normalized_tool_calls if normalized_tool_calls else None,
                )
        else:
            # Fallback if no chunks
            response = await llm_with_tools.ainvoke(lc_messages)
        
        lc_messages.append(response)

        # Check if there are tool calls
        if response.tool_calls:
            tool_iterations = state.get("tool_iterations", 0) + 1
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name") or ""
                if not tool_name:
                    continue
                events.append(
                    {
                        "type": "tool_call",
                        "tool": tool_name,
                        "args": tool_call.get("args") or {},
                    }
                )
            logger.info(
                "chat_tool_calls",
                tools=[tc.get("name") for tc in response.tool_calls if tc.get("name")],
            )
        else:
            # No tool calls - we have the final response
            events.append(
                {
                    "type": "stage",
                    "name": "chat",
                    "description": "Response generated",
                    "status": "completed",
                }
            )

        return {
            "lc_messages": lc_messages,
            "events": events,
            "tool_iterations": tool_iterations if response.tool_calls else state.get("tool_iterations", 0),
        }

    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        events.append(
            {
                "type": "stage",
                "name": "chat",
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
            "type": "stage",
            "name": "tool",
            "description": "Executing search...",
            "status": "running",
        }
    ]

    # Get the last AI message with tool calls
    last_message = lc_messages[-1] if lc_messages else None
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {
            "lc_messages": lc_messages,
            "events": events,
            "tool_iterations": state.get("tool_iterations", 0),
        }

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
            "type": "stage",
            "name": "tool",
            "description": "Search completed",
            "status": "completed",
        }
    )

    logger.info("chat_tools_executed", count=len(tool_results.get("messages", [])))

    return {
        "lc_messages": lc_messages,
        "events": events,
        "tool_iterations": state.get("tool_iterations", 0),
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

    tool_iterations = state.get("tool_iterations", 0)
    if tool_iterations >= MAX_TOOL_ITERATIONS:
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
