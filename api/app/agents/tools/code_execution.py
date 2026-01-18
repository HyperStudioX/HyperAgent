"""Code Execution Tool.

Provides a LangChain tool for executing code in E2B sandboxes with
session-based sandbox management for reuse across tool calls.
"""

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agents.tools.sandbox_manager import get_sandbox_manager
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExecuteCodeInput(BaseModel):
    """Input schema for code execution tool."""

    code: str = Field(
        ...,
        description="The code to execute in the sandbox",
    )
    language: Literal["python", "javascript", "typescript", "bash"] = Field(
        default="python",
        description="Programming language of the code",
    )
    packages: list[str] | None = Field(
        default=None,
        description="Optional list of packages to install before execution (pip for Python, npm for JS/TS)",
    )
    capture_visualizations: bool = Field(
        default=True,
        description="Whether to capture visualization outputs (PNG/HTML from /tmp/output*)",
    )
    timeout: int = Field(
        default=180,
        ge=1,
        le=600,
        description="Execution timeout in seconds (1-600)",
    )


@tool(args_schema=ExecuteCodeInput)
async def execute_code(
    code: str,
    language: Literal["python", "javascript", "typescript", "bash"] = "python",
    packages: list[str] | None = None,
    capture_visualizations: bool = True,
    timeout: int = 180,
    # Session context (injected by agent, not provided by LLM)
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Execute code in an E2B sandbox.

    Runs code in an isolated sandbox environment with support for multiple
    languages, package installation, and visualization capture. The sandbox
    is reused within the same user/task session for efficiency.

    Args:
        code: The code to execute
        language: Programming language (python, javascript, typescript, bash)
        packages: Optional packages to install before execution
        capture_visualizations: Whether to capture output files from /tmp/output*
        timeout: Execution timeout in seconds
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with execution results including:
        - success: Whether execution completed without errors
        - stdout: Standard output from execution
        - stderr: Standard error output
        - exit_code: Process exit code
        - visualizations: List of captured visualizations (if enabled)
        - error: Error message if execution failed
        - sandbox_id: ID of the sandbox used
    """
    # Check for E2B API key
    if not settings.e2b_api_key:
        logger.warning("e2b_api_key_not_configured")
        return json.dumps({
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "visualizations": [],
            "error": "E2B API key not configured. Set E2B_API_KEY environment variable.",
            "sandbox_id": None,
        })

    try:
        # Get or create sandbox session
        sandbox_manager = get_sandbox_manager()
        session = await sandbox_manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
        )
        executor = session.executor

        # Install packages if requested
        if packages:
            # Determine package manager based on language
            pkg_manager_map = {
                "python": "pip",
                "py": "pip",
                "javascript": "npm",
                "js": "npm",
                "typescript": "npm",
                "ts": "npm",
            }
            pkg_manager = pkg_manager_map.get(language)

            if pkg_manager:
                success, stdout, stderr = await executor.install_packages(
                    packages,
                    package_manager=pkg_manager,
                )
                if not success:
                    logger.warning(
                        "package_installation_warning",
                        packages=packages,
                        stderr=stderr[:500] if stderr else None,
                    )

        # Execute the code
        exec_result = await executor.execute_code(
            code=code,
            language=language,
            timeout=timeout,
        )

        # Capture visualizations if requested
        visualizations = []
        if capture_visualizations:
            visualizations = await executor.capture_visualizations()

        result = {
            "success": exec_result["success"],
            "stdout": exec_result["stdout"],
            "stderr": exec_result["stderr"],
            "exit_code": exec_result["exit_code"],
            "visualizations": visualizations,
            "error": None if exec_result["success"] else exec_result.get("stderr", ""),
            "sandbox_id": session.sandbox_id,
        }

        logger.info(
            "code_execution_completed",
            language=language,
            success=result["success"],
            exit_code=result["exit_code"],
            sandbox_id=session.sandbox_id,
            visualization_count=len(visualizations),
        )

        return json.dumps(result)

    except Exception as e:
        import traceback
        logger.error("code_execution_error", error=str(e), traceback=traceback.format_exc())
        return json.dumps({
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": None,
            "visualizations": [],
            "error": str(e),
            "sandbox_id": None,
        })


async def execute_code_with_context(
    code: str,
    language: Literal["python", "javascript", "typescript", "bash"] = "python",
    packages: list[str] | None = None,
    capture_visualizations: bool = True,
    timeout: int = 180,
    user_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Execute code and return parsed result dict.

    Convenience wrapper that returns a dict instead of JSON string.

    Args:
        code: The code to execute
        language: Programming language
        packages: Optional packages to install
        capture_visualizations: Whether to capture output files
        timeout: Execution timeout in seconds
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        Dict with execution results
    """
    result_json = await execute_code.ainvoke({
        "code": code,
        "language": language,
        "packages": packages,
        "capture_visualizations": capture_visualizations,
        "timeout": timeout,
        "user_id": user_id,
        "task_id": task_id,
    })
    return json.loads(result_json)
