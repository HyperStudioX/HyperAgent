"""Desktop Sandbox Manager for E2B Desktop Session Lifecycle.

Provides session-based desktop sandbox lifecycle management, enabling sandbox
sharing across multiple tool calls within the same user/task context.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.sandbox.base_desktop_executor import BaseDesktopExecutor

logger = get_logger(__name__)


def get_default_desktop_session_timeout() -> timedelta:
    """Get default desktop session timeout from settings."""
    return timedelta(minutes=settings.e2b_desktop_session_timeout_minutes)


# Cleanup interval for expired sessions (60 seconds)
CLEANUP_INTERVAL_SECONDS = 60


@dataclass
class DesktopSandboxSession:
    """Tracks an active desktop sandbox session."""

    executor: BaseDesktopExecutor
    session_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    timeout: timedelta = field(default_factory=get_default_desktop_session_timeout)
    # Stream state tracking
    _stream_url: str | None = field(default=None, repr=False)
    _stream_auth_key: str | None = field(default=None, repr=False)
    _stream_started: bool = field(default=False, repr=False)
    _stream_ready: bool = field(default=False, repr=False)

    @property
    def sandbox_id(self) -> str | None:
        """Get the underlying sandbox ID."""
        return self.executor.sandbox_id

    @property
    def browser_launched(self) -> bool:
        """Check if browser has been launched in this session."""
        return self.executor.browser_launched

    @property
    def stream_url(self) -> str | None:
        """Get the stream URL if available."""
        return self._stream_url

    @property
    def stream_auth_key(self) -> str | None:
        """Get the stream auth key if available."""
        return self._stream_auth_key

    @property
    def is_stream_started(self) -> bool:
        """Check if the stream has been started."""
        return self._stream_started

    @property
    def is_stream_ready(self) -> bool:
        """Check if the stream is ready for viewing."""
        return self._stream_ready

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > (self.last_accessed + self.timeout)

    def touch(self) -> None:
        """Update last accessed time to prevent expiry."""
        self.last_accessed = datetime.utcnow()

    def set_stream_info(self, stream_url: str, auth_key: str | None) -> None:
        """Set the stream information after starting.

        Args:
            stream_url: The URL to view the stream
            auth_key: Optional authentication key
        """
        self._stream_url = stream_url
        self._stream_auth_key = auth_key
        self._stream_started = True

    def mark_stream_ready(self) -> None:
        """Mark the stream as ready for viewing."""
        self._stream_ready = True


class DesktopSandboxManager:
    """Manages desktop sandbox sessions across multiple tool invocations.

    Uses a session key (desktop:user_id:task_id) to enable sandbox reuse
    within the same context. Provides automatic cleanup of expired
    sessions via background task.
    """

    _instance: "DesktopSandboxManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the desktop sandbox manager."""
        self._sessions: dict[str, DesktopSandboxSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._session_lock = asyncio.Lock()
        # Metrics counters
        self._total_created: int = 0
        self._total_cleaned: int = 0
        self._total_reused: int = 0
        self._health_check_failures: int = 0

    @classmethod
    def get_instance(cls) -> "DesktopSandboxManager":
        """Get the singleton instance of DesktopSandboxManager."""
        if cls._instance is None:
            cls._instance = DesktopSandboxManager()
        return cls._instance

    @staticmethod
    def _is_provider_available() -> bool:
        """Check if the desktop provider is available."""
        from app.sandbox.provider import is_provider_available

        available, _ = is_provider_available("desktop")
        return available

    @staticmethod
    def make_session_key(user_id: str | None, task_id: str | None) -> str:
        """Create a session key from user and task IDs.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            Session key string with desktop prefix
        """
        user = user_id or "anonymous"
        task = task_id or "default"
        return f"desktop:{user}:{task}"

    async def get_or_create_sandbox(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
        timeout: timedelta | None = None,
        launch_browser: bool = True,
        browser: str | None = None,
    ) -> DesktopSandboxSession:
        """Get an existing desktop sandbox session or create a new one.

        Args:
            user_id: User identifier
            task_id: Task identifier
            timeout: Session timeout (defaults to DEFAULT_DESKTOP_SESSION_TIMEOUT)
            launch_browser: Whether to launch browser on new sandbox
            browser: Browser to launch (defaults to config setting)

        Returns:
            DesktopSandboxSession with active executor

        Raises:
            ValueError: If E2B Desktop not available or API key not configured
        """
        # Validate prerequisites at manager level (fail fast)
        from app.sandbox.provider import is_provider_available

        available, issue = is_provider_available("desktop")
        if not available:
            raise ValueError(issue)

        session_key = self.make_session_key(user_id, task_id)
        session_timeout = timeout or get_default_desktop_session_timeout()

        async with self._session_lock:
            # Check for existing valid session
            if session_key in self._sessions:
                session = self._sessions[session_key]
                # Perform health check: not expired and sandbox still alive
                if not session.is_expired and await self._is_sandbox_healthy(session):
                    session.touch()
                    if launch_browser and not session.browser_launched:
                        await session.executor.launch_browser(browser=browser)
                    self._total_reused += 1
                    logger.info(
                        "desktop_sandbox_session_reused",
                        session_key=session_key,
                        sandbox_id=session.sandbox_id,
                        browser_launched=session.browser_launched,
                    )
                    return session
                else:
                    # Clean up unhealthy or expired session
                    await self._cleanup_session_internal(session_key)

            # Create new session via provider factory
            from app.sandbox.provider import create_desktop_executor

            executor = create_desktop_executor()
            await executor.create_sandbox()

            # Launch browser if requested
            if launch_browser:
                await executor.launch_browser(browser=browser)

            session = DesktopSandboxSession(
                executor=executor,
                session_key=session_key,
                timeout=session_timeout,
            )
            self._sessions[session_key] = session
            self._total_created += 1

            logger.info(
                "desktop_sandbox_session_created",
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
    ) -> DesktopSandboxSession | None:
        """Get an existing desktop sandbox session without creating one.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            DesktopSandboxSession if exists and valid, None otherwise
        """
        session_key = self.make_session_key(user_id, task_id)

        async with self._session_lock:
            session = self._sessions.get(session_key)
            if session and not session.is_expired and await self._is_sandbox_healthy(session):
                session.touch()
                return session
            return None

    async def ensure_stream_ready(
        self,
        session: DesktopSandboxSession,
        wait_ms: int | None = None,
    ) -> tuple[str | None, str | None]:
        """Ensure the desktop stream is started and ready for viewing.

        This method should be called before performing any desktop actions to ensure
        the user can see the actions in the live stream. It:
        1. Starts the stream if not already started
        2. Waits for the configured time to allow frontend to connect
        3. Marks the session as stream-ready

        For providers that don't support streaming (e.g., BoxLite), returns (None, None).

        Args:
            session: The desktop session
            wait_ms: Optional wait time in ms (defaults to settings.e2b_desktop_stream_ready_wait_ms)

        Returns:
            Tuple of (stream_url, auth_key). Both may be None if streaming is unsupported.
        """
        # If stream is already ready, just return the existing info
        if session.is_stream_ready and session.stream_url:
            logger.debug(
                "stream_already_ready",
                session_key=session.session_key,
                sandbox_id=session.sandbox_id,
            )
            return session.stream_url, session.stream_auth_key

        # Start stream if not started
        if not session.is_stream_started:
            logger.info(
                "starting_desktop_stream",
                session_key=session.session_key,
                sandbox_id=session.sandbox_id,
            )
            try:
                stream_url, auth_key = await session.executor.get_stream_url(require_auth=True)
                session.set_stream_info(stream_url, auth_key)
                logger.info(
                    "desktop_stream_started",
                    session_key=session.session_key,
                    sandbox_id=session.sandbox_id,
                )
            except NotImplementedError:
                # Provider does not support live streaming (e.g., BoxLite)
                # Mark as ready with no stream URL; frontend should use screenshots
                session.mark_stream_ready()
                logger.info(
                    "desktop_stream_not_supported",
                    session_key=session.session_key,
                    sandbox_id=session.sandbox_id,
                )
                return None, None

        # Wait for stream to be ready (allow frontend to connect)
        stream_wait = wait_ms or settings.e2b_desktop_stream_ready_wait_ms
        logger.info(
            "waiting_for_stream_ready",
            session_key=session.session_key,
            sandbox_id=session.sandbox_id,
            wait_ms=stream_wait,
        )
        await session.executor.wait(stream_wait)

        # Mark as ready
        session.mark_stream_ready()
        logger.info(
            "desktop_stream_ready",
            session_key=session.session_key,
            sandbox_id=session.sandbox_id,
        )

        return session.stream_url, session.stream_auth_key

    async def _is_sandbox_healthy(self, session: DesktopSandboxSession) -> bool:
        """Check if a sandbox session is still healthy and responsive.

        Args:
            session: The session to check

        Returns:
            True if sandbox is healthy, False otherwise
        """
        if not session.executor.sandbox_id:
            return False

        try:
            # Perform a lightweight health check by running a simple command
            stdout, stderr, exit_code = await session.executor.run_command(
                "echo 'health_check'",
                timeout_ms=5000,  # 5 second timeout for health check
            )
            return exit_code == 0 and "health_check" in stdout
        except Exception as e:
            self._health_check_failures += 1
            logger.warning(
                "desktop_sandbox_health_check_failed",
                session_key=session.session_key,
                sandbox_id=session.sandbox_id,
                error=str(e),
            )
            return False

    async def cleanup_session(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
    ) -> bool:
        """Explicitly clean up a desktop sandbox session.

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
                self._total_cleaned += 1
                logger.info(
                    "desktop_sandbox_session_cleaned",
                    session_key=session_key,
                    sandbox_id=session.sandbox_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "desktop_sandbox_session_cleanup_failed",
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
            expired_keys = [key for key, session in self._sessions.items() if session.is_expired]

            for key in expired_keys:
                if await self._cleanup_session_internal(key):
                    cleaned += 1

        if cleaned > 0:
            logger.info("desktop_expired_sessions_cleaned", count=cleaned)

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

        logger.info("desktop_all_sessions_cleaned", count=cleaned)
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
                logger.error("desktop_cleanup_loop_error", error=str(e))

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_metrics(self) -> dict[str, Any]:
        """Get sandbox manager metrics.

        Returns:
            Dict with metrics including:
                - active_sessions: Current number of active sessions
                - total_created: Total sessions created since startup
                - total_cleaned: Total sessions cleaned up since startup
                - total_reused: Total session reuses since startup
                - health_check_failures: Total health check failures
                - e2b_desktop_available: Whether E2B Desktop SDK is available
        """
        return {
            "active_sessions": len(self._sessions),
            "total_created": self._total_created,
            "total_cleaned": self._total_cleaned,
            "total_reused": self._total_reused,
            "health_check_failures": self._health_check_failures,
            "desktop_provider_available": self._is_provider_available(),
        }

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
                "stream_started": session.is_stream_started,
                "stream_ready": session.is_stream_ready,
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "is_expired": session.is_expired,
            }
            for session in self._sessions.values()
        ]


# Singleton accessor
def get_desktop_sandbox_manager() -> DesktopSandboxManager:
    """Get the global DesktopSandboxManager instance.

    Returns:
        DesktopSandboxManager singleton
    """
    return DesktopSandboxManager.get_instance()
