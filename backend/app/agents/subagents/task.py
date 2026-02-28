"""Task subagent for general-purpose task handling with tool calling and handoff support."""

import json
import threading
import uuid
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
from app.agents.hitl.interrupt_manager import get_interrupt_manager
from app.agents.prompts import TASK_SYSTEM_MESSAGE, TASK_SYSTEM_PROMPT, get_task_system_prompt
from app.agents.state import TaskState
from app.agents.tools import (
    get_react_config,
    get_tools_for_agent,
)
from app.agents.tools.react_tool import (
    deduplicate_tool_messages,
    truncate_messages_to_budget,
)
from app.agents.tools.tool_pipeline import (
    TaskToolHooks,
    ToolExecutionContext,
    execute_tool,
    execute_tools_batch,
)
from app.agents.utils import (
    append_history,
    build_image_context_message,
)
from app.ai.llm import extract_text_from_content, llm_service
from app.config import settings
from app.core.logging import get_logger
from app.guardrails.scanners.output_scanner import output_scanner

logger = get_logger(__name__)

# Module-level caches for tool lists and config (computed once, thread-safe)
_cached_task_tools: list | None = None
_cached_react_config = None
_cache_lock = threading.Lock()


def _get_cached_task_tools() -> list:
    """Get the task tools list, computing and caching on first call (thread-safe)."""
    global _cached_task_tools
    if _cached_task_tools is None:
        with _cache_lock:
            if _cached_task_tools is None:
                _cached_task_tools = get_tools_for_agent("task", include_handoffs=True)
    return _cached_task_tools


def _get_cached_react_config():
    """Get the react config for task, computing and caching on first call (thread-safe)."""
    global _cached_react_config
    if _cached_react_config is None:
        with _cache_lock:
            if _cached_react_config is None:
                _cached_react_config = get_react_config("task")
    return _cached_react_config


def clear_tool_cache() -> None:
    """Reset cached task tools and react config.

    Useful for testing or when tool registration changes at runtime.
    """
    global _cached_task_tools, _cached_react_config
    with _cache_lock:
        _cached_task_tools = None
        _cached_react_config = None


def _extract_task_plan_from_messages(
    tool_messages: list[ToolMessage],
) -> list[dict] | None:
    """Extract execution plan from task_planning skill output in tool messages.

    Scans tool messages for an invoke_skill result with skill_id="task_planning".
    If found and successful, returns the parsed plan steps list.

    Args:
        tool_messages: List of ToolMessage from the current act iteration

    Returns:
        List of plan step dicts if a plan was found, None otherwise
    """
    for msg in tool_messages:
        if not isinstance(msg, ToolMessage) or msg.name != "invoke_skill":
            continue
        try:
            parsed = json.loads(msg.content)
            if (
                parsed.get("skill_id") == "task_planning"
                and parsed.get("success")
            ):
                output = parsed.get("output", {})
                steps = output.get("steps", [])
                if steps and isinstance(steps, list):
                    logger.info(
                        "task_plan_extracted_from_skill_output",
                        step_count=len(steps),
                        complexity=output.get("complexity_assessment"),
                    )
                    return steps
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
    return None


async def reason_node(state: TaskState) -> dict:
    """ReAct reason node: LLM reasons about what to do next.

    Args:
        state: Current chat state

    Returns:
        Dict with updated messages and events
    """
    query = state.get("query") or ""
    mode = state.get("mode")
    locale = state.get("locale", "en")
    system_prompt = state.get("system_prompt") or get_task_system_prompt(locale)
    image_attachments = state.get("image_attachments") or []
    provider = state.get("provider")
    existing_summary = state.get("context_summary")
    # Create a copy to avoid in-place mutation issues
    lc_messages = list(state.get("lc_messages", []))

    event_list = []
    new_context_summary = None

    # Initialize messages if empty
    if not lc_messages:
        # Use pre-built cached message when using the default system prompt
        if system_prompt == TASK_SYSTEM_PROMPT:
            sys_msg = TASK_SYSTEM_MESSAGE
        else:
            sys_msg = SystemMessage(
                content=system_prompt,
                additional_kwargs={"cache_control": {"type": "ephemeral"}},
            )
        lc_messages = [sys_msg]

        # Add history if present
        history = state.get("messages", [])
        append_history(lc_messages, history)

        # Add multimodal image message if images are attached
        image_message = build_image_context_message(image_attachments)
        if image_message:
            lc_messages.append(image_message)
            logger.info("image_context_added_to_chat", image_count=len(image_attachments))

        # For dedicated modes (app, image, slide), directly synthesize a
        # tool call to invoke the corresponding skill.  This avoids relying
        # on the LLM to emit the correct invoke_skill call — some models
        # (especially with thinking/reasoning mode) return a text response
        # instead of using tools, which causes the mode to silently fail.
        _DIRECT_SKILL_MODES = {
            "image": {
                "skill_id": "image_generation",
                "param_key": "prompt",
            },
            "app": {
                "skill_id": "app_builder",
                "param_key": "description",
            },
            "slide": {
                "skill_id": "slide_generation",
                "param_key": "topic",
            },
            "data": {
                "skill_id": "data_analysis",
                "param_key": "query",
            },
        }

        skill_spec = _DIRECT_SKILL_MODES.get(mode)
        if skill_spec:
            lc_messages.append(HumanMessage(content=query))
            # Build a synthetic AI message with the invoke_skill tool call
            tool_call_id = f"direct_{skill_spec['skill_id']}_{uuid.uuid4().hex[:8]}"
            skill_params = {skill_spec["param_key"]: query}

            # Pass attachment_ids for data_analysis skill
            if skill_spec["skill_id"] == "data_analysis":
                attachment_ids = state.get("attachment_ids") or []
                if attachment_ids:
                    skill_params["attachment_ids"] = attachment_ids

            ai_message = AIMessage(
                content="",
                tool_calls=[{
                    "name": "invoke_skill",
                    "args": {
                        "skill_id": skill_spec["skill_id"],
                        "params": skill_params,
                    },
                    "id": tool_call_id,
                    "type": "tool_call",
                }],
            )
            lc_messages.append(ai_message)
            logger.info(
                "direct_skill_invocation",
                mode=mode,
                skill_id=skill_spec["skill_id"],
                original_query=query[:100],
            )
            return {
                "lc_messages": lc_messages,
                "events": event_list,
                "has_error": False,
            }
        else:
            # Add current query
            lc_messages.append(HumanMessage(content=query))

    # Debug: Log messages before deduplication
    logger.debug(
        "reason_node_messages",
        message_count=len(lc_messages),
        message_types=[type(m).__name__ for m in lc_messages],
        has_tool_messages=any(isinstance(m, ToolMessage) for m in lc_messages),
    )

    # Deduplicate tool messages to prevent API errors
    lc_messages = deduplicate_tool_messages(lc_messages)

    # Apply context compression before truncation (preserves semantic meaning)
    # Only create CompressionConfig/ContextCompressor if compression may actually run
    if settings.context_compression_enabled and len(lc_messages) > settings.context_compression_preserve_recent:
        # Quick token estimate to avoid creating compressor when clearly under threshold
        from app.agents.context_compression import estimate_message_tokens

        estimated_tokens = sum(estimate_message_tokens(m) for m in lc_messages)
        if existing_summary:
            from app.agents.context_compression import estimate_tokens
            estimated_tokens += estimate_tokens(existing_summary)

        if estimated_tokens > settings.context_compression_token_threshold:
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
                    locale=locale,
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
    config = _get_cached_react_config()
    lc_messages, was_truncated = truncate_messages_to_budget(
        lc_messages,
        max_tokens=config.max_message_tokens,
        preserve_recent=config.preserve_recent_messages,
    )
    if was_truncated:
        logger.info("task_messages_truncated_for_budget")
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
        task_type="task",
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    # Get all tools for chat agent (cached)
    all_tools = _get_cached_task_tools()
    llm_with_tools = llm.bind_tools(all_tools) if all_tools else llm

    # Planned execution mode: inject current step context as a temporary message
    # This focuses the LLM on one step at a time instead of the full plan
    messages_for_llm = lc_messages
    execution_plan = state.get("execution_plan", [])
    current_step_index = state.get("current_step_index", 0)

    if execution_plan and current_step_index < len(execution_plan):
        current_step = execution_plan[current_step_index]
        step_number = current_step.get("step_number", current_step_index + 1)
        total_steps = len(execution_plan)
        tool_hint = current_step.get("tool_or_skill") or "any appropriate tool"

        step_guidance = SystemMessage(content=(
            f"[Plan Execution — Step {step_number} of {total_steps}]\n"
            f"Current step: {current_step['action']}\n"
            f"Recommended tool: {tool_hint}\n"
            f"Focus on completing this specific step. "
            f"Do not repeat or re-invoke the task_planning skill."
        ))
        # Create a temporary copy with guidance appended — not persisted in state
        messages_for_llm = list(lc_messages) + [step_guidance]

        logger.info(
            "planned_execution_step_injected",
            step_number=step_number,
            total_steps=total_steps,
            action=current_step["action"][:100],
        )
    elif execution_plan and current_step_index >= len(execution_plan):
        # All plan steps completed — inject completion hint
        completion_hint = SystemMessage(content=(
            "[Plan Execution — All steps completed]\n"
            "The execution plan has been fully carried out. "
            "Provide a final summary of what was accomplished."
        ))
        messages_for_llm = list(lc_messages) + [completion_hint]
        logger.info("planned_execution_all_steps_completed")

    try:
        # Get AI response (may include tool calls)
        try:
            ai_message = await llm_with_tools.ainvoke(messages_for_llm)
        except Exception as invoke_err:
            # Providers with "thinking" mode (e.g. DeepSeek, Kimi) require
            # reasoning_content on every assistant message with tool_calls.
            # ChatOpenAI silently drops this field from responses, so the
            # ThinkingAwareChatOpenAI subclass patches the payload. If the
            # flag wasn't set upfront (e.g. enable_thinking not configured),
            # detect it here and enable the patch for all future calls.
            if "reasoning_content" in str(invoke_err):
                logger.info("thinking_mode_detected_enabling_patch")
                # Enable the payload-level patch on the underlying LLM client
                inner_llm = getattr(llm_with_tools, "bound", llm_with_tools)
                if hasattr(inner_llm, "thinking_mode"):
                    inner_llm.thinking_mode = True
                ai_message = await llm_with_tools.ainvoke(messages_for_llm)
            else:
                raise

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
        logger.error("task_reason_failed", error=str(e))
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


async def act_node(state: TaskState) -> dict:
    """ReAct act node: Execute tools based on LLM's tool calls.

    Includes Human-in-the-Loop (HITL) approval for high-risk tools.
    Delegates tool execution to the shared pipeline via execute_tools_batch.

    Args:
        state: Current chat state with tool calls

    Returns:
        Dict with tool results and events
    """
    from app.agents.hitl.tool_risk import requires_approval
    from app.config import settings

    lc_messages = list(state.get("lc_messages", []))
    event_list: list[dict] = []

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

    pending_tool_calls = [
        tc for tc in ai_message.tool_calls
        if tc.get("id", "") not in existing_tool_result_ids
    ]

    if not pending_tool_calls:
        logger.warning(
            "act_node_no_pending_tool_calls",
            existing_count=len(existing_tool_result_ids),
        )
        return {"events": event_list, "lc_messages": lc_messages}

    all_tools = _get_cached_task_tools()
    tool_map = {tool.name: tool for tool in all_tools}
    config = _get_cached_react_config()

    def hitl_check(tool_name: str) -> bool:
        # invoke_skill is always routed through HITL partitioning so per-skill
        # approval checks can run in TaskToolHooks.before_execution.
        return tool_name in {"ask_user", "invoke_skill"} or requires_approval(
            tool_name,
            auto_approve_tools=state.get("auto_approve_tools", []),
            hitl_enabled=state.get("hitl_enabled", True),
            risk_threshold=settings.hitl_default_risk_threshold,
        )

    hooks = TaskToolHooks(state=state)
    tool_messages, batch_events, error_count, pending_interrupt = (
        await execute_tools_batch(
            tool_calls=pending_tool_calls,
            tool_map=tool_map,
            config=config,
            hooks=hooks,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            hitl_partition=True,
            hitl_check=hitl_check,
        )
    )

    event_list.extend(batch_events)
    lc_messages.extend(tool_messages)

    result = {
        "lc_messages": lc_messages,
        "events": event_list,
        "tool_iterations": state.get("tool_iterations", 0) + (1 if tool_messages else 0),
    }

    if pending_interrupt:
        # Don't increment tool_iterations — the tool hasn't executed yet.
        result["pending_interrupt"] = pending_interrupt
        result["tool_iterations"] = state.get("tool_iterations", 0)

    # --- Planned execution mode ---

    # 1. Check if task_planning skill just returned a plan → parse into state
    if not state.get("execution_plan"):
        parsed_plan = _extract_task_plan_from_messages(tool_messages)
        if parsed_plan:
            result["execution_plan"] = parsed_plan
            result["current_step_index"] = 0
            logger.info(
                "execution_plan_parsed",
                step_count=len(parsed_plan),
            )
            # Emit plan_step event for the first step
            first_step = parsed_plan[0]
            event_list.append(events.plan_step(
                step_number=first_step.get("step_number", 1),
                total_steps=len(parsed_plan),
                action=first_step.get("action", ""),
                status="running",
            ))

    # 2. If already in planned execution, advance step and emit progress events
    elif state.get("execution_plan") and tool_messages and not pending_interrupt:
        execution_plan = state["execution_plan"]
        current_idx = state.get("current_step_index", 0)

        if current_idx < len(execution_plan):
            # Mark current step completed
            completed_step = execution_plan[current_idx]
            event_list.append(events.plan_step(
                step_number=completed_step.get("step_number", current_idx + 1),
                total_steps=len(execution_plan),
                action=completed_step.get("action", ""),
                status="completed",
            ))

            # Advance to next step
            next_idx = current_idx + 1
            result["current_step_index"] = next_idx

            if next_idx < len(execution_plan):
                # Emit running event for next step
                next_step = execution_plan[next_idx]
                event_list.append(events.plan_step(
                    step_number=next_step.get("step_number", next_idx + 1),
                    total_steps=len(execution_plan),
                    action=next_step.get("action", ""),
                    status="running",
                ))
                logger.info(
                    "planned_execution_step_advanced",
                    completed_step=current_idx + 1,
                    next_step=next_idx + 1,
                    total_steps=len(execution_plan),
                )
            else:
                logger.info(
                    "planned_execution_plan_completed",
                    total_steps=len(execution_plan),
                )

    return result


async def finalize_node(state: TaskState) -> dict:
    """Extract final response from messages and prepare output.

    Args:
        state: Current chat state

    Returns:
        Dict with final response and events (only new events; state.events uses operator.add)
    """
    lc_messages = state.get("lc_messages", [])

    # Extract final response from last AI message (prefer one without tool_calls)
    response = ""
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            response = extract_text_from_content(msg.content)
            break

    # Fallback: if every AIMessage had tool_calls (e.g., loop hit max_iterations),
    # extract text from the last AIMessage even though it has tool_calls
    if not response:
        for msg in reversed(lc_messages):
            if isinstance(msg, AIMessage):
                text = extract_text_from_content(msg.content)
                if text:
                    response = text
                    break

    # Last resort: generate a generic message so the user isn't left with silence
    if not response:
        response = "I was unable to complete the task within the allowed number of steps. Please try rephrasing your request or breaking it into smaller parts."

    # Emit only the new stage event; state.events uses operator.add so we must not return full list
    final_event = events.stage("task", "Response generated", "completed")

    return {
        "response": response,
        "events": [final_event],
    }


def should_continue(state: TaskState) -> Literal["act", "finalize"]:
    """Decide whether to continue ReAct loop or finalize.

    Args:
        state: Current chat state

    Returns:
        "act" if tools were called, "finalize" otherwise
    """
    # If there was an error, stop immediately
    if state.get("has_error"):
        logger.info("task_stopping_due_to_error")
        return "finalize"

    # If response is already set (from error handling), stop
    if state.get("response"):
        return "finalize"

    lc_messages = state.get("lc_messages", [])

    # Log plan progress if in planned execution mode
    execution_plan = state.get("execution_plan", [])
    if execution_plan:
        current_idx = state.get("current_step_index", 0)
        total = len(execution_plan)
        logger.info(
            "planned_execution_progress",
            current_step=current_idx + 1,
            total_steps=total,
            completed=current_idx >= total,
        )

    # Check if last message has tool calls
    for msg in reversed(lc_messages):
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                # Check iteration limit
                config = _get_cached_react_config()
                iters = state.get("tool_iterations", 0)
                if iters >= config.max_iterations:
                    logger.warning(
                        "task_max_iterations_reached",
                        iterations=iters,
                    )
                    return "finalize"
                return "act"
            else:
                # No tool calls, we're done
                return "finalize"

    return "finalize"


def should_wait_or_reason(state: TaskState) -> Literal["wait_interrupt", "reason"]:
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


async def wait_interrupt_node(state: TaskState) -> dict:
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
    logger.debug(
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

    # Get tools for potential execution (needed for approval flow) - cached
    all_tools = _get_cached_task_tools()
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
            tool_args = dict(pending.get("tool_args", {}) or {})
            user_id = state.get("user_id")
            task_id = state.get("task_id")

            if action in ("approve", "approve_always"):
                if action == "approve_always" and tool_name not in auto_approve_tools:
                    auto_approve_tools.append(tool_name)
                    logger.info("hitl_tool_auto_approved", tool_name=tool_name)

                config = _get_cached_react_config()
                ctx = ToolExecutionContext(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tool_call_id=tool_call_id,
                    tool=tool_map.get(tool_name),
                    user_id=user_id,
                    task_id=task_id,
                )
                hooks = TaskToolHooks(state=state, skip_before_execution=True)
                exec_result = await execute_tool(ctx, hooks=hooks, config=config)
                if exec_result.message:
                    result_str = exec_result.message.content
                else:
                    result_str = "Tool execution returned no result."
                event_list.extend(exec_result.events)

                if action == "approve_always":
                    log_prefix = "hitl_tool_auto_approved_and_executed"
                else:
                    log_prefix = "hitl_tool_approved_and_executed"
                logger.info(log_prefix, tool_name=tool_name)

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
                result_str = f"User responded: {value}" if value else "User skipped this question."
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
        event_list.append(events.tool_result(tool_name, result_str, tool_id=tool_call_id))

        # Debug: Log after adding tool result
        logger.debug(
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


def create_task_graph() -> StateGraph:
    """Create the task subagent graph with explicit ReAct pattern.

    Graph structure:
    [reason] -> [act?] -> [wait_interrupt?] -> [reason] -> ... -> END

    The ReAct loop:
    1. reason: LLM reasons and may call tools
    2. act: Execute tools if called (may set pending_interrupt for ask_user)
    3. wait_interrupt: If pending_interrupt, wait for user response
    4. Loop back to reason with tool results
    5. End when no more tool calls

    Returns:
        Compiled task graph
    """
    graph = StateGraph(TaskState)

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
task_subgraph = create_task_graph()
