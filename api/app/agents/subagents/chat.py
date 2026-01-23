"""Chat subagent for general conversation with tool calling and handoff support."""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph

from app.agents import events
from app.agents.context_compression import (
    CompressionConfig,
    ContextCompressor,
    inject_summary_as_context,
)
from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.agents.state import ChatState
from app.agents.tools import (
    get_react_config,
    get_tools_for_agent,
    get_tools_by_category,
    ToolCategory,
)
from app.agents.tools.react_tool import (
    truncate_messages_to_budget,
    truncate_tool_result,
)
from app.agents.utils import (
    append_history,
    build_image_context_message,
    create_stage_event,
    create_tool_call_event,
    create_tool_result_event,
    extract_and_add_image_events,
)
from app.ai.llm import extract_text_from_content, llm_service
from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import LLMProvider

logger = get_logger(__name__)


def _deduplicate_tool_messages(messages: list) -> list:
    """Remove duplicate ToolMessages with the same tool_call_id.

    The Anthropic API requires exactly one tool_result per tool_use.
    This ensures we don't have duplicates which cause API errors.

    Args:
        messages: List of LangChain messages

    Returns:
        Deduplicated list of messages
    """
    seen_tool_call_ids = set()
    result = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_call_id = msg.tool_call_id
            if tool_call_id in seen_tool_call_ids:
                logger.warning(
                    "duplicate_tool_message_removed",
                    tool_call_id=tool_call_id,
                    tool_name=getattr(msg, "name", "unknown"),
                )
                continue
            seen_tool_call_ids.add(tool_call_id)
        result.append(msg)

    return result


async def reason_node(state: ChatState) -> dict:
    """ReAct reason node: LLM reasons about what to do next.

    Args:
        state: Current chat state

    Returns:
        Dict with updated messages and events
    """
    query = state.get("query") or ""
    system_prompt = state.get("system_prompt") or CHAT_SYSTEM_PROMPT
    image_attachments = state.get("image_attachments") or []
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    existing_summary = state.get("context_summary")
    # Create a copy to avoid in-place mutation issues
    lc_messages = list(state.get("lc_messages", []))

    event_list = []
    new_context_summary = None

    # Initialize messages if empty
    if not lc_messages:
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

    # Deduplicate tool messages to prevent API errors
    lc_messages = _deduplicate_tool_messages(lc_messages)

    # Apply context compression before truncation (preserves semantic meaning)
    if settings.context_compression_enabled and len(lc_messages) > settings.context_compression_preserve_recent:
        compression_config = CompressionConfig(
            token_threshold=settings.context_compression_token_threshold,
            preserve_recent=settings.context_compression_preserve_recent,
            enabled=settings.context_compression_enabled,
        )
        compressor = ContextCompressor(compression_config)

        try:
            new_summary, lc_messages = await compressor.compress(
                lc_messages,
                existing_summary,
                provider,
            )
            if new_summary:
                # Inject summary as context after system message
                lc_messages = inject_summary_as_context(lc_messages, new_summary)
                new_context_summary = new_summary
                logger.info("context_compressed", summary_length=len(new_summary))
                event_list.append({
                    "type": "stage",
                    "name": "context",
                    "description": "Context compressed to preserve conversation history",
                    "status": "completed",
                })
        except Exception as e:
            logger.warning("context_compression_skipped", error=str(e))

    # Apply message truncation to stay within token budget (fallback safety)
    config = get_react_config("chat")
    lc_messages, was_truncated = truncate_messages_to_budget(
        lc_messages,
        max_tokens=config.max_message_tokens,
        preserve_recent=config.preserve_recent_messages,
    )
    if was_truncated:
        logger.info("chat_messages_truncated_for_budget")
        event_list.append({
            "type": "stage",
            "name": "context",
            "description": "Message history truncated to fit context window",
            "status": "completed",
        })

    # Get LLM with tools
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task(
        task_type="chat",
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    # Get all tools for chat agent
    all_tools = get_tools_for_agent("chat", include_handoffs=True)
    llm_with_tools = llm.bind_tools(all_tools) if all_tools else llm

    try:
        # Get AI response (may include tool calls)
        ai_message = await llm_with_tools.ainvoke(lc_messages)
        lc_messages.append(ai_message)

        # Stream tokens if no tool calls
        if not ai_message.tool_calls:
            response_text = extract_text_from_content(ai_message.content)
            if response_text:
                event_list.append(events.token(response_text))

        result = {
            "lc_messages": lc_messages,
            "events": event_list,
            "has_error": False,
        }
        # Include context summary if compression occurred
        if new_context_summary:
            result["context_summary"] = new_context_summary
        return result
    except Exception as e:
        logger.error("chat_reason_failed", error=str(e))
        error_msg = str(e)

        # Provide user-friendly error messages
        if "prompt is too long" in error_msg:
            response = "I apologize, but the conversation has become too long. Please start a new conversation or try a simpler request."
        else:
            response = f"I apologize, but I encountered an error: {e}"

        event_list.append(events.token(response))

        return {
            "lc_messages": lc_messages,
            "response": response,
            "events": event_list,
            "has_error": True,  # Signal to stop the loop
        }


async def act_node(state: ChatState) -> dict:
    """ReAct act node: Execute tools based on LLM's tool calls.

    Args:
        state: Current chat state with tool calls

    Returns:
        Dict with tool results and events
    """
    # Create a copy to avoid in-place mutation issues
    lc_messages = list(state.get("lc_messages", []))
    user_id = state.get("user_id")
    task_id = state.get("task_id")

    event_list = []

    # Get the last AI message (should have tool calls)
    ai_message = None
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage) and msg.tool_calls:
            ai_message = msg
            break

    if not ai_message or not ai_message.tool_calls:
        return {"events": event_list}

    # Check which tool calls already have results to avoid duplicates
    existing_tool_result_ids = {
        msg.tool_call_id
        for msg in lc_messages
        if isinstance(msg, ToolMessage)
    }

    # Filter out tool calls that already have results
    pending_tool_calls = [
        tc for tc in ai_message.tool_calls
        if tc.get("id", "") not in existing_tool_result_ids
    ]

    if not pending_tool_calls:
        logger.warning("act_node_no_pending_tool_calls", existing_count=len(existing_tool_result_ids))
        return {"events": event_list, "lc_messages": lc_messages}

    # Get tools
    all_tools = get_tools_for_agent("chat", include_handoffs=True)
    tool_map = {tool.name: tool for tool in all_tools}

    # Get browser tool names for context but don't handle side effects here
    BROWSER_TOOLS = {t.name for t in get_tools_by_category(ToolCategory.BROWSER)}

    # Execute pending tool calls (excluding already-processed ones)
    tool_results: list[ToolMessage] = []
    image_event_count = 0  # Track image events for indexing

    for tool_call in pending_tool_calls:
        tool_name = tool_call.get("name", "")
        tool_call_id = tool_call.get("id", "")
        args = tool_call.get("args", {})

        # Emit tool call event
        event_list.append(create_tool_call_event(tool_name, args, tool_call_id))

        if tool_name in tool_map:
            tool = tool_map[tool_name]
            try:
                # Add context args for tools that need them
                if tool_name in BROWSER_TOOLS:
                    args["user_id"] = user_id
                    args["task_id"] = task_id

                # Execute the tool
                result = await tool.ainvoke(args)
                result_str = str(result) if result is not None else ""

                # Emit tool result event (use preview, not full result)
                event_list.append(
                    create_tool_result_event(tool_name, result_str[:500], tool_call_id)
                )

                # Extract image events BEFORE truncation (preserve full base64 data)
                if tool_name == "generate_image" and result_str:
                    extract_and_add_image_events(
                        result_str, event_list, start_index=image_event_count
                    )
                    image_event_count = sum(
                        1 for e in event_list if isinstance(e, dict) and e.get("type") == "image"
                    )

                # Truncate tool result to avoid context overflow
                config = get_react_config("chat")
                result_str = truncate_tool_result(result_str, config.tool_result_max_chars)

                tool_results.append(
                    ToolMessage(
                        content=result_str,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )
            except Exception as e:
                logger.error("tool_execution_failed", tool=tool_name, error=str(e))
                error_msg = f"Error executing {tool_name}: {e}"
                event_list.append(create_tool_result_event(tool_name, error_msg, tool_call_id))
                tool_results.append(
                    ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )
        else:
            error_msg = f"Tool not found: {tool_name}"
            event_list.append(create_tool_result_event(tool_name, error_msg, tool_call_id))
            tool_results.append(
                ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

    # Add tool results to messages
    lc_messages.extend(tool_results)

    return {
        "lc_messages": lc_messages,
        "events": event_list,
        "tool_iterations": state.get("tool_iterations", 0) + 1,
    }


async def finalize_node(state: ChatState) -> dict:
    """Extract final response from messages and prepare output.

    Args:
        state: Current chat state

    Returns:
        Dict with final response and events (only new events; state.events uses operator.add)
    """
    lc_messages = state.get("lc_messages", [])

    # Extract final response from last AI message
    response = ""
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            response = extract_text_from_content(msg.content)
            break

    # Emit only the new stage event; state.events uses operator.add so we must not return full list
    final_event = create_stage_event("chat", "Response generated", "completed")

    return {
        "response": response,
        "events": [final_event],
    }


def should_continue(state: ChatState) -> Literal["act", "finalize"]:
    """Decide whether to continue ReAct loop or finalize.

    Args:
        state: Current chat state

    Returns:
        "act" if tools were called, "finalize" otherwise
    """
    # If there was an error, stop immediately
    if state.get("has_error"):
        logger.info("chat_stopping_due_to_error")
        return "finalize"

    # If response is already set (from error handling), stop
    if state.get("response"):
        return "finalize"

    lc_messages = state.get("lc_messages", [])

    # Check if last message has tool calls
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                # Check iteration limit
                config = get_react_config("chat")
                iters = state.get("tool_iterations", 0)
                if iters >= config.max_iterations:
                    logger.warning(
                        "chat_max_iterations_reached",
                        iterations=iters,
                    )
                    return "finalize"
                return "act"
            else:
                # No tool calls, we're done
                return "finalize"

    return "finalize"


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph with explicit ReAct pattern.

    Graph structure:
    [reason] -> [act?] -> [reason] -> ... -> END

    The ReAct loop:
    1. reason: LLM reasons and may call tools
    2. act: Execute tools if called
    3. Loop back to reason with tool results
    4. End when no more tool calls

    Returns:
        Compiled chat graph
    """
    graph = StateGraph(ChatState)

    # Add ReAct nodes
    graph.add_node("reason", reason_node)
    graph.add_node("act", act_node)
    graph.add_node("finalize", finalize_node)

    # Set entry point
    graph.set_entry_point("reason")

    # ReAct loop: reason -> act (if tools called) -> reason -> ... -> finalize
    graph.add_conditional_edges(
        "reason",
        should_continue,
        {
            "act": "act",
            "finalize": "finalize",
        },
    )

    # After acting, go back to reasoning
    graph.add_edge("act", "reason")

    # Finalize and end
    graph.add_edge("finalize", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
chat_subgraph = create_chat_graph()
