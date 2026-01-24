"""Browser automation tools using E2B Desktop Sandbox.

Provides browser automation capabilities in a secure, isolated environment.
Supports navigation, screenshots, and computer-use style interactions.
"""

import json
from typing import Literal
from urllib.parse import urlparse

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox.desktop_executor import E2B_DESKTOP_AVAILABLE, get_screenshot_as_base64

logger = get_logger(__name__)

# Constants for timing (in milliseconds)
WAIT_AFTER_FOCUS_ADDRESS_BAR = 800
WAIT_AFTER_SELECT_ALL = 300
WAIT_AFTER_PASTE_URL = 800  # Longer wait to ensure URL is fully pasted
WAIT_AFTER_CLICK = 500
WAIT_AFTER_SCROLL = 500

# URL truncation length for logging
URL_LOG_TRUNCATE_LENGTH = 100

# Maximum content length to return (in characters)
# This prevents token limit errors when pages have very long content
# ~4 chars per token, so 50K chars ≈ 12.5K tokens
MAX_CONTENT_LENGTH = 50000


def _validate_url(url: str) -> tuple[bool, str | None]:
    """Validate URL format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return False, "URL must include a scheme (e.g., https://)"
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported URL scheme: {parsed.scheme}. Use http or https."
        if not parsed.netloc:
            return False, "URL must include a domain (e.g., example.com)"
        return True, None
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"


async def _get_browser_session(user_id: str | None, task_id: str | None):
    """Get an existing browser session.

    Returns:
        Tuple of (manager, session) or (None, None) if unavailable
    """
    from app.sandbox import get_desktop_sandbox_manager

    manager = get_desktop_sandbox_manager()
    session = await manager.get_session(user_id=user_id, task_id=task_id)
    return manager, session


def _error_response(**kwargs) -> str:
    """Create a JSON error response."""
    return json.dumps({"success": False, **kwargs})


def _success_response(**kwargs) -> str:
    """Create a JSON success response."""
    return json.dumps({"success": True, **kwargs})


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
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
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
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with navigation results, extracted content, and optional screenshot
    """
    # Validate URL format
    is_valid, error_msg = _validate_url(url)
    if not is_valid:
        logger.warning("browser_navigate_invalid_url", url=url[:URL_LOG_TRUNCATE_LENGTH], error=error_msg)
        return _error_response(error=error_msg, url=url)

    if not E2B_DESKTOP_AVAILABLE:
        logger.error("browser_unavailable")
        return _error_response(
            error="E2B Desktop not available. Install with: pip install e2b-desktop",
            url=url,
        )

    logger.info(
        "browser_navigate_invoked",
        url=url[:URL_LOG_TRUNCATE_LENGTH],
        extract_content=extract_content,
        take_screenshot=take_screenshot,
        wait_ms=wait_ms,
    )

    try:
        from app.sandbox import get_desktop_sandbox_manager

        manager = get_desktop_sandbox_manager()
        session_key = manager.make_session_key(user_id, task_id)

        # Get existing session - supervisor should have already created it
        session = await manager.get_session(user_id=user_id, task_id=task_id)
        newly_created = False

        if session:
            logger.info(
                "browser_navigate_using_existing_session",
                session_key=session_key,
                sandbox_id=session.sandbox_id,
                browser_launched=session.browser_launched,
                stream_ready=session.is_stream_ready,
            )
        else:
            # Fallback: create session if not exists (shouldn't happen normally)
            logger.warning(
                "browser_navigate_creating_new_session",
                session_key=session_key,
                user_id=user_id,
                task_id=task_id,
            )
            session = await manager.get_or_create_sandbox(
                user_id=user_id,
                task_id=task_id,
                launch_browser=True,
            )
            newly_created = True

        executor = session.executor

        # Launch browser if needed
        if not session.browser_launched:
            logger.info("browser_navigate_launching_browser", sandbox_id=session.sandbox_id)
            await executor.launch_browser()

        # Ensure stream is ready before any visible actions
        stream_url, auth_key = await manager.ensure_stream_ready(session)

        logger.info(
            "browser_navigate_stream_ready",
            sandbox_id=session.sandbox_id,
            stream_url=stream_url[:URL_LOG_TRUNCATE_LENGTH] if stream_url else None,
            newly_created=newly_created,
        )

        # Navigate to URL using keyboard actions
        # Step 1: Focus address bar with Ctrl+L (E2B uses Linux)
        logger.info("browser_action_step1_focus_address_bar", sandbox_id=session.sandbox_id)
        await executor.press_key(["ctrl", "l"])
        await executor.wait(WAIT_AFTER_FOCUS_ADDRESS_BAR)

        # Step 2: Select all existing text with Ctrl+A
        logger.info("browser_action_step2_select_all", sandbox_id=session.sandbox_id)
        await executor.press_key(["ctrl", "a"])
        await executor.wait(WAIT_AFTER_SELECT_ALL)

        # Step 3: Type the URL (uses clipboard for non-ASCII, direct typing for ASCII)
        logger.info("browser_action_step3_type_url", sandbox_id=session.sandbox_id, url=url[:URL_LOG_TRUNCATE_LENGTH])
        await executor.type_text_via_clipboard(url)
        await executor.wait(WAIT_AFTER_PASTE_URL)

        # Step 4: Press Enter to navigate
        logger.info("browser_action_step4_press_enter", sandbox_id=session.sandbox_id)
        await executor.press_key("enter")

        # Step 5: Wait for page to load
        logger.info("browser_action_step5_waiting_for_page", sandbox_id=session.sandbox_id, wait_ms=wait_ms)
        await executor.wait(wait_ms)

        logger.info("browser_action_navigation_complete", sandbox_id=session.sandbox_id, url=url[:URL_LOG_TRUNCATE_LENGTH])

        result = {
            "success": True,
            "url": url,
            "sandbox_id": session.sandbox_id,
            "stream_url": stream_url,
            "stream_auth_key": auth_key,
            "stream_ready": session.is_stream_ready,
        }

        # Extract page content if requested
        # Note: Uses curl+html2text for extraction, separate from browser rendering
        if extract_content:
            try:
                page_content = await executor.extract_page_content(url)
                original_length = len(page_content)

                # Truncate content to prevent token limit errors
                if original_length > MAX_CONTENT_LENGTH:
                    page_content = page_content[:MAX_CONTENT_LENGTH] + f"\n\n... [Content truncated. Showing {MAX_CONTENT_LENGTH:,} of {original_length:,} characters]"
                    result["content_truncated"] = True

                result["content"] = page_content
                result["content_length"] = original_length

                logger.info(
                    "browser_content_extracted",
                    url=url[:URL_LOG_TRUNCATE_LENGTH],
                    content_length=original_length,
                    truncated=original_length > MAX_CONTENT_LENGTH,
                )
            except Exception as e:
                logger.warning(
                    "browser_content_extraction_failed",
                    url=url[:URL_LOG_TRUNCATE_LENGTH],
                    error=str(e),
                )
                result["content"] = f"Failed to extract content: {str(e)}"
                result["content_error"] = str(e)

        # Capture screenshot if requested
        if take_screenshot:
            screenshot_bytes = await executor.screenshot()
            result["screenshot"] = get_screenshot_as_base64(screenshot_bytes)

        logger.info(
            "browser_navigate_completed",
            url=url[:URL_LOG_TRUNCATE_LENGTH],
            sandbox_id=session.sandbox_id,
            has_content=extract_content,
            has_screenshot=take_screenshot,
        )

        return json.dumps(result)

    except Exception as e:
        logger.error(
            "browser_navigate_failed",
            url=url[:URL_LOG_TRUNCATE_LENGTH],
            error=str(e),
        )
        return _error_response(error=str(e), url=url)


class BrowserScreenshotInput(BaseModel):
    """Input schema for browser screenshot tool."""

    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
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
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with screenshot data
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available. Install with: pip install e2b-desktop")

    logger.info("browser_screenshot_invoked")

    try:
        manager, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        screenshot_bytes = await session.executor.screenshot()

        logger.info("browser_screenshot_completed", sandbox_id=session.sandbox_id)

        return _success_response(
            screenshot=get_screenshot_as_base64(screenshot_bytes),
            sandbox_id=session.sandbox_id,
        )

    except Exception as e:
        logger.error("browser_screenshot_failed", error=str(e))
        return _error_response(error=str(e))


class BrowserClickInput(BaseModel):
    """Input schema for browser click tool."""

    x: int = Field(description="X coordinate to click (relative to screen)")
    y: int = Field(description="Y coordinate to click (relative to screen)")
    button: Literal["left", "right", "middle"] = Field(
        default="left",
        description="Mouse button to click",
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
    )


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

    Coordinates are relative to the sandbox screen.

    Args:
        x: X coordinate to click
        y: Y coordinate to click
        button: Mouse button to use (left, right, middle)
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with click result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available")

    logger.info("browser_click_invoked", x=x, y=y, button=button)

    try:
        manager, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        # Ensure stream is ready before visible action
        await manager.ensure_stream_ready(session)

        await session.executor.click(x, y, button)
        await session.executor.wait(WAIT_AFTER_CLICK)

        logger.info("browser_click_completed", x=x, y=y, button=button)

        return _success_response(x=x, y=y, button=button, sandbox_id=session.sandbox_id)

    except Exception as e:
        logger.error("browser_click_failed", error=str(e))
        return _error_response(error=str(e))


class BrowserTypeInput(BaseModel):
    """Input schema for browser type tool."""

    text: str = Field(description="Text to type into the focused element")
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
    )


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

    Uses clipboard paste internally to handle non-ASCII characters correctly.

    Args:
        text: Text to type
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with typing result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available")

    logger.info("browser_type_invoked", text_length=len(text))

    try:
        manager, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        # Ensure stream is ready before visible action
        await manager.ensure_stream_ready(session)

        # Use clipboard paste to handle non-ASCII characters correctly
        await session.executor.type_text_via_clipboard(text)

        logger.info("browser_type_completed", text_length=len(text))

        return _success_response(text_length=len(text), sandbox_id=session.sandbox_id)

    except Exception as e:
        logger.error("browser_type_failed", error=str(e))
        return _error_response(error=str(e))


class BrowserPressKeyInput(BaseModel):
    """Input schema for browser press key tool."""

    key: str = Field(
        description="Key to press (e.g., 'enter', 'tab', 'escape', 'space', 'backspace') "
        "or combinations with '+' separator (e.g., 'ctrl+a', 'ctrl+shift+t')"
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
    )


@tool(args_schema=BrowserPressKeyInput)
async def browser_press_key(
    key: str,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Press a key or key combination in the browser.

    Presses a single key or key combination. Useful for:
    - Submitting forms (enter)
    - Navigation (tab, arrow keys)
    - Keyboard shortcuts (ctrl+a, ctrl+c, ctrl+v)
    - Closing dialogs (escape)

    Use lowercase key names (e.g., 'enter', 'tab', 'escape', 'space', 'backspace').
    For combinations, use '+' separator: 'ctrl+a', 'ctrl+shift+t'

    Args:
        key: Key or key combination to press
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with key press result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available")

    logger.info("browser_press_key_invoked", key=key)

    try:
        manager, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        # Ensure stream is ready before visible action
        await manager.ensure_stream_ready(session)

        # Parse key combinations (supports both '+' and ' ' separators)
        if "+" in key:
            keys = [k.strip() for k in key.split("+")]
            await session.executor.press_key(keys)
        elif " " in key:
            keys = [k.strip() for k in key.split()]
            await session.executor.press_key(keys)
        else:
            await session.executor.press_key(key)

        logger.info("browser_press_key_completed", key=key)

        return _success_response(key=key, sandbox_id=session.sandbox_id)

    except Exception as e:
        logger.error("browser_press_key_failed", error=str(e))
        return _error_response(error=str(e))


class BrowserScrollInput(BaseModel):
    """Input schema for browser scroll tool."""

    direction: Literal["up", "down"] = Field(
        default="down",
        description="Scroll direction (up or down)",
    )
    amount: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of scroll steps (1-20, each step is roughly one mouse wheel tick)",
    )
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
    )


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
        amount: Number of scroll steps (1-20)
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with scroll result
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available")

    logger.info("browser_scroll_invoked", direction=direction, amount=amount)

    try:
        manager, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        # Ensure stream is ready before visible action
        await manager.ensure_stream_ready(session)

        await session.executor.scroll(direction, amount)
        await session.executor.wait(WAIT_AFTER_SCROLL)

        logger.info("browser_scroll_completed", direction=direction, amount=amount)

        return _success_response(direction=direction, amount=amount, sandbox_id=session.sandbox_id)

    except Exception as e:
        logger.error("browser_scroll_failed", error=str(e))
        return _error_response(error=str(e))


class BrowserGetStreamInput(BaseModel):
    """Input schema for browser get stream URL tool."""

    user_id: str | None = Field(
        default=None,
        description="User ID for session management (injected by system)",
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (injected by system)",
    )


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
        user_id: User ID for session management (injected by system)
        task_id: Task ID for session management (injected by system)

    Returns:
        JSON string with stream URL and auth key
    """
    if not E2B_DESKTOP_AVAILABLE:
        return _error_response(error="E2B Desktop not available")

    logger.info("browser_get_stream_url_invoked")

    try:
        _, session = await _get_browser_session(user_id, task_id)

        if not session:
            return _error_response(error="No active browser sandbox session. Use browser_navigate first.")

        stream_url, auth_key = await session.executor.get_stream_url(require_auth=True)

        logger.info("browser_get_stream_url_completed")

        return _success_response(
            stream_url=stream_url,
            auth_key=auth_key,
            sandbox_id=session.sandbox_id,
        )

    except Exception as e:
        logger.error("browser_get_stream_url_failed", error=str(e))
        return _error_response(error=str(e))
