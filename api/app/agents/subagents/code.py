"""Code execution subagent using E2B sandbox with handoff support."""

import json
import re
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph

from app.agents.prompts import CODE_SYSTEM_PROMPT
from app.agents.state import CodeState
from app.agents.tools import (
    web_search,
    generate_image,
    analyze_image,
    get_handoff_tools_for_agent,
)
from app.agents.tools.code_execution import execute_code_with_context
from app.agents.tools.react_tool import build_ai_message_from_chunks
from app.agents.tools.search_gate import should_enable_tools
from app.agents.utils import (
    append_history,
    extract_and_add_image_events,
    create_stage_event,
    create_error_event,
    create_tool_call_event,
    create_tool_result_event,
)
from app.agents import events
from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import llm_service, extract_text_from_content

logger = get_logger(__name__)

CODING_TOOLS = [web_search, generate_image, analyze_image]
MAX_TOOL_ITERATIONS = 3


async def generate_code_node(state: CodeState) -> dict:
    """Generate code based on user query.

    Args:
        state: Current code state with query

    Returns:
        Dict with generated code, events, and potential handoff
    """
    query = state.get("query") or ""

    event_list = [create_stage_event("generate", "Generating code...", "running")]

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.get_llm_for_task("code", provider=provider, tier_override=tier, model_override=model)
    messages = [SystemMessage(content=CODE_SYSTEM_PROMPT)]
    append_history(messages, state.get("messages", []))
    messages.append(HumanMessage(content=query))
    history = state.get("messages", [])

    # Get handoff tools for code agent
    handoff_tools = get_handoff_tools_for_agent("code")

    try:
        if should_enable_tools(query, history):
            all_tools = CODING_TOOLS + handoff_tools
            llm_with_tools = llm.bind_tools(all_tools)
            tool_iterations = 0
            pending_handoff = None

            while tool_iterations < MAX_TOOL_ITERATIONS:
                response_chunks = []
                async for chunk in llm_with_tools.astream(messages):
                    response_chunks.append(chunk)

                tool_response = build_ai_message_from_chunks(response_chunks, query)
                if not tool_response.tool_calls:
                    break

                # Check for handoff
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or ""
                    if tool_name.startswith("handoff_to_"):
                        target_agent = tool_name.replace("handoff_to_", "")
                        task_description = tool_call.get("args", {}).get("task_description", "")
                        context = tool_call.get("args", {}).get("context", "")

                        pending_handoff = {
                            "source_agent": "code",
                            "target_agent": target_agent,
                            "task_description": task_description,
                            "context": context,
                        }

                        event_list.append(events.handoff(
                            source="code",
                            target=target_agent,
                            task=task_description,
                        ))

                        logger.info("code_handoff_detected", target=target_agent)
                        break

                if pending_handoff:
                    return {
                        "response": "",
                        "events": event_list,
                        "pending_handoff": pending_handoff,
                    }

                messages.append(tool_response)
                tool_iterations += 1
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                    if not tool_name:
                        continue
                    event_list.append(create_tool_call_event(tool_name, tool_call.get("args") or {}))

                tool_results = await ToolNode(all_tools).ainvoke({"messages": [tool_response]})
                for msg in tool_results.get("messages", []):
                    messages.append(msg)
                    if isinstance(msg, ToolMessage):
                        if msg.name == "generate_image":
                            extract_and_add_image_events(msg.content, event_list)
                        event_list.append(create_tool_result_event(msg.name, msg.content))

            if tool_iterations >= MAX_TOOL_ITERATIONS:
                event_list.append(create_stage_event(
                    "tool",
                    "Tool limit reached; continuing without more tool calls.",
                    "completed",
                ))

        # Stream the response
        response_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    response_chunks.append(content)
                    event_list.append(events.token(content))

        response = "".join(response_chunks)

        # Extract code blocks from response
        code = _extract_code(response)
        language = _detect_language(response)

        event_list.append(create_stage_event("generate", "Code generated", "completed"))

        logger.info(
            "code_generated",
            query=query[:50],
            language=language,
            code_length=len(code),
        )

        return {
            "response": response,
            "code": code,
            "language": language,
            "events": event_list,
        }

    except Exception as e:
        logger.error("code_generation_failed", error=str(e))
        event_list.append(create_error_event("generate", str(e)))
        return {
            "response": f"I apologize, but I encountered an error generating code: {str(e)}",
            "events": event_list,
        }


async def execute_code_node(state: CodeState) -> dict:
    """Execute generated code in E2B sandbox.

    Args:
        state: Current code state with code to execute

    Returns:
        Dict with execution results and events
    """
    code = state.get("code", "")
    language = state.get("language", "python")

    if not code:
        return {
            "execution_result": "No code to execute",
            "events": [events.code_result("No code to execute")],
        }

    event_list = [create_stage_event("execute", f"Executing {language} code...", "running")]

    # Check for E2B API key
    if not settings.e2b_api_key:
        logger.warning("e2b_api_key_not_configured")
        error_msg = "[E2B API key not configured. Please set E2B_API_KEY in environment.]"
        event_list.append(events.code_result(error_msg, error="E2B API key not configured"))
        event_list.append(create_error_event("execute", "E2B API key not configured"))
        return {"execution_result": "E2B API key not configured", "events": event_list}

    try:
        # Use the execute_code tool with session context
        exec_result = await execute_code_with_context(
            code=code,
            language=language,
            capture_visualizations=True,
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
        )

        result_parts = []
        if exec_result.get("stdout"):
            result_parts.append(f"Output:\n{exec_result['stdout']}")
        if exec_result.get("stderr") and exec_result.get("exit_code") != 0:
            result_parts.append(f"Errors:\n{exec_result['stderr']}")

        execution_result = "\n\n".join(result_parts) if result_parts else "Code executed successfully (no output)"

        event_list.append(events.code_result(
            execution_result,
            exit_code=exec_result.get("exit_code"),
            error_msg=exec_result.get("stderr") if exec_result.get("exit_code") != 0 else None,
        ))

        event_list.append(create_stage_event("execute", "Execution complete", "completed"))

        return {
            "execution_result": execution_result,
            "stdout": exec_result.get("stdout", ""),
            "stderr": exec_result.get("stderr", ""),
            "sandbox_id": exec_result.get("sandbox_id"),
            "events": event_list,
        }

    except Exception as e:
        logger.error("code_execution_failed", error=str(e))
        event_list.append(events.code_result(f"Execution error: {str(e)}", error_msg=str(e)))
        event_list.append(create_error_event("execute", str(e), f"Execution failed: {str(e)}"))
        return {
            "execution_result": f"Execution error: {str(e)}",
            "events": event_list,
        }


async def finalize_node(state: CodeState) -> dict:
    """Combine code generation and execution results into final response.

    Args:
        state: Current code state with code and execution results

    Returns:
        Dict with final response, events, and potential handoff
    """
    response = state.get("response", "")
    execution_result = state.get("execution_result")
    code = state.get("code", "")

    event_list = []

    if execution_result and code:
        if execution_result.startswith("Execution error"):
            response += f"\n\n**Execution Error:**\n```\n{execution_result}\n```"
        elif execution_result != "E2B API key not configured":
            response += f"\n\n**Execution Result:**\n```\n{execution_result}\n```"

        event_list.append(create_stage_event(
            "finalize",
            "Response finalized with execution results",
            "completed",
        ))
    else:
        event_list.append(create_stage_event("finalize", "Response finalized", "completed"))

    logger.info("code_response_finalized", has_execution=bool(execution_result))

    result = {
        "response": response,
        "events": event_list,
    }

    # Propagate handoff if present
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        result["pending_handoff"] = pending_handoff

    return result


def should_execute(state: CodeState) -> str:
    """Determine whether to execute the generated code.

    Args:
        state: Current code state

    Returns:
        Next node name: "execute" or "finalize"
    """
    # Check for pending handoff
    if state.get("pending_handoff"):
        return "finalize"

    query = state.get("query", "").lower()
    code = state.get("code", "")

    if not code:
        return "finalize"

    execution_keywords = ["run", "execute", "test", "run this", "execute this"]
    if any(keyword in query for keyword in execution_keywords):
        return "execute"

    return "finalize"


def _extract_code(response: str) -> str:
    """Extract code from markdown code blocks."""
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        if len(matches) > 1:
            logger.info(
                "multiple_code_blocks_found",
                count=len(matches),
                lengths=[len(m) for m in matches],
            )
            return max(matches, key=len).strip()
        return matches[0].strip()

    return ""


def _detect_language(response: str) -> str:
    """Detect the programming language from code blocks."""
    pattern = r"```(\w+)\n"
    match = re.search(pattern, response)

    if match:
        lang = match.group(1).lower()
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "sh": "bash",
            "shell": "bash",
        }
        return lang_map.get(lang, lang)

    return "python"


def create_code_graph() -> StateGraph:
    """Create the code execution subagent graph.

    Returns:
        Compiled code graph
    """
    graph = StateGraph(CodeState)

    graph.add_node("generate", generate_code_node)
    graph.add_node("execute", execute_code_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("generate")

    graph.add_conditional_edges(
        "generate",
        should_execute,
        {
            "execute": "execute",
            "finalize": "finalize",
        },
    )

    graph.add_edge("execute", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


code_subgraph = create_code_graph()
