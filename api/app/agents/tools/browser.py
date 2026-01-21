"""Browser automation tools using E2B Desktop Sandbox.

Provides browser automation capabilities in a secure, isolated environment.
Supports navigation, screenshots, and computer-use style interactions.
"""

import asyncio
import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.computer_executor import E2B_DESKTOP_AVAILABLE, get_screenshot_as_base64

logger = get_logger(__name__)


class BrowserNavigateInput(BaseModel):
    """Input schema for browser navigate tool."""

    url: str = Field(
        description="The URL to navigate to (e.g., 'https://example.com')"
    )
    extract_content: bool = Field(
        default=True,
        description="Whether to extract text content from the page (recommended for research)",
    )
    take_screenshot: bool = Field(
        default=False,
        description="Whether to capture a screenshot after navigation",
    )
    wait_ms: int = Field(
        default=5000,
        ge=1000,
        le=30000,
        description="Time to wait after navigation in milliseconds (1000-30000)",
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (auto-populated)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (auto-populated)",
    )


@tool(args_schema=BrowserNavigateInput)
async def browser_navigate(
    url: str,
    extract_content: bool = True,
    take_screenshot: bool = False,
    wait_ms: int = 5000,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Navigate to a URL in an isolated browser and extract page content.

    This tool runs a real browser in a secure E2B Desktop sandbox, providing:
    - Full browser functionality with JavaScript support
    - Text content extraction from web pages
    - Optional visual screenshots
    - Isolated environment for safe browsing

    Use this when you need to:
    - Visit websites and extract their text content for analysis
    - Access pages that require JavaScript rendering
    - Capture screenshots of web pages (optional)
    - Browse in a secure, isolated environment

    The sandbox is reused across multiple calls within the same task,
    so subsequent navigations are faster.

    Args:
        url: The URL to navigate to
        extract_content: Whether to extract text content from the page (default: True)
        take_screenshot: Whether to capture a screenshot after navigation (default: False)
        wait_ms: Time to wait after navigation for page to load
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with navigation results, extracted content, and optional screenshot
    """
    if not E2B_DESKTOP_AVAILABLE:
        error_msg = "E2B Desktop not available. Install with: pip install e2b-desktop"
        logger.error("browser_unavailable")
        return json.dumps({
            "success": False,
            "error": error_msg,
            "url": url,
        })

    logger.info(
        "browser_navigate_invoked",
        url=url[:100],
        extract_content=extract_content,
        take_screenshot=take_screenshot,
        wait_ms=wait_ms,
    )

    try:
        # Import here to avoid circular imports
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_or_create_sandbox(
            user_id=user_id,
            task_id=task_id,
            launch_browser=True,
        )

        executor = session.executor

        # Get stream URL for live viewing (reuse if already started)
        stream_url = None
        auth_key = None
        try:
            stream_url, auth_key = await executor.get_stream_url(require_auth=True)
            logger.info("browser_stream_url_retrieved", sandbox_id=session.sandbox_id)
        except Exception as e:
            # If stream is already running, try to just get the URL
            if "already running" in str(e).lower():
                try:
                    # Stream already started, get URL without starting
                    if executor.sandbox and executor.sandbox.stream:
                        auth_key = await asyncio.to_thread(executor.sandbox.stream.get_auth_key)
                        stream_url = await asyncio.to_thread(
                            executor.sandbox.stream.get_url,
                            auth_key=auth_key,
                        )
                        logger.info("browser_stream_url_reused", sandbox_id=session.sandbox_id)
                except Exception as inner_e:
                    logger.warning("browser_stream_url_reuse_failed", error=str(inner_e))
            else:
                logger.warning("browser_stream_url_failed", error=str(e))

        # Navigate to URL using keyboard
        # First, focus address bar with Ctrl+L (or Cmd+L on Mac, but E2B uses Linux)
        await executor.press_key(["ctrl", "l"])
        await executor.wait(500)

        # Clear any existing URL and paste new one via clipboard
        # Using clipboard avoids xdotool's issues with non-ASCII characters
        await executor.press_key(["ctrl", "a"])
        await executor.wait(200)
        await executor.type_text_via_clipboard(url)
        await executor.wait(300)

        # Press Enter to navigate
        await executor.press_key("Return")

        # Wait for page to load
        await executor.wait(wait_ms)

        result = {
            "success": True,
            "url": url,
            "sandbox_id": session.sandbox_id,
        }

        # Add stream URL for live viewing if available
        if stream_url:
            result["stream_url"] = stream_url
            if auth_key:
                result["stream_auth_key"] = auth_key

        # Extract page content if requested (primary use case for research)
        if extract_content:
            try:
                page_content = await executor.extract_page_content(url)
                result["content"] = page_content
                result["content_length"] = len(page_content)
                logger.info(
                    "browser_content_extracted",
                    url=url[:50],
                    content_length=len(page_content),
                )
            except Exception as e:
                logger.warning("browser_content_extraction_failed", url=url[:50], error=str(e))
                result["content"] = f"Failed to extract content: {str(e)}"
                result["content_error"] = str(e)

        # Capture screenshot if requested
        if take_screenshot:
            screenshot_bytes = await executor.screenshot()
            result["screenshot"] = get_screenshot_as_base64(screenshot_bytes)

        logger.info(
            "browser_navigate_completed",
            url=url[:50],
            success=True,
            has_content=extract_content,
            has_screenshot=take_screenshot,
            has_stream_url=bool(stream_url),
        )

        return json.dumps(result)

    except Exception as e:
        logger.error(
            "browser_navigate_failed",
            url=url[:50],
            error=str(e),
        )
        return json.dumps({
            "success": False,
            "error": str(e),
            "url": url,
        })


class BrowserScreenshotInput(BaseModel):
    """Input schema for browser screenshot tool."""

    user_id: str | None = Field(
        default=None,
        description="User ID for session management (auto-populated)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (auto-populated)",
    )


@tool(args_schema=BrowserScreenshotInput)
async def browser_screenshot(
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Capture a screenshot of the current browser state.

    Takes a screenshot of the entire sandbox, including the browser
    and any visible content. Use this to see what's currently displayed
    or to verify the results of previous actions.

    The sandbox must have been created by a previous browser_navigate
    call within the same task.

    Args:
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with screenshot data
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available. Install with: pip install e2b-desktop",
        })

    logger.info("browser_screenshot_invoked")

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        screenshot_bytes = await session.executor.screenshot()

        logger.info(
            "browser_screenshot_completed",
            sandbox_id=session.sandbox_id,
        )

        return json.dumps({
            "success": True,
            "screenshot": get_screenshot_as_base64(screenshot_bytes),
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_screenshot_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


class BrowserClickInput(BaseModel):
    """Input schema for browser click tool."""

    x: int = Field(description="X coordinate to click")
    y: int = Field(description="Y coordinate to click")
    button: Literal["left", "right", "middle"] = Field(
        default="left",
        description="Mouse button to click",
    )
    user_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)


@tool(args_schema=BrowserClickInput)
async def browser_click(
    x: int,
    y: int,
    button: Literal["left", "right", "middle"] = "left",
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Click at a specific position in the browser.

    Performs a mouse click at the specified coordinates. Use this for
    interacting with buttons, links, form fields, or any clickable elements.

    Coordinates are relative to the screen (typically 1024x768).

    Args:
        x: X coordinate to click
        y: Y coordinate to click
        button: Mouse button to use (left, right, middle)
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with click result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available",
        })

    logger.info("browser_click_invoked", x=x, y=y, button=button)

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        await session.executor.click(x, y, button)

        # Small wait after click
        await session.executor.wait(500)

        logger.info("browser_click_completed", x=x, y=y, button=button)

        return json.dumps({
            "success": True,
            "x": x,
            "y": y,
            "button": button,
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_click_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


class BrowserTypeInput(BaseModel):
    """Input schema for browser type tool."""

    text: str = Field(description="Text to type")
    user_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)


@tool(args_schema=BrowserTypeInput)
async def browser_type(
    text: str,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Type text in the browser.

    Types the specified text using the keyboard. The text will be typed
    wherever the cursor/focus currently is. Use browser_click first to
    focus on input fields before typing.

    Args:
        text: Text to type
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with typing result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available",
        })

    logger.info("browser_type_invoked", text_length=len(text))

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        # Use clipboard paste for text to avoid xdotool multi-byte issues
        await session.executor.type_text_via_clipboard(text)

        logger.info("browser_type_completed", text_length=len(text))

        return json.dumps({
            "success": True,
            "text_length": len(text),
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_type_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


class BrowserPressKeyInput(BaseModel):
    """Input schema for browser press key tool."""

    key: str = Field(
        description="Key to press (e.g., 'Return', 'Tab', 'Escape', or combinations like 'ctrl+a')"
    )
    user_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)


@tool(args_schema=BrowserPressKeyInput)
async def browser_press_key(
    key: str,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Press a key or key combination in the browser.

    Presses a single key or key combination. Useful for:
    - Submitting forms (Return/Enter)
    - Navigation (Tab, arrow keys)
    - Keyboard shortcuts (ctrl+a, ctrl+c, ctrl+v)
    - Closing dialogs (Escape)

    Key names follow X11 naming conventions (e.g., 'Return' not 'Enter').
    For combinations, use format: 'ctrl+a' or ['ctrl', 'a']

    Args:
        key: Key or key combination to press
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with key press result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available",
        })

    logger.info("browser_press_key_invoked", key=key)

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        # Handle key combinations with + separator
        if "+" in key:
            keys = key.split("+")
            await session.executor.press_key(keys)
        else:
            await session.executor.press_key(key)

        logger.info("browser_press_key_completed", key=key)

        return json.dumps({
            "success": True,
            "key": key,
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_press_key_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


class BrowserScrollInput(BaseModel):
    """Input schema for browser scroll tool."""

    direction: Literal["up", "down"] = Field(
        default="down",
        description="Scroll direction",
    )
    amount: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of scroll steps (1-20)",
    )
    user_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)


@tool(args_schema=BrowserScrollInput)
async def browser_scroll(
    direction: Literal["up", "down"] = "down",
    amount: int = 3,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Scroll the page in the browser.

    Scrolls the page up or down by the specified amount.
    Useful for viewing content below the fold or navigating long pages.

    Args:
        direction: Scroll direction (up or down)
        amount: Number of scroll steps
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with scroll result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available",
        })

    logger.info("browser_scroll_invoked", direction=direction, amount=amount)

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        await session.executor.scroll(direction, amount)

        # Small wait after scroll
        await session.executor.wait(500)

        logger.info("browser_scroll_completed", direction=direction, amount=amount)

        return json.dumps({
            "success": True,
            "direction": direction,
            "amount": amount,
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_scroll_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })


class BrowserGetStreamInput(BaseModel):
    """Input schema for browser get stream URL tool."""

    user_id: str | None = Field(default=None)
    task_id: str | None = Field(default=None)


@tool(args_schema=BrowserGetStreamInput)
async def browser_get_stream_url(
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Get a live stream URL of the browser.

    Returns a URL that can be used to view the browser in real-time.
    Useful for monitoring browser activity or debugging.

    The stream URL requires authentication by default.

    Args:
        user_id: User ID for session management
        task_id: Task ID for session management

    Returns:
        JSON string with stream URL and auth key
    """
    if not E2B_DESKTOP_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "E2B Desktop not available",
        })

    logger.info("browser_get_stream_url_invoked")

    try:
        from app.agents.tools.browser_sandbox_manager import get_browser_sandbox_manager

        manager = get_browser_sandbox_manager()
        session = await manager.get_session(
            user_id=user_id,
            task_id=task_id,
        )

        if not session:
            return json.dumps({
                "success": False,
                "error": "No active browser sandbox session. Use browser_navigate first.",
            })

        stream_url, auth_key = await session.executor.get_stream_url(require_auth=True)

        logger.info("browser_get_stream_url_completed")

        return json.dumps({
            "success": True,
            "stream_url": stream_url,
            "auth_key": auth_key,
            "sandbox_id": session.sandbox_id,
        })

    except Exception as e:
        logger.error("browser_get_stream_url_failed", error=str(e))
        return json.dumps({
            "success": False,
            "error": str(e),
        })
