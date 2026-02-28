"""Shell / Process Management Tools for Sandbox.

Provides LangChain tools for executing commands, managing background processes,
viewing output, and controlling process lifecycle within sandboxes.
"""

import asyncio
import json
import uuid

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox.execution_sandbox_manager import get_execution_sandbox_manager

logger = get_logger(__name__)

# Module-level storage for background shell sessions
# Maps session_id -> {"task": asyncio.Task, "output": str, "exit_code": int|None, "done": bool}
_background_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class ShellExecInput(BaseModel):
    """Input schema for shell_exec tool."""

    command: str = Field(
        ...,
        description="Shell command to execute",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for background process tracking. Auto-generated if not provided.",
    )
    background: bool = Field(
        default=False,
        description="If True, run command in background and return session_id immediately",
    )
    timeout: int = Field(
        default=120,
        description="Timeout in seconds for synchronous execution (ignored for background)",
    )
    user_id: str | None = Field(
        default=None,
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        json_schema_extra={"exclude": True},
    )


class ShellViewInput(BaseModel):
    """Input schema for shell_view tool."""

    session_id: str = Field(
        ...,
        description="Session ID of the background process to view output from",
    )


class ShellWaitInput(BaseModel):
    """Input schema for shell_wait tool."""

    session_id: str = Field(
        ...,
        description="Session ID of the background process to wait for",
    )
    timeout: int = Field(
        default=30,
        description="Maximum seconds to wait for completion",
    )


class ShellKillInput(BaseModel):
    """Input schema for shell_kill tool."""

    session_id: str = Field(
        ...,
        description="Session ID of the background process to terminate",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_sandbox_runtime(user_id: str | None, task_id: str | None):
    """Get sandbox runtime, creating session if needed."""
    manager = get_execution_sandbox_manager()
    session = await manager.get_or_create_sandbox(user_id=user_id, task_id=task_id)
    return session.executor.get_runtime()


async def _run_background_command(runtime, command: str, session_id: str) -> None:
    """Run a command in the background and store output."""
    try:
        result = await runtime.run_command(command, timeout=600)
        _background_sessions[session_id]["output"] = (
            (result.stdout or "") + (result.stderr or "")
        )
        _background_sessions[session_id]["exit_code"] = result.exit_code
    except asyncio.CancelledError:
        _background_sessions[session_id]["output"] += "\n[Process cancelled]"
        _background_sessions[session_id]["exit_code"] = -1
    except Exception as e:
        _background_sessions[session_id]["output"] += f"\n[Error: {e}]"
        _background_sessions[session_id]["exit_code"] = -1
    finally:
        _background_sessions[session_id]["done"] = True


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(args_schema=ShellExecInput)
async def shell_exec(
    command: str,
    session_id: str | None = None,
    background: bool = False,
    timeout: int = 120,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Execute a shell command in the sandbox.

    Run commands synchronously (default) or in background for long-running
    processes like dev servers. Use shell_view to monitor background output.
    """
    logger.info("shell_exec_invoked", command=command[:200], background=background)

    try:
        runtime = await _get_sandbox_runtime(user_id, task_id)
    except Exception as e:
        logger.error("shell_exec_sandbox_error", error=str(e))
        return json.dumps({"success": False, "error": f"Sandbox unavailable: {e}"})

    if background:
        sid = session_id or f"shell_{uuid.uuid4().hex[:8]}"
        _background_sessions[sid] = {
            "task": None,
            "output": "",
            "exit_code": None,
            "done": False,
            "command": command,
        }
        task = asyncio.create_task(_run_background_command(runtime, command, sid))
        _background_sessions[sid]["task"] = task
        logger.info("shell_exec_background_started", session_id=sid)
        return json.dumps({
            "success": True,
            "session_id": sid,
            "message": f"Background process started. Use shell_view('{sid}') to check output.",
        })

    # Synchronous execution
    try:
        result = await runtime.run_command(command, timeout=timeout)
        logger.info(
            "shell_exec_completed",
            exit_code=result.exit_code,
            stdout_len=len(result.stdout or ""),
        )
        return json.dumps({
            "success": True,
            "exit_code": result.exit_code,
            "stdout": (result.stdout or "")[:10000],
            "stderr": (result.stderr or "")[:5000],
        })
    except Exception as e:
        logger.error("shell_exec_failed", error=str(e))
        return json.dumps({"success": False, "error": str(e)})


@tool(args_schema=ShellViewInput)
async def shell_view(session_id: str) -> str:
    """View recent output from a background shell session."""
    logger.info("shell_view_invoked", session_id=session_id)

    session = _background_sessions.get(session_id)
    if not session:
        return json.dumps({
            "success": False,
            "error": f"Session '{session_id}' not found. Active sessions: {list(_background_sessions.keys())}",
        })

    return json.dumps({
        "success": True,
        "session_id": session_id,
        "command": session.get("command", ""),
        "output": (session.get("output", "") or "")[-5000:],
        "done": session["done"],
        "exit_code": session["exit_code"],
    })


@tool(args_schema=ShellWaitInput)
async def shell_wait(session_id: str, timeout: int = 30) -> str:
    """Wait for a background shell process to complete."""
    logger.info("shell_wait_invoked", session_id=session_id, timeout=timeout)

    session = _background_sessions.get(session_id)
    if not session:
        return json.dumps({
            "success": False,
            "error": f"Session '{session_id}' not found.",
        })

    if session["done"]:
        return json.dumps({
            "success": True,
            "session_id": session_id,
            "output": (session.get("output", "") or "")[-10000:],
            "exit_code": session["exit_code"],
            "already_done": True,
        })

    task = session.get("task")
    if not task:
        return json.dumps({"success": False, "error": "No task associated with session."})

    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        return json.dumps({
            "success": True,
            "session_id": session_id,
            "output": (session.get("output", "") or "")[-10000:],
            "exit_code": session["exit_code"],
        })
    except asyncio.TimeoutError:
        return json.dumps({
            "success": True,
            "session_id": session_id,
            "output": (session.get("output", "") or "")[-5000:],
            "exit_code": None,
            "timed_out": True,
            "message": f"Process still running after {timeout}s. Use shell_view to check later.",
        })


@tool(args_schema=ShellKillInput)
async def shell_kill(session_id: str) -> str:
    """Terminate a running background shell process."""
    logger.info("shell_kill_invoked", session_id=session_id)

    session = _background_sessions.get(session_id)
    if not session:
        return json.dumps({
            "success": False,
            "error": f"Session '{session_id}' not found.",
        })

    task = session.get("task")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    _background_sessions.pop(session_id, None)
    logger.info("shell_kill_completed", session_id=session_id)

    return json.dumps({
        "success": True,
        "session_id": session_id,
        "message": "Process terminated and session cleaned up.",
    })
