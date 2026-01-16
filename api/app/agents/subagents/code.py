"""Code execution subagent using E2B sandbox."""

from e2b import AsyncSandbox
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph

from app.agents.prompts import CODE_SYSTEM_PROMPT
from app.agents.state import CodeState
from app.agents.tools import web_search
from app.agents.tools.react_utils import build_ai_message_from_chunks
from app.agents.tools.search_gate import should_enable_web_search
from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import llm_service

logger = get_logger(__name__)

WEB_TOOLS = [web_search]
MAX_TOOL_ITERATIONS = 3


async def generate_code_node(state: CodeState) -> dict:
    """Generate code based on user query.

    Args:
        state: Current code state with query

    Returns:
        Dict with generated code and events
    """
    query = state.get("query") or ""

    events = [
        {
            "type": "stage",
            "name": "generate",
            "description": "Generating code...",
            "status": "running",
        }
    ]

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    model = state.get("model")
    llm = llm_service.get_llm(provider=provider, model=model)
    messages = [SystemMessage(content=CODE_SYSTEM_PROMPT)]
    _append_history(messages, state.get("messages", []))
    messages.append(HumanMessage(content=query))
    history = state.get("messages", [])

    try:
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

        # Stream the response
        response_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    response_chunks.append(content)
                    events.append({"type": "token", "content": content})

        response = "".join(response_chunks)

        # Extract code blocks from response
        code = _extract_code(response)
        language = _detect_language(response)

        events.append(
            {
                "type": "stage",
                "name": "generate",
                "description": "Code generated",
                "status": "completed",
            }
        )

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
            "response": f"I apologize, but I encountered an error generating code: {str(e)}",
            "events": events,
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
            "type": "stage",
            "name": "execute",
            "description": f"Executing {language} code...",
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
                "type": "error",
                "name": "execute",
                "description": "Execution skipped - E2B not configured",
                "error": "E2B API key not configured",
                "status": "failed",
            }
        )
        return {
            "execution_result": "E2B API key not configured",
            "events": events,
        }

    sandbox = None
    try:
        # Create E2B sandbox
        sandbox = await AsyncSandbox.create(
            api_key=settings.e2b_api_key,
            timeout=300,  # 5 minute timeout
        )

        logger.info("e2b_sandbox_created", sandbox_id=sandbox.sandbox_id, language=language)

        # Determine execution command based on language
        if language in ("python", "py"):
            await sandbox.files.write("/tmp/script.py", code)
            cmd = "python3 /tmp/script.py"
        elif language in ("javascript", "js"):
            await sandbox.files.write("/tmp/script.js", code)
            cmd = "node /tmp/script.js"
        elif language in ("typescript", "ts"):
            # Write to file and run with ts-node
            await sandbox.files.write("/tmp/script.ts", code)
            install_result = await sandbox.commands.run(
                "npm install -g ts-node typescript 2>/dev/null || true",
                timeout=60,
            )
            if install_result.exit_code != 0:
                logger.warning(
                    "ts_node_install_failed",
                    stderr=install_result.stderr,
                    stdout=install_result.stdout,
                )
            cmd = "ts-node /tmp/script.ts"
        elif language in ("bash", "sh", "shell"):
            await sandbox.files.write("/tmp/script.sh", code)
            await sandbox.commands.run("chmod +x /tmp/script.sh")
            cmd = "/tmp/script.sh"
        else:
            # Default to python
            await sandbox.files.write("/tmp/script.py", code)
            cmd = "python3 /tmp/script.py"

        # Execute the code
        execution = await sandbox.commands.run(cmd, timeout=120)

        stdout = execution.stdout or ""
        stderr = execution.stderr or ""

        # Build result
        result_parts = []
        if stdout:
            result_parts.append(f"Output:\n{stdout}")
        if stderr and execution.exit_code != 0:
            result_parts.append(f"Errors:\n{stderr}")

        execution_result = "\n\n".join(result_parts) if result_parts else "Code executed successfully (no output)"

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
            language=language,
            exit_code=execution.exit_code,
        )

        return {
            "execution_result": execution_result,
            "stdout": stdout,
            "stderr": stderr,
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


async def finalize_node(state: CodeState) -> dict:
    """Combine code generation and execution results into final response.

    Args:
        state: Current code state with code and execution results

    Returns:
        Dict with final response and events
    """
    response = state.get("response", "")
    execution_result = state.get("execution_result")
    code = state.get("code", "")

    events = []

    # If code was executed, append results to response
    if execution_result and code:
        # Format execution results nicely
        if execution_result.startswith("Execution error"):
            # Error case - append as error message
            response += f"\n\n**Execution Error:**\n```\n{execution_result}\n```"
        elif execution_result != "E2B API key not configured":
            # Success case - append as execution result
            response += f"\n\n**Execution Result:**\n```\n{execution_result}\n```"

        events.append(
            {
                "type": "stage",
                "name": "finalize",
                "description": "Response finalized with execution results",
                "status": "completed",
            }
        )
    else:
        events.append(
            {
                "type": "stage",
                "name": "finalize",
                "description": "Response finalized",
                "status": "completed",
            }
        )

    logger.info("code_response_finalized", has_execution=bool(execution_result))

    return {
        "response": response,
        "events": events,
    }


def should_execute(state: CodeState) -> str:
    """Determine whether to execute the generated code.

    Args:
        state: Current code state

    Returns:
        Next node name: "execute" or "finalize"
    """
    query = state.get("query", "").lower()
    code = state.get("code", "")

    # Must have code to execute
    if not code:
        return "finalize"

    # Check for explicit execution keywords
    execution_keywords = ["run", "execute", "test", "run this", "execute this"]
    if any(keyword in query for keyword in execution_keywords):
        return "execute"

    # Default: don't auto-execute, just generate
    return "finalize"


def _extract_code(response: str) -> str:
    """Extract code from markdown code blocks.
    
    If multiple code blocks are found, returns the largest one
    (most likely the main code to execute).
    """
    import re

    # Find all code blocks with language specifier
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
        # If multiple blocks, prefer the largest one (likely the main code)
        if len(matches) > 1:
            logger.info(
                "multiple_code_blocks_found",
                count=len(matches),
                lengths=[len(m) for m in matches],
            )
            # Return the largest block (most likely the main code)
            return max(matches, key=len).strip()
        return matches[0].strip()

    return ""


def _detect_language(response: str) -> str:
    """Detect the programming language from code blocks."""
    import re

    # Look for language specifier in code blocks
    pattern = r"```(\w+)\n"
    match = re.search(pattern, response)

    if match:
        lang = match.group(1).lower()
        # Normalize language names
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "sh": "bash",
            "shell": "bash",
        }
        return lang_map.get(lang, lang)

    return "python"  # Default


def _append_history(messages: list[BaseMessage], history: list[dict]) -> None:
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))


def create_code_graph() -> StateGraph:
    """Create the code execution subagent graph.

    Graph structure:
    [generate] → [should_execute?] → [execute] → [finalize] → [END]
                            ↓ (no)                    ↓
                          [finalize] → [END]

    Returns:
        Compiled code graph
    """
    graph = StateGraph(CodeState)

    # Add nodes
    graph.add_node("generate", generate_code_node)
    graph.add_node("execute", execute_code_node)
    graph.add_node("finalize", finalize_node)

    # Set entry point
    graph.set_entry_point("generate")

    # Conditional edge: execute only if requested
    graph.add_conditional_edges(
        "generate",
        should_execute,
        {
            "execute": "execute",
            "finalize": "finalize",
        },
    )

    # After execution, finalize the response
    graph.add_edge("execute", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
code_subgraph = create_code_graph()
