"""Sandbox Manager for E2B Session Lifecycle.

Provides session-based sandbox lifecycle management, enabling sandbox
sharing across multiple tool calls within the same user/task context.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.logging import get_logger
from app.services.e2b_executor import E2BSandboxExecutor

logger = get_logger(__name__)

# Default session timeout (10 minutes)
DEFAULT_SESSION_TIMEOUT = timedelta(minutes=10)

# Cleanup interval for expired sessions (60 seconds)
CLEANUP_INTERVAL_SECONDS = 60


@dataclass
class SandboxSession:
    """Tracks an active sandbox session."""

    executor: E2BSandboxExecutor
    session_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    timeout: timedelta = field(default=DEFAULT_SESSION_TIMEOUT)

    @property
    def sandbox_id(self) -> str | None:
        """Get the underlying sandbox ID."""
        if self.executor and self.executor.sandbox:
            return self.executor.sandbox.sandbox_id
        return None

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > (self.last_accessed + self.timeout)

    def touch(self) -> None:
        """Update last accessed time to prevent expiry."""
        self.last_accessed = datetime.utcnow()


class SandboxManager:
    """Manages sandbox sessions across multiple tool invocations.

    Uses a session key (user_id:task_id) to enable sandbox reuse
    within the same context. Provides automatic cleanup of expired
    sessions via background task.
    """

    _instance: "SandboxManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the sandbox manager."""
        self._sessions: dict[str, SandboxSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._session_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "SandboxManager":
        """Get the singleton instance of SandboxManager."""
        if cls._instance is None:
            cls._instance = SandboxManager()
        return cls._instance

    @staticmethod
    def make_session_key(user_id: str | None, task_id: str | None) -> str:
        """Create a session key from user and task IDs.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            Session key string
        """
        user = user_id or "anonymous"
        task = task_id or "default"
        return f"{user}:{task}"

    async def get_or_create_sandbox(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
        timeout: timedelta | None = None,
    ) -> SandboxSession:
        """Get an existing sandbox session or create a new one.

        Args:
            user_id: User identifier
            task_id: Task identifier
            timeout: Session timeout (defaults to DEFAULT_SESSION_TIMEOUT)

        Returns:
            SandboxSession with active executor
        """
        session_key = self.make_session_key(user_id, task_id)
        session_timeout = timeout or DEFAULT_SESSION_TIMEOUT

        async with self._session_lock:
            # Check for existing valid session
            if session_key in self._sessions:
                session = self._sessions[session_key]
                if not session.is_expired and session.executor.sandbox:
                    session.touch()
                    logger.info(
                        "sandbox_session_reused",
                        session_key=session_key,
                        sandbox_id=session.sandbox_id,
                    )
                    return session
                else:
                    # Clean up expired session
                    await self._cleanup_session_internal(session_key)

            # Create new session
            executor = E2BSandboxExecutor()
            await executor.create_sandbox()

            session = SandboxSession(
                executor=executor,
                session_key=session_key,
                timeout=session_timeout,
            )
            self._sessions[session_key] = session

            logger.info(
                "sandbox_session_created",
                session_key=session_key,
                sandbox_id=session.sandbox_id,
            )

            # Start cleanup task if not running
            self._ensure_cleanup_task()

            return session

    async def get_session(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
    ) -> SandboxSession | None:
        """Get an existing sandbox session without creating one.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            SandboxSession if exists and valid, None otherwise
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
        """Explicitly clean up a sandbox session.

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
                    "sandbox_session_cleaned",
                    session_key=session_key,
                    sandbox_id=session.sandbox_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "sandbox_session_cleanup_failed",
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
                key for key, session in self._sessions.items()
                if session.is_expired
            ]

            for key in expired_keys:
                if await self._cleanup_session_internal(key):
                    cleaned += 1

        if cleaned > 0:
            logger.info("expired_sessions_cleaned", count=cleaned)

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

        logger.info("all_sessions_cleaned", count=cleaned)
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
                logger.error("cleanup_loop_error", error=str(e))

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
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "is_expired": session.is_expired,
            }
            for session in self._sessions.values()
        ]


# Singleton accessor
def get_sandbox_manager() -> SandboxManager:
    """Get the global SandboxManager instance.

    Returns:
        SandboxManager singleton
    """
    return SandboxManager.get_instance()
