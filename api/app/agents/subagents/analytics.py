"""Data analytics subagent using E2B sandbox for code execution."""

import base64
import os
import re
from typing import Any

from e2b import AsyncSandbox
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
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
from app.agents.tools import web_search
from app.agents.tools.react_utils import build_ai_message_from_chunks
from app.agents.tools.search_gate import should_enable_web_search
from app.config import settings
from app.core.logging import get_logger
from app.db.base import async_session_maker
from app.db.models import File as FileModel
from app.services.file_storage import file_storage_service
from app.services.llm import llm_service
from app.models.schemas import LLMProvider

logger = get_logger(__name__)

WEB_TOOLS = [web_search]
MAX_TOOL_ITERATIONS = 3


async def plan_analysis_node(state: DataAnalysisState) -> dict:
    """Plan the data analysis approach.

    Args:
        state: Current data analysis state

    Returns:
        Dict with analysis plan and events
    """
    query = state.get("query") or ""
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")

    events = []

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
                    events.append({
                        "type": "stage",
                        "name": "plan",
                        "description": f"Found {len(attachments_info)} attachments for analysis",
                        "status": "running",
                    })
        except Exception as e:
            logger.error("failed_to_fetch_attachments", error=str(e))

    attachments_context = "\n".join(attachments_info) if attachments_info else "No files attached."

    try:
        # Determine analysis type and approach
        planning_prompt = get_planning_prompt(query, attachments_context)
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)
        messages = [SystemMessage(content=PLANNING_SYSTEM_PROMPT)]
        _append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=planning_prompt))
        history = state.get("messages", [])

        if should_enable_web_search(query, history):
            llm_with_tools = llm.bind_tools(WEB_TOOLS)
            tool_iterations = 0
            while tool_iterations < MAX_TOOL_ITERATIONS:
                response_chunks = []
                async for chunk in llm_with_tools.astream(messages):
                    response_chunks.append(chunk)

                tool_response = build_ai_message_from_chunks(response_chunks, query)
                if not tool_response.tool_calls:
                    break

                messages.append(tool_response)
                tool_iterations += 1
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                    if not tool_name:
                        continue
                    events.append(
                        {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_call.get("args") or {},
                        }
                    )

                tool_results = await ToolNode(WEB_TOOLS).ainvoke({"messages": [tool_response]})
                for msg in tool_results.get("messages", []):
                    messages.append(msg)
                    if isinstance(msg, ToolMessage):
                        events.append(
                            {
                                "type": "tool_result",
                                "tool": msg.name,
                                "content": msg.content[:500] if len(msg.content) > 500 else msg.content,
                            }
                        )

            if tool_iterations >= MAX_TOOL_ITERATIONS:
                events.append(
                    {
                        "type": "stage",
                        "name": "tool",
                        "description": "Tool limit reached; continuing without more tool calls.",
                        "status": "completed",
                    }
                )

        # Stream the planning response
        plan_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    plan_chunks.append(content)
                    events.append({"type": "token", "content": content})

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

        events.append(
            {
                "type": "stage",
                "name": "plan",
                "description": f"Analysis type: {analysis_type}",
                "status": "completed",
            }
        )

        logger.info("analysis_planned", query=query[:50], analysis_type=analysis_type)

        return {
            "analysis_type": analysis_type,
            "analysis_plan": plan,
            "events": events,
        }

    except Exception as e:
        logger.error("analysis_planning_failed", error=str(e))
        events.append(
            {
                "type": "error",
                "name": "plan",
                "description": f"Planning error: {str(e)}",
                "error": str(e),
                "status": "failed",
            }
        )
        return {
            "analysis_type": "general",
            "events": events,
        }


async def generate_code_node(state: DataAnalysisState) -> dict:
    """Generate Python code for data analysis.

    Args:
        state: Current data analysis state

    Returns:
        Dict with generated code and events
    """
    query = state.get("query") or ""
    data_source = state.get("data_source", "")
    analysis_type = state.get("analysis_type", "general")
    analysis_plan = state.get("analysis_plan", "")
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")

    events = []

    # Build data context
    data_context = ""
    if data_source:
        data_context = f"\nData context:\n{data_source[:2000]}"

    # Build file context
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
                file_info = [f"File: '{f.original_filename}'" for f in files]
        except Exception as e:
            logger.error("failed_to_fetch_file_info", error=str(e))

    file_context = "\n".join(file_info) if file_info else "No additional data files."

    try:
        code_generation_prompt = get_code_generation_prompt(
            query=query,
            analysis_type=analysis_type,
            analysis_plan=analysis_plan,
            data_context=data_context,
            file_context=file_context,
        )
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)
        messages = [SystemMessage(content=DATA_ANALYSIS_SYSTEM_PROMPT)]
        _append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=code_generation_prompt))
        history = state.get("messages", [])

        if should_enable_web_search(query, history):
            llm_with_tools = llm.bind_tools(WEB_TOOLS)
            tool_iterations = 0
            while tool_iterations < MAX_TOOL_ITERATIONS:
                response_chunks = []
                async for chunk in llm_with_tools.astream(messages):
                    response_chunks.append(chunk)

                tool_response = build_ai_message_from_chunks(response_chunks, query)
                if not tool_response.tool_calls:
                    break

                messages.append(tool_response)
                tool_iterations += 1
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                    if not tool_name:
                        continue
                    events.append(
                        {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_call.get("args") or {},
                        }
                    )

                tool_results = await ToolNode(WEB_TOOLS).ainvoke({"messages": [tool_response]})
                for msg in tool_results.get("messages", []):
                    messages.append(msg)
                    if isinstance(msg, ToolMessage):
                        events.append(
                            {
                                "type": "tool_result",
                                "tool": msg.name,
                                "content": msg.content[:500] if len(msg.content) > 500 else msg.content,
                            }
                        )

            if tool_iterations >= MAX_TOOL_ITERATIONS:
                events.append(
                    {
                        "type": "stage",
                        "name": "tool",
                        "description": "Tool limit reached; continuing without more tool calls.",
                        "status": "completed",
                    }
                )

        # Stream the code generation
        response_chunks = []
        async for chunk in llm.astream(messages, config={"tags": ["generate_code"]}):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    response_chunks.append(content)
                    events.append({"type": "token", "content": content})

        response = "".join(response_chunks)

        # Extract code from response
        code = _extract_code(response)

        events.append(
            {
                "type": "stage",
                "name": "generate",
                "description": "Code generated",
                "status": "completed",
            }
        )

        logger.info("analysis_code_generated", analysis_type=analysis_type, code_length=len(code))

        return {
            "response": response,
            "code": code,
            "language": "python",
            "events": events,
        }

    except Exception as e:
        logger.error("code_generation_failed", error=str(e))
        events.append(
            {
                "type": "error",
                "name": "generate",
                "description": f"Error: {str(e)}",
                "error": str(e),
                "status": "failed",
            }
        )
        return {
            "response": f"Error generating code: {str(e)}",
            "events": events,
        }


async def execute_code_node(state: DataAnalysisState) -> dict:
    """Execute the generated code in E2B sandbox.

    Args:
        state: Current data analysis state with code to execute

    Returns:
        Dict with execution results and events
    """
    code = state.get("code", "")
    attachment_ids = state.get("attachment_ids", [])
    user_id = state.get("user_id")

    if not code:
        return {
            "execution_result": "No code to execute",
            "events": [
                {
                    "type": "code_result",
                    "output": "No code to execute",
                    "error": None,
                }
            ],
        }

    events = []

    # Check for E2B API key
    if not settings.e2b_api_key:
        logger.warning("e2b_api_key_not_configured")
        events.append(
            {
                "type": "code_result",
                "output": "[E2B API key not configured. Please set E2B_API_KEY in environment.]",
                "error": "E2B API key not configured",
            }
        )
        return {
            "execution_result": "E2B API key not configured",
            "events": events,
        }

    sandbox = None
    try:
        # Create E2B sandbox with data analysis template
        sandbox = await AsyncSandbox.create(
            api_key=settings.e2b_api_key,
            timeout=300,  # 5 minute timeout
        )

        logger.info("e2b_sandbox_created", sandbox_id=sandbox.sandbox_id)

        # Upload attachments to sandbox
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
                        events.append({
                            "type": "stage",
                            "name": "execute",
                            "description": f"Uploading {f.original_filename} to sandbox...",
                            "status": "running",
                        })
                        safe_name = _safe_filename(f.id, f.original_filename)
                        # Download from storage and write to sandbox
                        file_data = await file_storage_service.download_file(f.storage_key)
                        await sandbox.files.write(safe_name, file_data.getvalue())
                        logger.info("file_uploaded_to_sandbox", filename=safe_name)
            except Exception as e:
                logger.error("failed_to_upload_attachments_to_sandbox", error=str(e))
                events.append({
                    "type": "error",
                    "name": "execute",
                    "description": f"Failed to upload files: {str(e)}",
                    "error": str(e),
                    "status": "failed",
                })
                # Continue execution but log the error

        # Install required packages
        install_cmd = "pip install -q pandas numpy matplotlib seaborn plotly scipy scikit-learn openpyxl xlrd"
        await sandbox.commands.run(install_cmd, timeout=120)

        # Execute the analysis code
        # Write code to a file first to avoid shell quoting issues
        script_path = "/tmp/analysis.py"
        await sandbox.files.write(script_path, code)
        
        execution = await sandbox.commands.run(
            f"python3 {script_path}",
            timeout=180,
        )

        stdout = execution.stdout or ""
        stderr = execution.stderr or ""

        # Check for output files
        visualization_data = None
        visualization_type = None

        try:
            # Try to read PNG output
            png_content = await sandbox.files.read("/tmp/output.png")
            if png_content:
                visualization_data = base64.b64encode(png_content).decode("utf-8")
                visualization_type = "image/png"
                logger.info("visualization_captured", type="png")
        except Exception:
            pass

        if not visualization_data:
            try:
                # Try to read HTML output (for plotly)
                html_content = await sandbox.files.read("/tmp/output.html")
                if html_content:
                    visualization_data = html_content.decode("utf-8") if isinstance(html_content, bytes) else html_content
                    visualization_type = "text/html"
                    logger.info("visualization_captured", type="html")
            except Exception:
                pass

        # Build result
        result_parts = []
        if stdout:
            result_parts.append(f"Output:\n{stdout}")
        if stderr and execution.exit_code != 0:
            result_parts.append(f"Errors:\n{stderr}")

        execution_result = "\n\n".join(result_parts) if result_parts else "Code executed successfully (no output)"

        # Add visualization event if we have one
        if visualization_data:
            events.append(
                {
                    "type": "visualization",
                    "data": visualization_data,
                    "mime_type": visualization_type,
                }
            )

        events.append(
            {
                "type": "code_result",
                "output": execution_result,
                "exit_code": execution.exit_code,
                "error": stderr if execution.exit_code != 0 else None,
            }
        )

        events.append(
            {
                "type": "stage",
                "name": "execute",
                "description": "Execution complete",
                "status": "completed",
            }
        )

        logger.info(
            "code_execution_completed",
            exit_code=execution.exit_code,
            has_visualization=visualization_data is not None,
        )

        return {
            "execution_result": execution_result,
            "stdout": stdout,
            "stderr": stderr,
            "visualization": visualization_data,
            "visualization_type": visualization_type,
            "sandbox_id": sandbox.sandbox_id,
            "events": events,
        }

    except Exception as e:
        logger.error("code_execution_failed", error=str(e))
        events.append(
            {
                "type": "code_result",
                "output": f"Execution error: {str(e)}",
                "error": str(e),
            }
        )
        events.append(
            {
                "type": "error",
                "name": "execute",
                "description": f"Execution failed: {str(e)}",
                "error": str(e),
                "status": "failed",
            }
        )
        return {
            "execution_result": f"Execution error: {str(e)}",
            "events": events,
        }

    finally:
        # Clean up sandbox
        if sandbox:
            try:
                await sandbox.kill()
            except Exception as e:
                logger.warning("sandbox_cleanup_failed", error=str(e))


async def summarize_results_node(state: DataAnalysisState) -> dict:
    """Summarize the analysis results for the user.

    Args:
        state: Current data analysis state with execution results

    Returns:
        Dict with summary response and events
    """
    query = state.get("query") or ""
    execution_result = state.get("execution_result", "")
    code = state.get("code", "")
    analysis_type = state.get("analysis_type", "general")
    has_visualization = state.get("visualization") is not None

    events = []

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    model = state.get("model")
    llm = llm_service.get_llm(provider=provider, model=model)

    try:
        summary_prompt = get_summary_prompt(
            query=query,
            analysis_type=analysis_type,
            code=code[:1500],
            execution_result=execution_result[:2000],
            has_visualization=has_visualization,
        )

        # Stream the summary
        response_chunks = []
        messages = [SystemMessage(content=SUMMARY_SYSTEM_PROMPT)]
        _append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=summary_prompt))
        async for chunk in llm.astream(messages, config={"tags": ["summarize"]}):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    response_chunks.append(content)
                    events.append({"type": "token", "content": content})

        summary = "".join(response_chunks)

        events.append(
            {
                "type": "stage",
                "name": "summarize",
                "description": "Summary complete",
                "status": "completed",
            }
        )

        logger.info("analysis_summarized")

        return {
            "response": summary,
            "events": events,
        }

    except Exception as e:
        logger.error("summarization_failed", error=str(e))
        # Fall back to raw results
        return {
            "response": f"Analysis Results:\n\n{execution_result}",
            "events": events,
        }


def should_execute(state: DataAnalysisState) -> str:
    """Determine whether to execute the generated code.

    Args:
        state: Current data analysis state

    Returns:
        Next node name: "execute" or "summarize"
    """
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


def _append_history(messages: list[BaseMessage], history: list[dict]) -> None:
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))


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
