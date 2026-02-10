"""BoxLite Desktop Executor.

Local Docker-based implementation of the desktop/browser sandbox executor.
Uses boxlite.ComputerBox for browser automation in a local container.

Note: BoxLite does not support live WebRTC streaming. The get_stream_url()
method raises NotImplementedError; callers should fall back to screenshot-based
viewing.
"""

import asyncio
import base64
from typing import Literal

from app.config import settings
from app.core.logging import get_logger
from app.sandbox.base_desktop_executor import BaseDesktopExecutor, get_screenshot_as_base64

logger = get_logger(__name__)

try:
    import boxlite

    BOXLITE_DESKTOP_AVAILABLE = True
except ImportError:
    BOXLITE_DESKTOP_AVAILABLE = False
    boxlite = None  # type: ignore[assignment]


class BoxLiteDesktopExecutor(BaseDesktopExecutor):
    """Manages BoxLite desktop sandbox for browser operations.

    Uses boxlite.ComputerBox which provides a headless desktop environment
    with browser automation capabilities.
    """

    def __init__(
        self,
        image: str | None = None,
        timeout: int | None = None,
        default_browser: str | None = None,
    ):
        self._image = image or settings.boxlite_desktop_image
        self._timeout = timeout or settings.boxlite_desktop_timeout
        self._default_browser = default_browser or settings.boxlite_desktop_default_browser
        self._box: "boxlite.ComputerBox | None" = None
        self._browser_launched: bool = False
        self._sandbox_id: str | None = None

    @property
    def sandbox_id(self) -> str | None:
        return self._sandbox_id

    @property
    def browser_launched(self) -> bool:
        return self._browser_launched

    async def create_sandbox(self) -> str:
        if not BOXLITE_DESKTOP_AVAILABLE:
            raise ValueError("BoxLite not installed. Install with: pip install boxlite")

        # ComputerBox constructor is synchronous (creates the container)
        self._box = await asyncio.to_thread(
            boxlite.ComputerBox,
            cpu=settings.boxlite_cpus,
            memory=settings.boxlite_memory_mib,
        )

        # Start the container, then wait for the desktop environment to be ready
        await self._box.start()
        await self._box.wait_until_ready(timeout=self._timeout)

        import uuid

        self._sandbox_id = f"boxlite-desktop-{uuid.uuid4().hex[:12]}"
        logger.info(
            "boxlite_desktop_sandbox_created",
            sandbox_id=self._sandbox_id,
            image=self._image,
        )
        return self._sandbox_id

    # Browser executable names to try, in order of preference
    _BROWSER_FALLBACKS = ["chromium-browser", "chromium", "google-chrome", "firefox"]

    async def launch_browser(
        self,
        browser: str | None = None,
        wait_ms: int = 10000,
    ) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        browser_name = browser or self._default_browser
        logger.info("boxlite_launching_browser", browser=browser_name)

        # Try the requested browser first, then fall back to alternatives
        candidates = [browser_name] + [
            b for b in self._BROWSER_FALLBACKS if b != browser_name
        ]

        last_error: Exception | None = None
        for candidate in candidates:
            try:
                await self._box.exec(candidate, "&")
                await asyncio.sleep(wait_ms / 1000)
                self._browser_launched = True
                logger.info("boxlite_browser_launched", browser=candidate)
                return
            except Exception as e:
                logger.warning(
                    "boxlite_browser_not_found",
                    browser=candidate,
                    error=str(e),
                )
                last_error = e

        raise RuntimeError(
            f"No browser found in container. Tried: {candidates}. "
            f"Last error: {last_error}"
        )

    async def screenshot(self) -> bytes:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # ComputerBox.screenshot() returns a dict with base64 data
        result = await self._box.screenshot()
        screenshot_b64 = result["data"]
        screenshot_bytes = base64.b64decode(screenshot_b64)
        logger.info("boxlite_screenshot_captured", size=len(screenshot_bytes))
        return screenshot_bytes

    async def click(
        self,
        x: int,
        y: int,
        button: Literal["left", "right", "middle"] = "left",
    ) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await self._box.mouse_move(x, y)

        if button == "left":
            await self._box.left_click()
        elif button == "right":
            await self._box.right_click()
        elif button == "middle":
            await self._box.middle_click()

    async def double_click(self, x: int, y: int) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await self._box.mouse_move(x, y)
        await self._box.double_click()

    async def type_text(
        self,
        text: str,
        chunk_size: int = 25,
        delay_ms: int = 75,
    ) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # ComputerBox.type() uses xdotool type under the hood
        await self._box.type(text)

    async def type_text_via_clipboard(self, text: str) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # Try direct typing for ASCII text
        try:
            text.encode("ascii")
            await self.type_text(text)
            return
        except UnicodeEncodeError:
            pass

        # Use clipboard for non-ASCII text
        import shlex

        safe_text = shlex.quote(text)
        result = await self._box.exec(
            "bash", "-c",
            f"echo -n {safe_text} | xclip -selection clipboard 2>/dev/null",
        )

        if result.exit_code != 0:
            # Fallback to direct typing
            await self.type_text(text)
            return

        await asyncio.sleep(0.1)
        await self._box.key("ctrl+v")
        await asyncio.sleep(0.1)

    async def press_key(self, key: str | list[str]) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # ComputerBox.key() expects a string like "Return", "ctrl+c", etc.
        if isinstance(key, list):
            key_str = "+".join(key)
        else:
            key_str = key
        await self._box.key(key_str)

    async def scroll(
        self,
        direction: Literal["up", "down"] = "down",
        amount: int = 3,
    ) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        # ComputerBox.scroll() requires x, y coordinates; use current cursor position
        cursor_x, cursor_y = await self._box.cursor_position()
        await self._box.scroll(cursor_x, cursor_y, direction, amount)

    async def move_mouse(self, x: int, y: int) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await self._box.mouse_move(x, y)

    async def drag(
        self,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
    ) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await self._box.left_click_drag(
            from_pos[0], from_pos[1], to_pos[0], to_pos[1],
        )

    async def wait(self, milliseconds: int) -> None:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.sleep(milliseconds / 1000)

    async def run_command(self, command: str, timeout_ms: int = 30000) -> tuple[str, str, int]:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        result = await self._box.exec("bash", "-c", command)
        return result.stdout, result.stderr, result.exit_code

    async def extract_page_content(self, url: str, timeout_ms: int = 30000) -> str:
        if not self._box:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        extract_script = f"""python3 -c "
import urllib.request
import html.parser

class TextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip_tags = {{'script', 'style', 'head', 'title', 'meta',
            'noscript', 'header', 'footer', 'nav'}}
        self.current_tag = None
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
    def handle_endtag(self, tag):
        self.current_tag = None
    def handle_data(self, data):
        if self.current_tag not in self.skip_tags:
            text = data.strip()
            if text:
                self.text.append(text)
    def get_text(self):
        return chr(10).join(self.text)

try:
    req = urllib.request.Request('{url}', headers={{'User-Agent': 'Mozilla/5.0'}})
    with urllib.request.urlopen(req, timeout=20) as response:
        html_content = response.read().decode('utf-8', errors='ignore')
    parser = TextExtractor()
    parser.feed(html_content)
    print(parser.get_text())
except Exception as e:
    print(f'Error: {{e}}')
"
"""
        try:
            stdout, stderr, exit_code = await self.run_command(extract_script, timeout_ms)
            if exit_code != 0:
                return f"Failed to extract content: {stderr[:500] if stderr else 'Unknown error'}"
            content = stdout.strip()
            if not content:
                return "No text content found on the page."
            max_chars = 15000
            if len(content) > max_chars:
                content = (
                    content[:max_chars]
                    + f"\n\n[Content truncated - showing first {max_chars} characters]"
                )
            return content
        except Exception as e:
            return f"Error extracting content: {str(e)}"

    async def cleanup(self) -> None:
        if self._box:
            sandbox_id = self._sandbox_id
            try:
                # Use async context manager exit for cleanup.
                # ComputerBox.shutdown() has a bug (calls self._box.shutdown()
                # on the native Box which doesn't have that method).
                await self._box.__aexit__(None, None, None)
                logger.info("boxlite_desktop_sandbox_cleaned_up", sandbox_id=sandbox_id)
            except Exception as e:
                logger.warning(
                    "boxlite_desktop_cleanup_failed", sandbox_id=sandbox_id, error=str(e)
                )
            finally:
                self._box = None
                self._browser_launched = False


__all__ = [
    "BoxLiteDesktopExecutor",
    "BOXLITE_DESKTOP_AVAILABLE",
    "get_screenshot_as_base64",
]
