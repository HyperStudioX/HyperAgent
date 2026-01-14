"""Data analytics subagent using E2B sandbox for code execution."""

import base64
import re
from typing import Any

from e2b import AsyncSandbox
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import DataAnalysisState
from app.config import settings
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

DATA_ANALYSIS_SYSTEM_PROMPT = """You are a data analysis expert. Your role is to help users analyze data, create visualizations, and derive insights.

When the user provides data or asks for analysis:
1. Understand what they want to achieve
2. Write clean, efficient Python code using appropriate libraries
3. Include clear comments explaining each step
4. Handle errors gracefully

Available libraries in the sandbox:
- pandas: Data manipulation and analysis
- numpy: Numerical computing
- matplotlib: Static visualizations
- seaborn: Statistical visualizations
- plotly: Interactive visualizations
- scipy: Scientific computing and statistics
- scikit-learn: Machine learning

For visualizations:
- Always save plots to '/tmp/output.png' using plt.savefig('/tmp/output.png', dpi=150, bbox_inches='tight')
- Use plt.close() after saving to free memory
- For plotly, save to '/tmp/output.html'

For data output:
- Print results using print() for text output
- Save CSV results to '/tmp/output.csv' if needed

Always wrap your code in a markdown code block with the language specified:
```python
# your analysis code here
```"""

CODE_GENERATION_PROMPT = """Based on the user's request, generate Python code for data analysis.

User request: {query}

{data_context}

Generate complete, executable Python code that:
1. Performs the requested analysis
2. Handles potential errors
3. Outputs results clearly (print statements for text, save files for visualizations)
4. Includes comments explaining key steps

Remember to save any visualizations to '/tmp/output.png' or '/tmp/output.html'."""


async def plan_analysis_node(state: DataAnalysisState) -> dict:
    """Plan the data analysis approach.

    Args:
        state: Current data analysis state

    Returns:
        Dict with analysis plan and events
    """
    query = state.get("query", "")

    events = [
        {
            "type": "step",
            "step_type": "plan",
            "description": "Planning analysis approach...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()

    try:
        # Determine analysis type and approach
        planning_prompt = f"""Analyze this data analysis request and determine:
1. What type of analysis is needed (visualization, statistics, data processing, ML)
2. What data format is expected (CSV, JSON, inline, URL)
3. Key steps to accomplish the task

Request: {query}

Respond in a brief, structured format."""

        response = await llm.ainvoke([
            SystemMessage(content="You are a data analysis planning assistant."),
            HumanMessage(content=planning_prompt),
        ])

        plan = response.content

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
                "type": "step",
                "step_type": "plan",
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
                "type": "step",
                "step_type": "plan",
                "description": f"Planning error: {str(e)}",
                "status": "completed",
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
    query = state.get("query", "")
    data_source = state.get("data_source", "")
    analysis_type = state.get("analysis_type", "general")

    events = [
        {
            "type": "step",
            "step_type": "generate",
            "description": "Generating analysis code...",
            "status": "running",
        }
    ]

    # Build data context
    data_context = ""
    if data_source:
        data_context = f"\nData provided:\n{data_source[:2000]}"  # Limit context size

    llm = llm_service.get_llm()

    try:
        # Stream the code generation
        response_chunks = []
        async for chunk in llm.astream([
            SystemMessage(content=DATA_ANALYSIS_SYSTEM_PROMPT),
            HumanMessage(content=CODE_GENERATION_PROMPT.format(
                query=query,
                data_context=data_context,
            )),
        ]):
            if chunk.content:
                response_chunks.append(chunk.content)
                events.append({"type": "token", "content": chunk.content})

        response = "".join(response_chunks)

        # Extract code from response
        code = _extract_code(response)

        events.append(
            {
                "type": "step",
                "step_type": "generate",
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
                "type": "step",
                "step_type": "generate",
                "description": f"Error: {str(e)}",
                "status": "completed",
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

    events = [
        {
            "type": "step",
            "step_type": "execute",
            "description": "Executing code in sandbox...",
            "status": "running",
        }
    ]

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
        events.append(
            {
                "type": "step",
                "step_type": "execute",
                "description": "Execution skipped - E2B not configured",
                "status": "completed",
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

        # Install required packages
        install_cmd = "pip install -q pandas numpy matplotlib seaborn plotly scipy scikit-learn openpyxl xlrd"
        await sandbox.commands.run(install_cmd, timeout=120)

        # Execute the analysis code
        execution = await sandbox.commands.run(
            f"python3 -c '''{code}'''",
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
                "type": "step",
                "step_type": "execute",
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
                "type": "step",
                "step_type": "execute",
                "description": f"Execution failed: {str(e)}",
                "status": "completed",
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
    query = state.get("query", "")
    execution_result = state.get("execution_result", "")
    code = state.get("code", "")
    has_visualization = state.get("visualization") is not None

    events = [
        {
            "type": "step",
            "step_type": "summarize",
            "description": "Summarizing results...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()

    try:
        summary_prompt = f"""Summarize the data analysis results for the user.

Original request: {query}

Code executed:
```python
{code[:1500]}
```

Execution output:
{execution_result[:2000]}

{"A visualization was generated and will be displayed." if has_visualization else ""}

Provide a clear, concise summary of:
1. What analysis was performed
2. Key findings or results
3. Any insights or recommendations"""

        # Stream the summary
        response_chunks = []
        async for chunk in llm.astream([
            SystemMessage(content="You are a data analysis assistant. Summarize results clearly and concisely."),
            HumanMessage(content=summary_prompt),
        ]):
            if chunk.content:
                response_chunks.append(chunk.content)
                events.append({"type": "token", "content": chunk.content})

        summary = "".join(response_chunks)

        events.append(
            {
                "type": "step",
                "step_type": "summarize",
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
    """Extract Python code from markdown code blocks."""
    # Find code blocks with python specifier
    pattern = r"```python\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

    # Try without language specifier
    pattern = r"```\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        return matches[0].strip()

    return ""


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
