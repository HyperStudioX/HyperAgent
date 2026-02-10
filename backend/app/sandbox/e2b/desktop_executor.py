"""E2B Desktop Executor.

E2B-specific implementation of the desktop/browser sandbox executor.
Wraps E2B Desktop SDK for browser automation, screenshots, mouse/keyboard
input, streaming, and content extraction.
"""

import asyncio
import base64
import shlex
from typing import Literal

from app.config import settings
from app.core.logging import get_logger
from app.middleware.circuit_breaker import CircuitBreakerOpen, get_e2b_breaker
from app.sandbox.base_desktop_executor import BaseDesktopExecutor

logger = get_logger(__name__)

# E2B Desktop SDK import
try:
    from e2b_desktop import Sandbox as DesktopSandbox

    E2B_DESKTOP_AVAILABLE = True
except ImportError:
    E2B_DESKTOP_AVAILABLE = False
    DesktopSandbox = None
    logger.warning(
        "e2b_desktop_not_installed",
        message="Install with: pip install e2b-desktop",
    )


class E2BDesktopExecutor(BaseDesktopExecutor):
    """Manages E2B Desktop sandbox for browser operations."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int | None = None,
        default_browser: str | None = None,
    ):
        self.api_key = api_key or settings.e2b_api_key
        self.timeout = timeout or settings.e2b_desktop_timeout
        self.default_browser = default_browser or settings.e2b_desktop_default_browser
        self.sandbox: DesktopSandbox | None = None
        self._browser_launched: bool = False
        self._stream_started: bool = False

    @property
    def sandbox_id(self) -> str | None:
        if self.sandbox:
            return self.sandbox.sandbox_id
        return None

    @property
    def browser_launched(self) -> bool:
        return self._browser_launched

    @property
    def stream_started(self) -> bool:
        return self._stream_started

    async def create_sandbox(self) -> str:
        if not E2B_DESKTOP_AVAILABLE:
            raise ValueError("E2B Desktop not available. Install with: pip install e2b-desktop")

        if not self.api_key:
            raise ValueError("E2B API key not configured. Set E2B_API_KEY environment variable.")

        breaker = get_e2b_breaker()

        try:
            async with breaker.call():
                self.sandbox = await asyncio.to_thread(
                    DesktopSandbox.create,
                    timeout=self.timeout,
                    api_key=self.api_key,
                )
            logger.info(
                "e2b_desktop_sandbox_created",
                sandbox_id=self.sandbox.sandbox_id,
                timeout=self.timeout,
            )
            return self.sandbox.sandbox_id

        except CircuitBreakerOpen as e:
            logger.warning(
                "e2b_desktop_sandbox_circuit_open",
                service="e2b_desktop",
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error("e2b_desktop_sandbox_creation_failed", error=str(e))
            raise

    async def launch_browser(
        self,
        browser: str | None = None,
        wait_ms: int = 10000,
    ) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        browser_name = browser or self.default_browser
        logger.info("launching_browser", browser=browser_name)

        await asyncio.to_thread(self.sandbox.launch, browser_name)
        await asyncio.to_thread(self.sandbox.wait, wait_ms)

        try:
            await asyncio.to_thread(self.sandbox.move_mouse, 512, 384)
            await asyncio.to_thread(self.sandbox.left_click)
            await asyncio.to_thread(self.sandbox.wait, 500)
            await asyncio.to_thread(self.sandbox.press, ["alt", "F10"])
            await asyncio.to_thread(self.sandbox.wait, 500)
            logger.debug("browser_window_focused_and_maximized", browser=browser_name)
        except Exception as e:
            logger.warning("browser_window_focus_failed", browser=browser_name, error=str(e))

        self._browser_launched = True
        logger.info("browser_launched", browser=browser_name)

    async def screenshot(self) -> bytes:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        screenshot_bytes = await asyncio.to_thread(
            self.sandbox.screenshot,
            "bytes",
        )

        logger.info("screenshot_captured", size=len(screenshot_bytes))
        return bytes(screenshot_bytes)

    async def click(
        self,
        x: int,
        y: int,
        button: Literal["left", "right", "middle"] = "left",
    ) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.move_mouse, x, y)

        if button == "left":
            await asyncio.to_thread(self.sandbox.left_click)
        elif button == "right":
            await asyncio.to_thread(self.sandbox.right_click)
        elif button == "middle":
            await asyncio.to_thread(self.sandbox.middle_click)

        logger.debug("mouse_clicked", x=x, y=y, button=button)

    async def double_click(self, x: int, y: int) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.move_mouse, x, y)
        await asyncio.to_thread(self.sandbox.double_click)
        logger.debug("mouse_double_clicked", x=x, y=y)

    async def type_text(
        self,
        text: str,
        chunk_size: int = 25,
        delay_ms: int = 75,
    ) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(
            self.sandbox.write,
            text,
            chunk_size=chunk_size,
            delay_in_ms=delay_ms,
        )
        logger.debug("text_typed", length=len(text))

    async def type_text_via_clipboard(self, text: str) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        try:
            text.encode("ascii")
            is_ascii = True
        except UnicodeEncodeError:
            is_ascii = False

        if is_ascii:
            await self.type_text(text)
            logger.debug("text_typed_direct", length=len(text))
            return

        safe_text = shlex.quote(text)

        copy_cmd = f"echo -n {safe_text} | xclip -selection clipboard 2>/dev/null"
        stdout, stderr, exit_code = await self.run_command(copy_cmd)

        if exit_code != 0:
            copy_cmd = f"echo -n {safe_text} | xsel --clipboard --input 2>/dev/null"
            stdout, stderr, exit_code = await self.run_command(copy_cmd)

        if exit_code != 0:
            logger.warning(
                "clipboard_not_available_fallback_to_direct",
                text_preview=text[:20],
            )
            await self.type_text(text)
            return

        await self.wait(100)
        await self.press_key(["ctrl", "v"])
        await self.wait(100)

        logger.debug("text_typed_via_clipboard", length=len(text))

    async def press_key(self, key: str | list[str]) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.press, key)
        logger.debug("key_pressed", key=key)

    async def scroll(
        self,
        direction: Literal["up", "down"] = "down",
        amount: int = 3,
    ) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.scroll, direction, amount)
        logger.debug("scrolled", direction=direction, amount=amount)

    async def move_mouse(self, x: int, y: int) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.move_mouse, x, y)
        logger.debug("mouse_moved", x=x, y=y)

    async def drag(
        self,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
    ) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.drag, from_pos, to_pos)
        logger.debug("dragged", from_pos=from_pos, to_pos=to_pos)

    async def wait(self, milliseconds: int) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.wait, milliseconds)

    async def get_stream_url(self, require_auth: bool = True) -> tuple[str, str | None]:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        if not self._stream_started:
            try:
                await asyncio.to_thread(
                    self.sandbox.stream.start,
                    require_auth=require_auth,
                )
                self._stream_started = True
                logger.info("stream_started", require_auth=require_auth)
            except Exception as e:
                error_msg = str(e).lower()
                if "already running" in error_msg or "already started" in error_msg:
                    self._stream_started = True
                    logger.debug("stream_already_running", message=str(e))
                else:
                    raise

        auth_key = None
        if require_auth:
            auth_key = await asyncio.to_thread(self.sandbox.stream.get_auth_key)

        stream_url = await asyncio.to_thread(
            self.sandbox.stream.get_url,
            auth_key=auth_key,
        )

        logger.info("stream_url_retrieved", require_auth=require_auth)
        return stream_url, auth_key

    async def stop_stream(self) -> None:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        await asyncio.to_thread(self.sandbox.stream.stop)
        logger.info("stream_stopped")

    async def run_command(self, command: str, timeout_ms: int = 30000) -> tuple[str, str, int]:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        result = await asyncio.to_thread(
            self.sandbox.commands.run,
            command,
            timeout=timeout_ms // 1000,
        )

        logger.debug("command_executed", command=command[:50], exit_code=result.exit_code)
        return result.stdout, result.stderr, result.exit_code

    async def extract_page_content(self, url: str, timeout_ms: int = 30000) -> str:
        if not self.sandbox:
            raise RuntimeError("Sandbox not created. Call create_sandbox() first.")

        extract_script = f"""
python3 -c "
import urllib.request
import html.parser
import re

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
        return '\\n'.join(self.text)

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
                logger.warning(
                    "page_content_extraction_failed",
                    url=url[:50],
                    exit_code=exit_code,
                    stderr=stderr[:200] if stderr else "",
                )
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

            logger.info("page_content_extracted", url=url[:50], content_length=len(content))
            return content

        except Exception as e:
            logger.error("page_content_extraction_error", url=url[:50], error=str(e))
            return f"Error extracting content: {str(e)}"

    async def cleanup(self) -> None:
        if self.sandbox:
            sandbox_id = self.sandbox.sandbox_id
            try:
                try:
                    await asyncio.to_thread(self.sandbox.stream.stop)
                    logger.debug("desktop_stream_stopped", sandbox_id=sandbox_id)
                except Exception as e:
                    logger.debug(
                        "desktop_stream_stop_skipped",
                        sandbox_id=sandbox_id,
                        reason=str(e),
                    )

                await asyncio.to_thread(self.sandbox.kill)
                logger.info("desktop_sandbox_cleaned_up", sandbox_id=sandbox_id)
            except Exception as e:
                logger.warning(
                    "desktop_sandbox_cleanup_failed",
                    sandbox_id=sandbox_id,
                    error=str(e),
                )
            finally:
                self.sandbox = None
                self._browser_launched = False
                self._stream_started = False


def get_screenshot_as_base64(screenshot_bytes: bytes) -> dict:
    """Convert screenshot bytes to base64 format for tool response."""
    return {
        "data": base64.b64encode(screenshot_bytes).decode("utf-8"),
        "type": "image/png",
    }
