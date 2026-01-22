"""Computer use tool for autonomous desktop control.

This implements a unified computer_use tool following Anthropic's API pattern,
integrated with E2B Desktop sandbox for execution.
"""

import asyncio
import base64
import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox.computer_executor import E2B_DESKTOP_AVAILABLE

logger = get_logger(__name__)

# Desktop dimensions (E2B default)
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768


class ComputerUseInput(BaseModel):
    """Input schema for unified computer_use tool."""

    action: Literal[
        "screenshot",
        "click",
        "double_click",
        "type",
        "key",
        "scroll",
        "cursor_position",
        "move",
        "drag",
        "wait",
        "launch_browser",
    ] = Field(
        description="The action to perform on the desktop"
    )
    coordinate: tuple[int, int] | None = Field(
        default=None,
        description="(x, y) coordinate for click, move, or scroll actions. Required for click/move/scroll."
    )
    text: str | None = Field(
        default=None,
        description="Text to type. Required for 'type' action."
    )
    key: str | None = Field(
        default=None,
        description="Key or key combination to press (e.g., 'enter', 'ctrl+a', 'ctrl+shift+t'). Required for 'key' action."
    )
    scroll_direction: Literal["up", "down"] | None = Field(
        default=None,
        description="Scroll direction. Required for 'scroll' action."
    )
    scroll_amount: int | None = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of scroll steps (1-20). Used with 'scroll' action."
    )
    duration_ms: int | None = Field(
        default=None,
        ge=100,
        le=30000,
        description="Duration in milliseconds for 'wait' action (100-30000)."
    )
    drag_end: tuple[int, int] | None = Field(
        default=None,
        description="End coordinate for drag action. Requires 'coordinate' as start position."
    )
    button: Literal["left", "right", "middle"] | None = Field(
        default="left",
        description="Mouse button for click action."
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (auto-populated)."
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (auto-populated)."
    )


@tool(args_schema=ComputerUseInput)
async def computer_use(
    action: Literal[
        "screenshot",
        "click",
        "double_click",
        "type",
        "key",
        "scroll",
        "cursor_position",
        "move",
        "drag",
        "wait",
        "launch_browser",
    ],
    coordinate: tuple[int, int] | None = None,
    text: str | None = None,
    key: str | None = None,
    scroll_direction: Literal["up", "down"] | None = None,
    scroll_amount: int | None = 3,
    duration_ms: int | None = None,
    drag_end: tuple[int, int] | None = None,
    button: Literal["left", "right", "middle"] | None = "left",
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Control the computer desktop to complete tasks.

    This tool provides comprehensive desktop control capabilities in an E2B sandbox:
    - Take screenshots to see the current state
    - Click on UI elements at specific coordinates
    - Type text into focused elements
    - Press keyboard keys and shortcuts
    - Scroll the page
    - Move the cursor
    - Drag elements

    Actions:
    - screenshot: Capture the current desktop state. Returns base64-encoded PNG.
    - click: Click at coordinate (x, y). Use button param for right/middle click.
    - double_click: Double-click at coordinate (x, y).
    - type: Type text into the focused element.
    - key: Press a key or key combination (e.g., "enter", "ctrl+a", "ctrl+shift+t").
    - scroll: Scroll at the current position. Requires scroll_direction.
    - cursor_position: Get the current cursor position.
    - move: Move cursor to coordinate (x, y).
    - drag: Drag from coordinate to drag_end.
    - wait: Wait for duration_ms milliseconds.
    - launch_browser: Launch the browser (call this first before browsing).

    The desktop is 1024x768 pixels. Always take a screenshot first to understand
    the current state before performing actions.

    Args:
        action: The action to perform
        coordinate: (x, y) position for click/move/scroll/drag
        text: Text to type
        key: Key or key combination to press
        scroll_direction: "up" or "down" for scroll action
        scroll_amount: Number of scroll steps (1-20)
        duration_ms: Wait duration in milliseconds
        drag_end: End position for drag action
        button: Mouse button for click action
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with the action result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available. Install with: pip install e2b-desktop",
        })

    logger.info(
        "computer_use_invoked",
        action=action,
        coordinate=coordinate,
        has_text=text is not None,
        has_key=key is not None,
    )

    try:
        from app.sandbox import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()

        # For launch_browser, we need to create sandbox and launch
        if action == "launch_browser":
            session = await manager.get_or_create_sandbox(
                user_id=user_id,
                task_id=task_id,
                launch_browser=True,
            )
            # Ensure stream is ready - this starts the stream and waits for connection
            stream_url, auth_key = await manager.ensure_stream_ready(session)
            return json.dumps({
                "success": True,
                "action": "launch_browser",
                "sandbox_id": session.sandbox_id,
                "stream_url": stream_url,
                "auth_key": auth_key,
                "stream_ready": session.is_stream_ready,
                "screen_size": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            })

        # For other actions, get existing session or create new one
        session = await manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
            launch_browser=action != "screenshot",  # Don't auto-launch for screenshot-only
        )
        executor = session.executor

        # For visible actions (not screenshot), ensure stream is ready first
        visible_actions = {"click", "double_click", "type", "key", "scroll", "move", "drag"}
        if action in visible_actions:
            await manager.ensure_stream_ready(session)

        # Handle each action type
        if action == "screenshot":
            screenshot_bytes = await executor.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return json.dumps({
                "success": True,
                "action": "screenshot",
                "screenshot": screenshot_b64,
                "screen_size": {"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            })

        elif action == "click":
            if coordinate is None:
                return json.dumps({
                    "success": False,
                    "error": "coordinate is required for click action",
                })
            x, y = coordinate
            await executor.click(x, y, button=button or "left")
            return json.dumps({
                "success": True,
                "action": "click",
                "coordinate": [x, y],
                "button": button,
            })

        elif action == "double_click":
            if coordinate is None:
                return json.dumps({
                    "success": False,
                    "error": "coordinate is required for double_click action",
                })
            x, y = coordinate
            await executor.double_click(x, y)
            return json.dumps({
                "success": True,
                "action": "double_click",
                "coordinate": [x, y],
            })

        elif action == "type":
            if text is None:
                return json.dumps({
                    "success": False,
                    "error": "text is required for type action",
                })
            # Use clipboard method for reliability
            await executor.type_text_via_clipboard(text)
            return json.dumps({
                "success": True,
                "action": "type",
                "text_length": len(text),
            })

        elif action == "key":
            if key is None:
                return json.dumps({
                    "success": False,
                    "error": "key is required for key action",
                })
            # Parse key combination if it contains +
            if "+" in key:
                key_combo = key.split("+")
            else:
                key_combo = key
            await executor.press_key(key_combo)
            return json.dumps({
                "success": True,
                "action": "key",
                "key": key,
            })

        elif action == "scroll":
            if scroll_direction is None:
                return json.dumps({
                    "success": False,
                    "error": "scroll_direction is required for scroll action",
                })
            await executor.scroll(
                direction=scroll_direction,
                amount=scroll_amount or 3,
            )
            return json.dumps({
                "success": True,
                "action": "scroll",
                "direction": scroll_direction,
                "amount": scroll_amount,
            })

        elif action == "cursor_position":
            # E2B doesn't have a direct cursor position API
            # We track it internally or return unknown
            return json.dumps({
                "success": True,
                "action": "cursor_position",
                "position": "unknown",
                "note": "Cursor position tracking not available. Take a screenshot to see visual state.",
            })

        elif action == "move":
            if coordinate is None:
                return json.dumps({
                    "success": False,
                    "error": "coordinate is required for move action",
                })
            x, y = coordinate
            await executor.move_mouse(x, y)
            return json.dumps({
                "success": True,
                "action": "move",
                "coordinate": [x, y],
            })

        elif action == "drag":
            if coordinate is None or drag_end is None:
                return json.dumps({
                    "success": False,
                    "error": "coordinate and drag_end are required for drag action",
                })
            await executor.drag(
                from_pos=tuple(coordinate),
                to_pos=tuple(drag_end),
            )
            return json.dumps({
                "success": True,
                "action": "drag",
                "from": list(coordinate),
                "to": list(drag_end),
            })

        elif action == "wait":
            if duration_ms is None:
                return json.dumps({
                    "success": False,
                    "error": "duration_ms is required for wait action",
                })
            await executor.wait(duration_ms)
            return json.dumps({
                "success": True,
                "action": "wait",
                "duration_ms": duration_ms,
            })

        else:
            return json.dumps({
                "success": False,
                "error": f"Unknown action: {action}",
            })

    except Exception as e:
        logger.error("computer_use_error", action=action, error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
            "action": action,
        })


class ComputerBashInput(BaseModel):
    """Input schema for computer bash tool."""

    command: str = Field(
        description="The bash command to execute in the sandbox"
    )
    timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=300000,
        description="Command timeout in milliseconds (1000-300000)"
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (auto-populated)"
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (auto-populated)"
    )


@tool(args_schema=ComputerBashInput)
async def computer_bash(
    command: str,
    timeout_ms: int = 30000,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Execute a bash command in the computer sandbox.

    This tool runs shell commands in the E2B Desktop sandbox environment.
    Use it for:
    - Installing software (apt-get, pip)
    - File operations (ls, cat, mkdir, etc.)
    - Running scripts
    - System configuration

    The command runs with full shell access in the sandbox. Be careful with
    destructive commands.

    Args:
        command: Bash command to execute
        timeout_ms: Command timeout in milliseconds
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with stdout, stderr, and exit code
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available. Install with: pip install e2b-desktop",
        })

    logger.info(
        "computer_bash_invoked",
        command=command[:100],
        timeout_ms=timeout_ms,
    )

    try:
        from app.sandbox import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
            launch_browser=False,
        )

        stdout, stderr, exit_code = await session.executor.run_command(
            command,
            timeout_ms=timeout_ms,
        )

        return json.dumps({
            "success": exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        })

    except Exception as e:
        logger.error("computer_bash_error", command=command[:50], error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


# Export all computer tools
COMPUTER_TOOLS = [computer_use, computer_bash]
