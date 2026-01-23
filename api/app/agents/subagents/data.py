"""Data analysis subagent using E2B sandbox for code execution with handoff support."""

import base64
import os
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.agents.prompts import (
    DATA_ANALYSIS_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    get_code_generation_prompt,
    get_planning_prompt,
    get_summary_prompt,
)
from app.agents.state import DataAnalysisState
from app.agents.tools import (
    get_tools_for_agent,
    execute_react_loop,
    get_react_config,
)
from app.agents.tools.code_execution import execute_code_with_context
from app.sandbox import sandbox_file_with_context
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
from app.db.base import async_session_maker
from app.db.models import File as FileModel
from app.services.file_storage import file_storage_service
from app.ai.llm import llm_service, extract_text_from_content
from app.ai.model_tiers import ModelTier
from app.models.schemas import LLMProvider

logger = get_logger(__name__)


async def plan_analysis_node(state: DataAnalysisState) -> dict:
    """Plan the data analysis approach using the canonical ReAct loop.

    Args:
        state: Current data analysis state

    Returns:
        Dict with analysis plan, events, and potential handoff
    """
    query = state.get("query") or ""
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")
    task_id = state.get("task_id")

    event_list = []

    # Fetch attachment info if provided
    attachments_info = []
    if attachment_ids and user_id:
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(FileModel).where(
                        FileModel.id.in_(attachment_ids),
                        FileModel.user_id == user_id
                    )
                )
                files = result.scalars().all()
                attachments_info = [
                    f"- {f.original_filename} ({f.content_type}, {f.file_size} bytes)"
                    for f in files
                ]
                if attachments_info:
                    event_list.append(create_stage_event(
                        "plan",
                        f"Found {len(attachments_info)} attachments for analysis",
                        "running",
                    ))
        except Exception as e:
            logger.error("failed_to_fetch_attachments", error=str(e))

    attachments_context = "\n".join(attachments_info) if attachments_info else "No files attached."

    # Get agent-specific ReAct configuration
    config = get_react_config("data")

    try:
        # Determine analysis type and approach
        planning_prompt = get_planning_prompt(query, attachments_context)
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)
        messages = [SystemMessage(content=PLANNING_SYSTEM_PROMPT)]
        append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=planning_prompt))

        # Always enable tools - let the LLM decide when to use them
        enable_tools = True

        # Get all tools for data agent (code_exec, data, handoffs)
        all_tools = get_tools_for_agent("data", include_handoffs=True)

        if enable_tools and all_tools:
            llm_with_tools = llm.bind_tools(all_tools)

            # Execute the canonical ReAct loop (StreamProcessor handles events)
            extra_tool_args = {
                "user_id": user_id,
                "task_id": task_id,
            }
            result = await execute_react_loop(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=all_tools,
                query=query,
                config=config,
                source_agent="data",
                extra_tool_args=extra_tool_args,
            )

            # Add events from the ReAct loop
            event_list.extend(result.events)
            messages = result.messages

            # Check for pending handoff
            if result.pending_handoff:
                logger.info("data_handoff_detected", target=result.pending_handoff.get("target_agent"))
                return {
                    "analysis_type": "general",
                    "events": event_list,
                    "pending_handoff": result.pending_handoff,
                }

        # Get the planning response (don't stream tokens to message content)
        plan_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    plan_chunks.append(content)

        plan = "".join(plan_chunks)

        # Detect analysis type
        analysis_type = "general"
        query_lower = query.lower()
        if any(word in query_lower for word in ["plot", "chart", "graph", "visualiz", "show"]):
            analysis_type = "visualization"
        elif any(word in query_lower for word in ["statistic", "mean", "median", "correlation", "regression"]):
            analysis_type = "statistics"
        elif any(word in query_lower for word in ["clean", "transform", "parse", "convert", "filter"]):
            analysis_type = "processing"
        elif any(word in query_lower for word in ["predict", "classify", "cluster", "train", "model"]):
            analysis_type = "ml"

        # Truncate plan for display in stage details (keep first ~200 chars)
        plan_preview = plan[:200].strip()
        if len(plan) > 200:
            plan_preview += "..."

        event_list.append(create_stage_event(
            "plan",
            f"Analysis type: {analysis_type}" + (f" - {plan_preview}" if plan_preview else ""),
            "completed",
        ))

        logger.info("analysis_planned", query=query[:50], analysis_type=analysis_type)

        return {
            "analysis_type": analysis_type,
            "analysis_plan": plan,
            "events": event_list,
        }

    except Exception as e:
        logger.error("analysis_planning_failed", error=str(e))
        event_list.append(create_error_event("plan", str(e), f"Planning error: {str(e)}"))
        return {
            "analysis_type": "general",
            "events": event_list,
        }


async def generate_code_node(state: DataAnalysisState) -> dict:
    """Generate Python code for data analysis using the canonical ReAct loop.

    Args:
        state: Current data analysis state

    Returns:
        Dict with generated code, events, and potential handoff
    """
    # Check for pending handoff
    if state.get("pending_handoff"):
        return {"code": "", "events": [], "pending_handoff": state.get("pending_handoff")}

    query = state.get("query") or ""
    data_source = state.get("data_source", "")
    analysis_type = state.get("analysis_type", "general")
    analysis_plan = state.get("analysis_plan", "")
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")
    task_id = state.get("task_id")

    event_list = []

    # Build data context
    data_context = ""
    if data_source:
        data_context = f"\nData context:\n{data_source[:2000]}"

    # Build file context with sandbox paths
    # Files are uploaded to sandbox with safe names: {file_id}_{original_filename}
    file_info = []
    if attachment_ids and user_id:
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(FileModel).where(
                        FileModel.id.in_(attachment_ids),
                        FileModel.user_id == user_id
                    )
                )
                files = result.scalars().all()
                for f in files:
                    safe_name = _safe_filename(f.id, f.original_filename)
                    file_info.append(f"File: '/home/user/{safe_name}' (original: {f.original_filename})")
        except Exception as e:
            logger.error("failed_to_fetch_file_info", error=str(e))

    file_context = "\n".join(file_info) if file_info else "No additional data files."

    # Get agent-specific ReAct configuration
    config = get_react_config("data")

    try:
        # Log file context for debugging
        logger.info("code_generation_context", file_context=file_context, analysis_type=analysis_type)

        code_generation_prompt = get_code_generation_prompt(
            query=query,
            analysis_type=analysis_type,
            analysis_plan=analysis_plan,
            data_context=data_context,
            file_context=file_context,
        )
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        # Use MAX tier for code generation to ensure high-quality, correct code
        llm = llm_service.get_llm_for_tier(ModelTier.MAX, provider=provider, model_override=model)
        messages = [SystemMessage(content=DATA_ANALYSIS_SYSTEM_PROMPT)]
        append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=code_generation_prompt))

        # Always enable tools - let the LLM decide when to use them
        enable_tools = True

        # Get all tools for data agent (code_exec, data, handoffs)
        all_tools = get_tools_for_agent("data", include_handoffs=True)

        if enable_tools and all_tools:
            llm_with_tools = llm.bind_tools(all_tools)

            # Execute the canonical ReAct loop (StreamProcessor handles events)
            extra_tool_args = {
                "user_id": user_id,
                "task_id": task_id,
            }
            result = await execute_react_loop(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=all_tools,
                query=query,
                config=config,
                source_agent="data",
                extra_tool_args=extra_tool_args,
            )

            # Add events from the ReAct loop
            event_list.extend(result.events)
            messages = result.messages

            # Check for pending handoff
            if result.pending_handoff:
                logger.info("data_handoff_detected", target=result.pending_handoff.get("target_agent"))
                return {
                    "code": "",
                    "events": event_list,
                    "pending_handoff": result.pending_handoff,
                }

        # Stream the code generation
        response_chunks = []
        async for chunk in llm.astream(messages, config={"tags": ["generate_code"]}):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    response_chunks.append(content)
                    event_list.append(events.token(content))

        response = "".join(response_chunks)

        # Extract code from response
        code = _extract_code(response)

        # Log the extracted code for debugging
        logger.info("analysis_code_extracted", code_preview=code[:500] if code else "NO CODE EXTRACTED")

        event_list.append(create_stage_event("generate", "Code generated", "completed"))

        logger.info("analysis_code_generated", analysis_type=analysis_type, code_length=len(code))

        return {
            "response": response,
            "code": code,
            "language": "python",
            "events": event_list,
        }

    except Exception as e:
        logger.error("code_generation_failed", error=str(e))
        event_list.append(create_error_event("generate", str(e)))
        return {
            "response": f"Error generating code: {str(e)}",
            "events": event_list,
        }


async def execute_code_node(state: DataAnalysisState) -> dict:
    """Execute the generated code in E2B sandbox.

    Args:
        state: Current data analysis state with code to execute

    Returns:
        Dict with execution results, images, and events
    """
    # Check for pending handoff
    if state.get("pending_handoff"):
        return {
            "execution_result": "",
            "images": [],
            "events": [],
            "pending_handoff": state.get("pending_handoff"),
        }

    code = state.get("code", "")
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")
    task_id = state.get("task_id")

    if not code:
        return {
            "execution_result": "No code to execute",
            "events": [events.code_result("No code to execute")],
        }

    event_list = []

    # Check for E2B API key
    if not settings.e2b_api_key:
        logger.warning("e2b_api_key_not_configured")
        error_msg = "[E2B API key not configured. Please set E2B_API_KEY in environment.]"
        event_list.append(events.code_result(error_msg, error_msg="E2B API key not configured"))
        return {"execution_result": "E2B API key not configured", "events": event_list}

    try:
        # Upload attachments to sandbox if provided using sandbox_file tool
        if attachment_ids and user_id:
            try:
                async with async_session_maker() as session:
                    result = await session.execute(
                        select(FileModel).where(
                            FileModel.id.in_(attachment_ids),
                            FileModel.user_id == user_id
                        )
                    )
                    files = result.scalars().all()

                    if not files:
                        error_msg = "No files found for the provided attachment IDs"
                        logger.error("no_files_found_for_attachments", attachment_ids=attachment_ids)
                        event_list.append(create_error_event("execute", error_msg))
                        return {"execution_result": error_msg, "events": event_list}

                    for f in files:
                        event_list.append(create_stage_event(
                            "execute",
                            f"Uploading {f.original_filename} to sandbox...",
                            "running",
                        ))
                        safe_name = _safe_filename(f.id, f.original_filename)
                        file_data = await file_storage_service.download_file(f.storage_key)

                        # Get bytes from BytesIO if needed
                        file_bytes = file_data.getvalue() if hasattr(file_data, 'getvalue') else file_data

                        # Use sandbox_file tool to write file to sandbox
                        write_result = await sandbox_file_with_context(
                            operation="write",
                            path=f"/home/user/{safe_name}",
                            content=base64.b64encode(file_bytes).decode("utf-8"),
                            is_binary=True,
                            user_id=user_id,
                            task_id=task_id,
                        )

                        if not write_result.get("success"):
                            error_msg = f"Failed to upload {f.original_filename}: {write_result.get('error')}"
                            logger.error("file_upload_failed", filename=f.original_filename, error=write_result.get("error"))
                            event_list.append(create_error_event("execute", error_msg))
                            # Continue with other files

            except Exception as e:
                error_msg = f"Failed to upload files to sandbox: {str(e)}"
                logger.error("failed_to_upload_attachments_to_sandbox", error=str(e))
                event_list.append(create_error_event("execute", str(e), error_msg))
                return {"execution_result": error_msg, "events": event_list}

        # Install required packages and execute code using execute_code tool
        packages = ["pandas", "numpy", "matplotlib", "seaborn", "plotly",
                   "scipy", "scikit-learn", "openpyxl", "xlrd"]

        event_list.append(create_stage_event(
            "execute",
            "Executing analysis code...",
            "running",
        ))

        exec_result = await execute_code_with_context(
            code=code,
            language="python",
            packages=packages,
            capture_images=True,
            user_id=user_id,
            task_id=task_id,
        )

        # Get images from result
        images = exec_result.get("images", [])

        # Build result
        result_parts = []
        if exec_result.get("stdout"):
            result_parts.append(f"Output:\n{exec_result['stdout']}")
        if exec_result.get("stderr") and exec_result.get("exit_code") != 0:
            result_parts.append(f"Errors:\n{exec_result['stderr']}")

        execution_result = "\n\n".join(result_parts) if result_parts else "Code executed successfully (no output)"

        # Add image events for charts/images (only if data is non-empty)
        for img in images:
            img_data = img.get("data", "")
            if img_data:  # Only emit image event if data is present
                event_list.append(events.image(
                    data=img_data,
                    mime_type=img.get("type", "image/png"),
                ))
                logger.info("image_event_created", mime_type=img.get("type", "image/png"), data_length=len(img_data))
            else:
                logger.warning("image_skipped_empty_data", path=img.get("path", "unknown"))

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
            "images": images,
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


async def summarize_results_node(state: DataAnalysisState) -> dict:
    """Summarize the analysis results for the user.

    Args:
        state: Current data analysis state with execution results

    Returns:
        Dict with summary response, events, and potential handoff
    """
    # Check for pending handoff
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        return {
            "response": "",
            "events": [],
            "pending_handoff": pending_handoff,
        }

    query = state.get("query") or ""
    execution_result = state.get("execution_result", "")
    code = state.get("code", "")
    analysis_type = state.get("analysis_type", "general")

    # Check for images (new format) or fallback to old format
    images = state.get("images", [])
    has_visualization = len(images) > 0 or state.get("visualization") is not None
    visualization_count = len(images) if images else (1 if state.get("visualization") else 0)

    event_list = []

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task("data", provider=provider, tier_override=tier, model_override=model)

    try:
        summary_prompt = get_summary_prompt(
            query=query,
            analysis_type=analysis_type,
            code=code[:1500],
            execution_result=execution_result[:2000],
            has_visualization=has_visualization,
            visualization_count=visualization_count,
        )

        # Stream the summary
        response_chunks = []
        messages = [SystemMessage(content=SUMMARY_SYSTEM_PROMPT)]
        append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=summary_prompt))
        async for chunk in llm.astream(messages, config={"tags": ["summarize"]}):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    response_chunks.append(content)
                    event_list.append(events.token(content))

        summary = "".join(response_chunks)

        event_list.append(create_stage_event("summarize", "Summary complete", "completed"))

        logger.info("analysis_summarized")

        return {
            "response": summary,
            "events": event_list,
        }

    except Exception as e:
        logger.error("summarization_failed", error=str(e))
        # Fall back to raw results
        return {
            "response": f"Analysis Results:\n\n{execution_result}",
            "events": event_list,
        }


def should_execute(state: DataAnalysisState) -> str:
    """Determine whether to execute the generated code.

    Args:
        state: Current data analysis state

    Returns:
        Next node name: "execute" or "summarize"
    """
    # Skip execution if there's a pending handoff
    if state.get("pending_handoff"):
        return "summarize"

    # Check if we have code to execute
    code = state.get("code", "")
    if not code:
        return "summarize"

    # Check for explicit execution request or data analysis context
    query = state.get("query", "").lower()

    # For data analysis, we typically want to execute
    # Only skip if explicitly asked to just generate code
    if "don't run" in query or "don't execute" in query or "just generate" in query:
        return "summarize"

    return "execute"


def _extract_code(response: str) -> str:
    """Extract Python code from markdown code blocks.

    If multiple code blocks are found, returns the largest one
    (most likely the main code to execute).
    """
    # Find all code blocks with python specifier
    pattern = r"```python\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        # If multiple blocks, prefer the largest one (likely the main code)
        if len(matches) > 1:
            logger.info("multiple_code_blocks_found", count=len(matches), lengths=[len(m) for m in matches])
            return max(matches, key=len).strip()
        return matches[0].strip()

    # Try without language specifier
    pattern = r"```\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        if len(matches) > 1:
            logger.info("multiple_code_blocks_found", count=len(matches), lengths=[len(m) for m in matches])
            return max(matches, key=len).strip()
        return matches[0].strip()

    return ""


def _safe_filename(file_id: str, filename: str) -> str:
    base_name = os.path.basename(filename) or "file"
    return f"{file_id}_{base_name}"


def create_data_graph() -> StateGraph:
    """Create the data analysis subagent graph.

    Graph structure:
    [plan] → [generate] → [should_execute?] → [execute] → [summarize] → [END]
                            ↓ (no code)
                        [summarize] → [END]

    Returns:
        Compiled data analysis graph
    """
    graph = StateGraph(DataAnalysisState)

    # Add nodes
    graph.add_node("plan", plan_analysis_node)
    graph.add_node("generate", generate_code_node)
    graph.add_node("execute", execute_code_node)
    graph.add_node("summarize", summarize_results_node)

    # Set entry point
    graph.set_entry_point("plan")

    # Linear flow: plan → generate
    graph.add_edge("plan", "generate")

    # Conditional: execute or skip to summarize
    graph.add_conditional_edges(
        "generate",
        should_execute,
        {
            "execute": "execute",
            "summarize": "summarize",
        },
    )

    # After execution, summarize
    graph.add_edge("execute", "summarize")

    # End after summary
    graph.add_edge("summarize", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
data_subgraph = create_data_graph()
