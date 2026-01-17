"""Chat subagent for general conversation with tool calling and handoff support."""

import uuid
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

from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.agents.state import ChatState
from app.agents.tools import (
    web_search,
    generate_image,
    analyze_image,
    get_handoff_tools_for_agent,
    is_handoff_response,
    parse_handoff_response,
)
from app.agents.tools.search_gate import should_enable_tools
from app.agents.utils import (
    append_history,
    build_image_context_message,
    extract_and_add_image_events,
    create_stage_event,
    create_tool_call_event,
    create_tool_result_event,
    truncate_content,
)
from app.agents import events
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import extract_text_from_content, llm_service

logger = get_logger(__name__)

# Available tools for the chat agent
CHAT_TOOLS = [web_search, generate_image, analyze_image]
MAX_TOOL_ITERATIONS = 5


async def agent_node(state: ChatState) -> dict:
    """Process a chat message, potentially calling tools or initiating handoffs.

    Args:
        state: Current chat state with query and messages

    Returns:
        Dict with updated messages, events, and potential handoff
    """
    query = state.get("query") or ""
    system_prompt = state.get("system_prompt") or CHAT_SYSTEM_PROMPT
    lc_messages = state.get("lc_messages") or []
    image_attachments = state.get("image_attachments") or []

    logger.info("chat_agent_processing", query=query[:50], image_count=len(image_attachments))

    event_list = []

    # Initialize messages if this is the first call
    if not lc_messages:
        event_list.append(create_stage_event("chat", "Processing query...", "running"))

        lc_messages = [SystemMessage(content=system_prompt)]

        # Add history if present
        history = state.get("messages", [])
        append_history(lc_messages, history)

        # Add multimodal image message if images are attached
        image_message = build_image_context_message(image_attachments)
        if image_message:
            lc_messages.append(image_message)
            logger.info("image_context_added_to_chat", image_count=len(image_attachments))

        # Add current query
        lc_messages.append(HumanMessage(content=query))

    history = state.get("messages", [])
    # Enable tools if search/image triggers detected OR images are attached
    enable_tools = should_enable_tools(query, history) or bool(image_attachments)
    if state.get("tool_iterations", 0) > 0:
        enable_tools = True

    # Get handoff tools for chat agent
    handoff_tools = get_handoff_tools_for_agent("chat")

    # Get LLM with tier routing (chat uses PRO tier by default)
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.get_llm_for_task(
        task_type="chat",
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    # Combine regular tools with handoff tools
    all_tools = CHAT_TOOLS + handoff_tools if enable_tools else handoff_tools
    llm_with_tools = llm.bind_tools(all_tools) if all_tools else llm

    try:
        # Use astream to enable streaming
        response_chunks = []
        async for chunk in llm_with_tools.astream(lc_messages):
            response_chunks.append(chunk)

        # Build complete response from chunks
        if response_chunks:
            response = response_chunks[-1]

            # Accumulate all content
            full_content = ""
            all_tool_calls = []
            for chunk in response_chunks:
                if hasattr(chunk, "content") and chunk.content:
                    full_content += extract_text_from_content(chunk.content)
                if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                    all_tool_calls.extend(chunk.tool_calls)

            # Normalize tool calls
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
                normalized_tool_calls.append({
                    **tool_call,
                    "id": tool_call_id,
                    "name": tool_name,
                    "args": tool_args,
                })

            tool_iterations = state.get("tool_iterations", 0)
            use_fallback_response = False
            if normalized_tool_calls and tool_iterations >= MAX_TOOL_ITERATIONS:
                event_list.append(create_stage_event(
                    "tool",
                    "Tool limit reached; finishing without more tool calls.",
                    "completed",
                ))
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
                response = AIMessage(
                    content=full_content,
                    tool_calls=normalized_tool_calls if normalized_tool_calls else None,
                )
        else:
            response = await llm_with_tools.ainvoke(lc_messages)

        lc_messages.append(response)

        # Check if there are tool calls
        if response.tool_calls:
            tool_iterations = state.get("tool_iterations", 0) + 1
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name") or ""
                if not tool_name:
                    continue
                event_list.append(create_tool_call_event(
                    tool_name,
                    tool_call.get("args") or {},
                ))
            logger.info(
                "chat_tool_calls",
                tools=[tc.get("name") for tc in response.tool_calls if tc.get("name")],
            )
        else:
            # No tool calls - we have the final response
            event_list.append(create_stage_event("chat", "Response generated", "completed"))

        return {
            "lc_messages": lc_messages,
            "events": event_list,
            "tool_iterations": tool_iterations if response.tool_calls else state.get("tool_iterations", 0),
        }

    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        event_list.append(create_stage_event("chat", f"Error: {str(e)}", "completed"))
        error_msg = AIMessage(content=f"I apologize, but I encountered an error: {e}")
        lc_messages.append(error_msg)
        return {
            "lc_messages": lc_messages,
            "events": event_list,
        }


async def tool_node(state: ChatState) -> dict:
    """Execute tool calls and return results, including handoff detection.

    Args:
        state: Current chat state with pending tool calls

    Returns:
        Dict with tool results added to messages and potential handoff
    """
    lc_messages = state.get("lc_messages", [])

    event_list = [create_stage_event("tool", "Executing tools...", "running")]

    # Get the last AI message with tool calls
    last_message = lc_messages[-1] if lc_messages else None
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {
            "lc_messages": lc_messages,
            "events": event_list,
            "tool_iterations": state.get("tool_iterations", 0),
        }

    # Check for handoff tool calls first
    pending_handoff = None
    regular_tool_calls = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name") or ""
        if tool_name.startswith("handoff_to_"):
            # This is a handoff request
            target_agent = tool_name.replace("handoff_to_", "")
            task_description = tool_call.get("args", {}).get("task_description", "")
            context = tool_call.get("args", {}).get("context", "")

            pending_handoff = {
                "source_agent": "chat",
                "target_agent": target_agent,
                "task_description": task_description,
                "context": context,
            }

            event_list.append(events.handoff(
                source="chat",
                target=target_agent,
                task=task_description,
            ))

            logger.info(
                "chat_handoff_detected",
                target=target_agent,
                task=task_description[:50],
            )
        else:
            regular_tool_calls.append(tool_call)

    # If there's a handoff, return it without executing other tools
    if pending_handoff:
        # Add a message indicating handoff
        handoff_msg = ToolMessage(
            content=f"Handing off to {pending_handoff['target_agent']} agent.",
            tool_call_id=last_message.tool_calls[0].get("id", str(uuid.uuid4())),
        )
        lc_messages.append(handoff_msg)

        event_list.append(create_stage_event("tool", "Handoff initiated", "completed"))

        return {
            "lc_messages": lc_messages,
            "events": event_list,
            "tool_iterations": state.get("tool_iterations", 0),
            "pending_handoff": pending_handoff,
        }

    # Execute regular tool calls
    handoff_tools = get_handoff_tools_for_agent("chat")
    all_tools = CHAT_TOOLS + handoff_tools
    tool_executor = ToolNode(all_tools)
    tool_results = await tool_executor.ainvoke({"messages": [last_message]})

    # Add tool results to messages
    for msg in tool_results.get("messages", []):
        lc_messages.append(msg)
        if isinstance(msg, ToolMessage):
            # Handle image generation results
            if msg.name == "generate_image":
                extract_and_add_image_events(msg.content, event_list)

            # Emit source events from search results
            event_list.append(create_tool_result_event(
                msg.name,
                msg.content,
            ))

    event_list.append(create_stage_event("tool", "Tools completed", "completed"))

    logger.info("chat_tools_executed", count=len(tool_results.get("messages", [])))

    return {
        "lc_messages": lc_messages,
        "events": event_list,
        "tool_iterations": state.get("tool_iterations", 0),
    }


def should_continue(state: ChatState) -> Literal["tools", "finalize"]:
    """Determine whether to continue with tools or finalize.

    Args:
        state: Current chat state

    Returns:
        Next node: "tools" if tool calls pending, "finalize" otherwise
    """
    # Check for pending handoff - go to finalize to propagate it
    if state.get("pending_handoff"):
        return "finalize"

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
        Dict with final response and potential handoff
    """
    lc_messages = state.get("lc_messages", [])

    # Find the last AI message without tool calls
    response = ""
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            response = msg.content
            break

    result = {"response": response}

    # Propagate handoff if present
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        result["pending_handoff"] = pending_handoff

    return result


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph with ReAct pattern and handoff support.

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
