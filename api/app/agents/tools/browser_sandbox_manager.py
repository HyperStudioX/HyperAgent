"""Browser Sandbox Manager for E2B Desktop Session Lifecycle.

Provides session-based browser sandbox lifecycle management, enabling sandbox
sharing across multiple tool calls within the same user/task context.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.computer_executor import E2BDesktopExecutor

logger = get_logger(__name__)

# Default session timeout (15 minutes - longer for browser startup)
DEFAULT_BROWSER_SESSION_TIMEOUT = timedelta(minutes=15)

# Cleanup interval for expired sessions (60 seconds)
CLEANUP_INTERVAL_SECONDS = 60


@dataclass
class BrowserSandboxSession:
    """Tracks an active browser sandbox session."""

    executor: E2BDesktopExecutor
    session_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    timeout: timedelta = field(default=DEFAULT_BROWSER_SESSION_TIMEOUT)

    @property
    def sandbox_id(self) -> str | None:
        """Get the underlying sandbox ID."""
        return self.executor.sandbox_id

    @property
    def browser_launched(self) -> bool:
        """Check if browser has been launched in this session."""
        return self.executor.browser_launched

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > (self.last_accessed + self.timeout)

    def touch(self) -> None:
        """Update last accessed time to prevent expiry."""
        self.last_accessed = datetime.utcnow()


class BrowserSandboxManager:
    """Manages browser sandbox sessions across multiple tool invocations.

    Uses a session key (browser:user_id:task_id) to enable sandbox reuse
    within the same context. Provides automatic cleanup of expired
    sessions via background task.
    """

    _instance: "BrowserSandboxManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the browser sandbox manager."""
        self._sessions: dict[str, BrowserSandboxSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._session_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "BrowserSandboxManager":
        """Get the singleton instance of BrowserSandboxManager."""
        if cls._instance is None:
            cls._instance = BrowserSandboxManager()
        return cls._instance

    @staticmethod
    def make_session_key(user_id: str | None, task_id: str | None) -> str:
        """Create a session key from user and task IDs.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            Session key string with browser prefix
        """
        user = user_id or "anonymous"
        task = task_id or "default"
        return f"browser:{user}:{task}"

    async def get_or_create_sandbox(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
        timeout: timedelta | None = None,
        launch_browser: bool = True,
        browser: str | None = None,
    ) -> BrowserSandboxSession:
        """Get an existing browser sandbox session or create a new one.

        Args:
            user_id: User identifier
            task_id: Task identifier
            timeout: Session timeout (defaults to DEFAULT_BROWSER_SESSION_TIMEOUT)
            launch_browser: Whether to launch browser on new sandbox
            browser: Browser to launch (defaults to config setting)

        Returns:
            BrowserSandboxSession with active executor
        """
        session_key = self.make_session_key(user_id, task_id)
        session_timeout = timeout or DEFAULT_BROWSER_SESSION_TIMEOUT

        async with self._session_lock:
            # Check for existing valid session
            if session_key in self._sessions:
                session = self._sessions[session_key]
                if not session.is_expired and session.executor.sandbox:
                    session.touch()
                    logger.info(
                        "browser_sandbox_session_reused",
                        session_key=session_key,
                        sandbox_id=session.sandbox_id,
                        browser_launched=session.browser_launched,
                    )
                    return session
                else:
                    # Clean up expired session
                    await self._cleanup_session_internal(session_key)

            # Create new session
            executor = E2BDesktopExecutor()
            await executor.create_sandbox()

            # Launch browser if requested
            if launch_browser:
                await executor.launch_browser(browser=browser)

            session = BrowserSandboxSession(
                executor=executor,
                session_key=session_key,
                timeout=session_timeout,
            )
            self._sessions[session_key] = session

            logger.info(
                "browser_sandbox_session_created",
                session_key=session_key,
                sandbox_id=session.sandbox_id,
                browser_launched=session.browser_launched,
            )

            # Start cleanup task if not running
            self._ensure_cleanup_task()

            return session

    async def get_session(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
    ) -> BrowserSandboxSession | None:
        """Get an existing browser sandbox session without creating one.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            BrowserSandboxSession if exists and valid, None otherwise
        """
        session_key = self.make_session_key(user_id, task_id)

        async with self._session_lock:
            session = self._sessions.get(session_key)
            if session and not session.is_expired and session.executor.sandbox:
                session.touch()
                return session
            return None

    async def cleanup_session(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
    ) -> bool:
        """Explicitly clean up a browser sandbox session.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            True if session was cleaned up, False if not found
        """
        session_key = self.make_session_key(user_id, task_id)

        async with self._session_lock:
            return await self._cleanup_session_internal(session_key)

    async def _cleanup_session_internal(self, session_key: str) -> bool:
        """Internal cleanup method (assumes lock is held).

        Args:
            session_key: Session key to clean up

        Returns:
            True if session was cleaned up, False if not found
        """
        session = self._sessions.pop(session_key, None)
        if session:
            try:
                await session.executor.cleanup()
                logger.info(
                    "browser_sandbox_session_cleaned",
                    session_key=session_key,
                    sandbox_id=session.sandbox_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "browser_sandbox_session_cleanup_failed",
                    session_key=session_key,
                    error=str(e),
                )
        return False

    async def cleanup_expired(self) -> int:
        """Clean up all expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0

        async with self._session_lock:
            expired_keys = [
                key for key, session in self._sessions.items() if session.is_expired
            ]

            for key in expired_keys:
                if await self._cleanup_session_internal(key):
                    cleaned += 1

        if cleaned > 0:
            logger.info("browser_expired_sessions_cleaned", count=cleaned)

        return cleaned

    async def cleanup_all(self) -> int:
        """Clean up all sessions.

        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0

        async with self._session_lock:
            keys = list(self._sessions.keys())
            for key in keys:
                if await self._cleanup_session_internal(key):
                    cleaned += 1

        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        logger.info("browser_all_sessions_cleaned", count=cleaned)
        return cleaned

    def _ensure_cleanup_task(self) -> None:
        """Ensure the background cleanup task is running."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background loop that periodically cleans up expired sessions."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("browser_cleanup_loop_error", error=str(e))

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_session_info(self) -> list[dict[str, Any]]:
        """Get information about all active sessions for debugging.

        Returns:
            List of session info dicts
        """
        return [
            {
                "session_key": session.session_key,
                "sandbox_id": session.sandbox_id,
                "browser_launched": session.browser_launched,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "is_expired": session.is_expired,
            }
            for session in self._sessions.values()
        ]


# Singleton accessor
def get_browser_sandbox_manager() -> BrowserSandboxManager:
    """Get the global BrowserSandboxManager instance.

    Returns:
        BrowserSandboxManager singleton
    """
    return BrowserSandboxManager.get_instance()
