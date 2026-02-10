"""Base Desktop Executor ABC.

Defines the abstract interface for desktop/browser sandbox executors.
All provider implementations (E2B, BoxLite) must extend this class.
"""

import base64
from abc import ABC, abstractmethod
from typing import Literal


def get_screenshot_as_base64(screenshot_bytes: bytes) -> dict:
    """Convert screenshot bytes to base64 format for tool response."""
    return {
        "data": base64.b64encode(screenshot_bytes).decode("utf-8"),
        "type": "image/png",
    }


class BaseDesktopExecutor(ABC):
    """Abstract base class for desktop sandbox executors.

    Provides the interface for browser automation, screenshots, mouse/keyboard
    input, streaming, and content extraction across sandbox providers.
    """

    @abstractmethod
    async def create_sandbox(self) -> str:
        """Create a new desktop sandbox instance.

        Returns:
            Sandbox ID string
        """
        ...

    @abstractmethod
    async def launch_browser(
        self,
        browser: str | None = None,
        wait_ms: int = 10000,
    ) -> None:
        """Launch a browser in the sandbox.

        Args:
            browser: Browser to launch (e.g., "google-chrome", "firefox")
            wait_ms: Time to wait for browser to open in milliseconds
        """
        ...

    @abstractmethod
    async def screenshot(self) -> bytes:
        """Capture a screenshot of the desktop.

        Returns:
            Screenshot as bytes (PNG format)
        """
        ...

    @abstractmethod
    async def click(
        self,
        x: int,
        y: int,
        button: Literal["left", "right", "middle"] = "left",
    ) -> None:
        """Click at a specific position.

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button to click
        """
        ...

    @abstractmethod
    async def double_click(self, x: int, y: int) -> None:
        """Double-click at a specific position.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        ...

    @abstractmethod
    async def type_text(
        self,
        text: str,
        chunk_size: int = 25,
        delay_ms: int = 75,
    ) -> None:
        """Type text using the keyboard.

        Args:
            text: Text to type
            chunk_size: Characters to type per chunk
            delay_ms: Delay between chunks in milliseconds
        """
        ...

    @abstractmethod
    async def type_text_via_clipboard(self, text: str) -> None:
        """Type text, using clipboard paste for non-ASCII characters.

        Args:
            text: Text to type/paste
        """
        ...

    @abstractmethod
    async def press_key(self, key: str | list[str]) -> None:
        """Press a key or key combination.

        Args:
            key: Key to press (e.g., "enter", ["ctrl", "shift", "t"])
        """
        ...

    @abstractmethod
    async def scroll(
        self,
        direction: Literal["up", "down"] = "down",
        amount: int = 3,
    ) -> None:
        """Scroll the page.

        Args:
            direction: Scroll direction
            amount: Number of scroll steps
        """
        ...

    @abstractmethod
    async def move_mouse(self, x: int, y: int) -> None:
        """Move mouse to a specific position.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        ...

    @abstractmethod
    async def drag(
        self,
        from_pos: tuple[int, int],
        to_pos: tuple[int, int],
    ) -> None:
        """Drag from one position to another.

        Args:
            from_pos: Starting position (x, y)
            to_pos: Ending position (x, y)
        """
        ...

    @abstractmethod
    async def wait(self, milliseconds: int) -> None:
        """Wait for a specified time.

        Args:
            milliseconds: Time to wait in milliseconds
        """
        ...

    async def get_stream_url(self, require_auth: bool = True) -> tuple[str, str | None]:
        """Get the desktop stream URL.

        Starts the stream if not already running.

        Args:
            require_auth: Whether to require authentication for the stream

        Returns:
            Tuple of (stream_url, auth_key or None)

        Raises:
            NotImplementedError: If the provider does not support streaming
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support live streaming. "
            "Use screenshot() for visual feedback instead."
        )

    async def stop_stream(self) -> None:
        """Stop the desktop stream.

        Raises:
            NotImplementedError: If the provider does not support streaming
        """
        raise NotImplementedError(f"{type(self).__name__} does not support live streaming.")

    @abstractmethod
    async def run_command(self, command: str, timeout_ms: int = 30000) -> tuple[str, str, int]:
        """Run a shell command in the sandbox.

        Args:
            command: Shell command to execute
            timeout_ms: Command timeout in milliseconds

        Returns:
            Tuple of (stdout, stderr, exit_code)
        """
        ...

    @abstractmethod
    async def extract_page_content(self, url: str, timeout_ms: int = 30000) -> str:
        """Extract text content from a web page.

        Args:
            url: URL to extract content from
            timeout_ms: Timeout in milliseconds

        Returns:
            Extracted text content from the page
        """
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up sandbox resources."""
        ...

    @property
    @abstractmethod
    def sandbox_id(self) -> str | None:
        """Get the sandbox ID, or None if not yet created."""
        ...

    @property
    @abstractmethod
    def browser_launched(self) -> bool:
        """Check if browser has been launched."""
        ...

    @property
    def stream_started(self) -> bool:
        """Check if the stream has been started.

        Default implementation returns False. Providers with streaming
        support should override this.
        """
        return False

    async def __aenter__(self):
        """Context manager entry - creates sandbox."""
        await self.create_sandbox()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleans up sandbox."""
        await self.cleanup()
