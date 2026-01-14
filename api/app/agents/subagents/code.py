"""Code execution subagent using E2B sandbox."""

from e2b import AsyncSandbox
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import CodeState
from app.config import settings
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

CODE_SYSTEM_PROMPT = """You are a code assistant that helps users write and execute code.

When the user asks for code:
1. Write clean, well-documented code
2. Include error handling where appropriate
3. Provide explanations for complex logic
4. Use best practices for the language

When generating code to execute, wrap it in a code block with the language specified:
```python
# your code here
```

Supported languages: Python, JavaScript, TypeScript, Shell/Bash

If the user wants to execute code, provide the code and indicate it should be run."""


async def generate_code_node(state: CodeState) -> dict:
    """Generate code based on user query.

    Args:
        state: Current code state with query

    Returns:
        Dict with generated code and events
    """
    query = state.get("query", "")

    events = [
        {
            "type": "step",
            "step_type": "generate",
            "description": "Generating code...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()

    try:
        # Stream the response
        response_chunks = []
        async for chunk in llm.astream(
            [
                SystemMessage(content=CODE_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ]
        ):
            if chunk.content:
                response_chunks.append(chunk.content)
                events.append({"type": "token", "content": chunk.content})

        response = "".join(response_chunks)

        # Extract code blocks from response
        code = _extract_code(response)
        language = _detect_language(response)

        events.append(
            {
                "type": "step",
                "step_type": "generate",
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
                "type": "step",
                "step_type": "generate",
                "description": f"Error: {str(e)}",
                "status": "completed",
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
            "type": "step",
            "step_type": "execute",
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
        # Create E2B sandbox
        sandbox = await AsyncSandbox.create(
            api_key=settings.e2b_api_key,
            timeout=300,  # 5 minute timeout
        )

        logger.info("e2b_sandbox_created", sandbox_id=sandbox.sandbox_id, language=language)

        # Determine execution command based on language
        if language in ("python", "py"):
            cmd = f"python3 -c '''{code}'''"
        elif language in ("javascript", "js"):
            cmd = f"node -e '{code}'"
        elif language in ("typescript", "ts"):
            # Write to file and run with ts-node
            await sandbox.files.write("/tmp/script.ts", code)
            await sandbox.commands.run("npm install -g ts-node typescript 2>/dev/null || true", timeout=60)
            cmd = "ts-node /tmp/script.ts"
        elif language in ("bash", "sh", "shell"):
            cmd = f"bash -c '{code}'"
        else:
            # Default to python
            cmd = f"python3 -c '''{code}'''"

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
                "type": "step",
                "step_type": "execute",
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


def should_execute(state: CodeState) -> str:
    """Determine whether to execute the generated code.

    Args:
        state: Current code state

    Returns:
        Next node name: "execute" or END
    """
    # For now, don't auto-execute - just generate
    # Future: check if user explicitly requested execution
    query = state.get("query", "").lower()
    if "run" in query or "execute" in query or "test" in query:
        return "execute"
    return "end"


def _extract_code(response: str) -> str:
    """Extract code from markdown code blocks."""
    import re

    # Find code blocks with language specifier
    pattern = r"```(?:\w+)?\n(.*?)```"
    matches = re.findall(pattern, response, re.DOTALL)

    if matches:
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


def create_code_graph() -> StateGraph:
    """Create the code execution subagent graph.

    Graph structure:
    [generate_code] → [should_execute?] → [execute] → [END]
                            ↓ (no)
                          [END]

    Returns:
        Compiled code graph
    """
    graph = StateGraph(CodeState)

    # Add nodes
    graph.add_node("generate", generate_code_node)
    graph.add_node("execute", execute_code_node)

    # Set entry point
    graph.set_entry_point("generate")

    # Conditional edge: execute only if requested
    graph.add_conditional_edges(
        "generate",
        should_execute,
        {
            "execute": "execute",
            "end": END,
        },
    )

    graph.add_edge("execute", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
code_subgraph = create_code_graph()
