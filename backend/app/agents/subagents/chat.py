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
from app.agents.hitl.interrupt_manager import (
    create_approval_interrupt,
    get_interrupt_manager,
)
from app.agents.hitl.tool_risk import requires_approval
from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.agents.state import ChatState
from app.agents.tools import (
    ToolCategory,
    get_react_config,
    get_tools_by_category,
    get_tools_for_agent,
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
from app.guardrails.scanners.output_scanner import output_scanner
from app.guardrails.scanners.tool_scanner import tool_scanner
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

    # Debug: Log messages before deduplication
    logger.info(
        "reason_node_messages",
        message_count=len(lc_messages),
        message_types=[type(m).__name__ for m in lc_messages],
        has_tool_messages=any(isinstance(m, ToolMessage) for m in lc_messages),
    )

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
                # Apply output guardrails
                scan_result = await output_scanner.scan(response_text, query)
                if scan_result.blocked:
                    logger.warning(
                        "output_guardrail_blocked",
                        violations=[v.value for v in scan_result.violations],
                        reason=scan_result.reason,
                    )
                    response_text = (
                        "I apologize, but I cannot provide that response. "
                        "Please ask a different question."
                    )
                elif scan_result.sanitized_content:
                    logger.info("output_guardrail_sanitized")
                    response_text = scan_result.sanitized_content

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

    Includes Human-in-the-Loop (HITL) approval for high-risk tools.

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
    interrupt_manager = get_interrupt_manager()

    for tool_call in pending_tool_calls:
        tool_name = tool_call.get("name", "")
        tool_call_id = tool_call.get("id", "")
        args = tool_call.get("args", {})

        # Check if tool requires approval (high-risk tools like browser, code execution)
        if requires_approval(
            tool_name,
            auto_approve_tools=state.get("auto_approve_tools", []),
            hitl_enabled=state.get("hitl_enabled", True),
            risk_threshold=settings.hitl_default_risk_threshold,
        ):
            thread_id = task_id or user_id or "default"

            # Create approval interrupt event
            interrupt_event = create_approval_interrupt(
                tool_name=tool_name,
                args=args,
                timeout_seconds=settings.hitl_approval_timeout,
            )
            interrupt_id = interrupt_event["interrupt_id"]

            # Emit tool call event first (so frontend knows what's being approved)
            event_list.append(create_tool_call_event(tool_name, args, tool_call_id))
            event_list.append(interrupt_event)

            logger.info(
                "hitl_tool_approval_required",
                tool_name=tool_name,
                interrupt_id=interrupt_id,
                thread_id=thread_id,
                tool_call_id=tool_call_id,
            )

            # Store the interrupt in Redis for the frontend to find
            await interrupt_manager.create_interrupt(
                thread_id=thread_id,
                interrupt_id=interrupt_id,
                interrupt_data=interrupt_event,
            )

            # Return with pending interrupt - will be handled by wait_interrupt_node
            lc_messages.extend(tool_results)
            return {
                "lc_messages": lc_messages,
                "events": event_list,
                "tool_iterations": state.get("tool_iterations", 0) + 1,
                "pending_interrupt": {
                    "interrupt_id": interrupt_id,
                    "thread_id": thread_id,
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "tool_args": args,  # Store for execution after approval
                    "is_approval": True,
                },
            }

        # Emit tool call event
        event_list.append(create_tool_call_event(tool_name, args, tool_call_id))

        # Handle ask_user tool specially - emit interrupt and pause for response
        if tool_name == "ask_user":
            from app.agents.hitl.interrupt_manager import (
                create_decision_interrupt,
                create_input_interrupt,
            )

            # Debug: Log the raw args received from LLM
            logger.info(
                "hitl_ask_user_args",
                tool_call_id=tool_call_id,
                args=args,
            )

            question = args.get("question", "")
            question_type = args.get("question_type", "input")
            options = args.get("options")
            context = args.get("context")
            thread_id = task_id or user_id or "default"

            # Build message with context
            message = f"{context}\n\n{question}" if context else question

            # Handle confirmation type
            if question_type == "confirmation":
                options = [
                    {"label": "Yes", "value": "yes", "description": "Proceed"},
                    {"label": "No", "value": "no", "description": "Cancel"},
                ]
                question_type = "decision"

            # Create interrupt event
            if question_type == "decision" and options:
                interrupt_event = create_decision_interrupt(
                    title="Agent Question",
                    message=message,
                    options=options,
                    timeout_seconds=settings.hitl_decision_timeout,
                )
            else:
                interrupt_event = create_input_interrupt(
                    title="Agent Question",
                    message=message,
                    timeout_seconds=settings.hitl_decision_timeout,
                )

            interrupt_id = interrupt_event["interrupt_id"]
            event_list.append(interrupt_event)

            logger.info(
                "hitl_ask_user",
                question_type=question_type,
                interrupt_id=interrupt_id,
                thread_id=thread_id,
                question=question[:100] if question else "",
                message=message[:100] if message else "",
                options_count=len(options) if options else 0,
                tool_call_id=tool_call_id,
            )

            # Store the interrupt in Redis for the frontend to find
            await interrupt_manager.create_interrupt(
                thread_id=thread_id,
                interrupt_id=interrupt_id,
                interrupt_data=interrupt_event,
            )

            # Return with pending interrupt - will be handled by wait_interrupt_node
            lc_messages.extend(tool_results)
            return {
                "lc_messages": lc_messages,
                "events": event_list,
                "tool_iterations": state.get("tool_iterations", 0) + 1,
                "pending_interrupt": {
                    "interrupt_id": interrupt_id,
                    "thread_id": thread_id,
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                },
            }

        if tool_name in tool_map:
            tool = tool_map[tool_name]

            # Tool guardrails check
            tool_scan_result = await tool_scanner.scan(tool_name, args)
            if tool_scan_result.blocked:
                logger.warning(
                    "tool_guardrail_blocked",
                    tool_name=tool_name,
                    violations=[v.value for v in tool_scan_result.violations],
                    reason=tool_scan_result.reason,
                )
                error_msg = f"Tool blocked: {tool_scan_result.reason}"
                event_list.append(create_tool_result_event(tool_name, error_msg, tool_call_id))
                tool_results.append(
                    ToolMessage(
                        content=error_msg,
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                )
                continue

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


def should_wait_or_reason(state: ChatState) -> Literal["wait_interrupt", "reason"]:
    """Decide whether to wait for interrupt response or continue reasoning.

    Args:
        state: Current chat state

    Returns:
        "wait_interrupt" if pending interrupt exists, "reason" otherwise
    """
    pending = state.get("pending_interrupt")
    if pending:
        logger.info(
            "routing_to_wait_interrupt",
            interrupt_id=pending.get("interrupt_id"),
            thread_id=pending.get("thread_id"),
        )
        return "wait_interrupt"
    logger.debug("routing_to_reason", has_pending=False)
    return "reason"


async def wait_interrupt_node(state: ChatState) -> dict:
    """Wait for user response to a pending interrupt and add result.

    This node handles the async wait for user input when the agent
    has asked a question via ask_user tool.

    Args:
        state: Current chat state with pending_interrupt

    Returns:
        Dict with tool result message and cleared pending_interrupt
    """
    logger.info("wait_interrupt_node_started")

    pending = state.get("pending_interrupt")
    if not pending:
        logger.warning("wait_interrupt_node_no_pending")
        return {"pending_interrupt": None}

    interrupt_id = pending.get("interrupt_id")
    thread_id = pending.get("thread_id", "default")
    tool_call_id = pending.get("tool_call_id")
    tool_name = pending.get("tool_name", "ask_user")

    interrupt_manager = get_interrupt_manager()
    event_list = []
    lc_messages = list(state.get("lc_messages", []))

    # Debug: Log the messages before adding tool result
    logger.info(
        "wait_interrupt_messages_before",
        message_count=len(lc_messages),
        message_types=[type(m).__name__ for m in lc_messages],
    )

    logger.info(
        "wait_interrupt_subscribing",
        interrupt_id=interrupt_id,
        thread_id=thread_id,
        tool_call_id=tool_call_id,
    )

    # Get tools for potential execution (needed for approval flow)
    all_tools = get_tools_for_agent("chat", include_handoffs=True)
    tool_map = {tool.name: tool for tool in all_tools}

    # Track auto_approve updates
    auto_approve_tools = list(state.get("auto_approve_tools", []))

    try:
        # Wait for user response
        response = await interrupt_manager.wait_for_response(
            thread_id=thread_id,
            interrupt_id=interrupt_id,
            timeout_seconds=settings.hitl_decision_timeout,
        )

        action = response.get("action", "skip")
        value = response.get("value")

        logger.info(
            "wait_interrupt_response_received",
            interrupt_id=interrupt_id,
            action=action,
            is_approval=pending.get("is_approval", False),
        )

        # Handle approval responses for high-risk tools
        if pending.get("is_approval"):
            tool_args = pending.get("tool_args", {})
            user_id = state.get("user_id")
            task_id = state.get("task_id")

            if action == "approve":
                # Execute the approved tool
                if tool_name in tool_map:
                    tool = tool_map[tool_name]
                    try:
                        # Add context args for browser tools
                        browser_tools = {
                            t.name for t in get_tools_by_category(ToolCategory.BROWSER)
                        }
                        if tool_name in browser_tools:
                            tool_args["user_id"] = user_id
                            tool_args["task_id"] = task_id

                        result = await tool.ainvoke(tool_args)
                        result_str = f"Tool executed: {str(result)[:500]}"

                        logger.info(
                            "hitl_tool_approved_and_executed",
                            tool_name=tool_name,
                            tool_call_id=tool_call_id,
                        )
                    except Exception as e:
                        logger.error(
                            "hitl_approved_tool_failed",
                            tool=tool_name,
                            error=str(e),
                        )
                        result_str = f"Error executing {tool_name}: {e}"
                else:
                    result_str = f"Tool not found: {tool_name}"

            elif action == "approve_always":
                # Add to auto-approve list and execute
                if tool_name not in auto_approve_tools:
                    auto_approve_tools.append(tool_name)
                    logger.info(
                        "hitl_tool_auto_approved",
                        tool_name=tool_name,
                    )

                # Execute the tool
                if tool_name in tool_map:
                    tool = tool_map[tool_name]
                    try:
                        browser_tools = {
                            t.name for t in get_tools_by_category(ToolCategory.BROWSER)
                        }
                        if tool_name in browser_tools:
                            tool_args["user_id"] = user_id
                            tool_args["task_id"] = task_id

                        result = await tool.ainvoke(tool_args)
                        result_str = (
                            f"Tool executed (auto-approved): {str(result)[:500]}"
                        )
                    except Exception as e:
                        logger.error(
                            "hitl_approved_tool_failed",
                            tool=tool_name,
                            error=str(e),
                        )
                        result_str = f"Error executing {tool_name}: {e}"
                else:
                    result_str = f"Tool not found: {tool_name}"

            elif action == "deny":
                result_str = f"User denied execution of {tool_name}. The tool was not executed."
                logger.info(
                    "hitl_tool_denied",
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                )

            else:
                result_str = f"Unknown approval action: {action}. Tool not executed."

        else:
            # Handle ask_user responses (non-approval interrupts)
            if action == "skip":
                result_str = "User skipped this question."
            elif action in ("select", "input"):
                if value:
                    result_str = f"User responded: {value}"
                else:
                    result_str = "User skipped this question."
            else:
                result_str = f"User action: {action}"

        # Add tool result message
        lc_messages.append(
            ToolMessage(
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
        )

        # Emit response event
        from app.agents.utils import create_tool_result_event
        event_list.append(create_tool_result_event(tool_name, result_str, tool_call_id))

        # Debug: Log after adding tool result
        logger.info(
            "wait_interrupt_messages_after",
            message_count=len(lc_messages),
            result_str=result_str,
            tool_call_id=tool_call_id,
        )

    except TimeoutError:
        logger.warning("wait_interrupt_timeout", interrupt_id=interrupt_id)
        result_str = "timeout"
        lc_messages.append(
            ToolMessage(
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
        )

    except Exception as e:
        logger.error("wait_interrupt_error", error=str(e), interrupt_id=interrupt_id)
        result_str = f"error: {str(e)}"
        lc_messages.append(
            ToolMessage(
                content=result_str,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
        )

    result = {
        "lc_messages": lc_messages,
        "events": event_list,
        "pending_interrupt": None,  # Clear the pending interrupt
    }

    # Include auto_approve_tools if it was updated
    if auto_approve_tools != state.get("auto_approve_tools", []):
        result["auto_approve_tools"] = auto_approve_tools

    return result


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph with explicit ReAct pattern.

    Graph structure:
    [reason] -> [act?] -> [wait_interrupt?] -> [reason] -> ... -> END

    The ReAct loop:
    1. reason: LLM reasons and may call tools
    2. act: Execute tools if called (may set pending_interrupt for ask_user)
    3. wait_interrupt: If pending_interrupt, wait for user response
    4. Loop back to reason with tool results
    5. End when no more tool calls

    Returns:
        Compiled chat graph
    """
    graph = StateGraph(ChatState)

    # Add ReAct nodes
    graph.add_node("reason", reason_node)
    graph.add_node("act", act_node)
    graph.add_node("wait_interrupt", wait_interrupt_node)
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

    # After acting, check if we need to wait for interrupt or continue reasoning
    graph.add_conditional_edges(
        "act",
        should_wait_or_reason,
        {
            "wait_interrupt": "wait_interrupt",
            "reason": "reason",
        },
    )

    # After waiting for interrupt, go back to reasoning
    graph.add_edge("wait_interrupt", "reason")

    # Finalize and end
    graph.add_edge("finalize", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
chat_subgraph = create_chat_graph()
