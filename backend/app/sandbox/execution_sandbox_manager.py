"""Execution Sandbox Manager for E2B Session Lifecycle.

Provides session-based code execution sandbox lifecycle management, enabling sandbox
sharing across multiple tool calls within the same user/task context.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.sandbox.base_code_executor import BaseCodeExecutor

logger = get_logger(__name__)


def get_default_execution_session_timeout() -> timedelta:
    """Get default execution session timeout from settings."""
    return timedelta(minutes=settings.e2b_session_timeout_minutes)


# Cleanup interval for expired sessions (60 seconds)
CLEANUP_INTERVAL_SECONDS = 60


@dataclass
class ExecutionSandboxSession:
    """Tracks an active code execution sandbox session."""

    executor: BaseCodeExecutor
    session_key: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    timeout: timedelta = field(default_factory=get_default_execution_session_timeout)

    @property
    def sandbox_id(self) -> str | None:
        """Get the underlying sandbox ID."""
        if self.executor:
            return self.executor.sandbox_id
        return None

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > (self.last_accessed + self.timeout)

    def touch(self) -> None:
        """Update last accessed time to prevent expiry."""
        self.last_accessed = datetime.utcnow()


class ExecutionSandboxManager:
    """Manages code execution sandbox sessions across multiple tool invocations.

    Uses a session key (user_id:task_id) to enable sandbox reuse
    within the same context. Provides automatic cleanup of expired
    sessions via background task.
    """

    _instance: "ExecutionSandboxManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the execution sandbox manager."""
        self._sessions: dict[str, ExecutionSandboxSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._session_lock = asyncio.Lock()
        # Metrics counters
        self._total_created: int = 0
        self._total_cleaned: int = 0
        self._total_reused: int = 0
        self._health_check_failures: int = 0

    @classmethod
    def get_instance(cls) -> "ExecutionSandboxManager":
        """Get the singleton instance of ExecutionSandboxManager."""
        if cls._instance is None:
            cls._instance = ExecutionSandboxManager()
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
    ) -> ExecutionSandboxSession:
        """Get an existing sandbox session or create a new one.

        Args:
            user_id: User identifier
            task_id: Task identifier
            timeout: Session timeout (defaults to DEFAULT_EXECUTION_SESSION_TIMEOUT)

        Returns:
            ExecutionSandboxSession with active executor

        Raises:
            ValueError: If E2B API key not configured
        """
        # Validate prerequisites at manager level (fail fast)
        from app.sandbox.provider import is_provider_available

        available, issue = is_provider_available("execution")
        if not available:
            raise ValueError(issue)

        session_key = self.make_session_key(user_id, task_id)
        session_timeout = timeout or get_default_execution_session_timeout()

        async with self._session_lock:
            # Check for existing valid session
            if session_key in self._sessions:
                session = self._sessions[session_key]
                # Perform health check: not expired and sandbox still alive
                if not session.is_expired and await self._is_sandbox_healthy(session):
                    session.touch()
                    self._total_reused += 1
                    logger.info(
                        "execution_sandbox_session_reused",
                        session_key=session_key,
                        sandbox_id=session.sandbox_id,
                    )
                    return session
                else:
                    # Clean up unhealthy or expired session
                    await self._cleanup_session_internal(session_key)

            # Create new session via provider factory
            from app.sandbox.provider import create_code_executor

            executor = create_code_executor()
            await executor.create_sandbox()

            session = ExecutionSandboxSession(
                executor=executor,
                session_key=session_key,
                timeout=session_timeout,
            )
            self._sessions[session_key] = session
            self._total_created += 1

            logger.info(
                "execution_sandbox_session_created",
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
    ) -> ExecutionSandboxSession | None:
        """Get an existing sandbox session without creating one.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            ExecutionSandboxSession if exists and valid, None otherwise
        """
        session_key = self.make_session_key(user_id, task_id)

        async with self._session_lock:
            session = self._sessions.get(session_key)
            if session and not session.is_expired and await self._is_sandbox_healthy(session):
                session.touch()
                return session
            return None

    async def _is_sandbox_healthy(self, session: ExecutionSandboxSession) -> bool:
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
            runtime = session.executor.get_runtime()
            result = await runtime.run_command(
                "echo 'health_check'",
                timeout=5,
            )
            return result.exit_code == 0 and "health_check" in result.stdout
        except Exception as e:
            self._health_check_failures += 1
            logger.warning(
                "execution_sandbox_health_check_failed",
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
                self._total_cleaned += 1
                logger.info(
                    "execution_sandbox_session_cleaned",
                    session_key=session_key,
                    sandbox_id=session.sandbox_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "execution_sandbox_session_cleanup_failed",
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
            logger.info("execution_expired_sessions_cleaned", count=cleaned)

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

        logger.info("execution_all_sessions_cleaned", count=cleaned)
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
                logger.error("execution_cleanup_loop_error", error=str(e))

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
        """
        return {
            "active_sessions": len(self._sessions),
            "total_created": self._total_created,
            "total_cleaned": self._total_cleaned,
            "total_reused": self._total_reused,
            "health_check_failures": self._health_check_failures,
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
                "created_at": session.created_at.isoformat(),
                "last_accessed": session.last_accessed.isoformat(),
                "is_expired": session.is_expired,
            }
            for session in self._sessions.values()
        ]


# Singleton accessor
def get_execution_sandbox_manager() -> ExecutionSandboxManager:
    """Get the global ExecutionSandboxManager instance.

    Returns:
        ExecutionSandboxManager singleton
    """
    return ExecutionSandboxManager.get_instance()
