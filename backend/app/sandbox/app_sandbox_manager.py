"""App Sandbox Manager for E2B Session Lifecycle.

Provides session-based app development sandbox lifecycle management, enabling sandbox
sharing across multiple tool calls within the same user/task context.

Key features:
- Port forwarding for web applications
- Project scaffolding with templates
- Dev server management
- Long-running sessions for iterative development
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from e2b import AsyncSandbox

from app.config import settings
from app.core.logging import get_logger
from app.middleware.circuit_breaker import CircuitBreakerOpen, get_e2b_breaker
from app.sandbox import file_operations

logger = get_logger(__name__)


def get_default_app_session_timeout() -> timedelta:
    """Get default app session timeout from settings (longer than code execution)."""
    # Use a longer timeout for app development (30 minutes default)
    return timedelta(minutes=30)


# Cleanup interval for expired sessions (60 seconds)
CLEANUP_INTERVAL_SECONDS = 60

# Supported app templates
# Note: Using vite@5 instead of vite@latest because E2B sandbox has Node.js 20.9.0
# and Vite 6+ requires Node.js 20.19+ or 22.12+
APP_TEMPLATES = {
    "react": {
        "name": "React (Vite)",
        "scaffold_cmd": "npm create vite@5 app -- --template react && cd app && npm install",
        "start_cmd": "cd app && npm run dev -- --host 0.0.0.0",
        "port": 5173,
    },
    "react-ts": {
        "name": "React TypeScript (Vite)",
        "scaffold_cmd": "npm create vite@5 app -- --template react-ts && cd app && npm install",
        "start_cmd": "cd app && npm run dev -- --host 0.0.0.0",
        "port": 5173,
    },
    "nextjs": {
        "name": "Next.js",
        "scaffold_cmd": "npx create-next-app@14 app --typescript --tailwind --eslint --app --src-dir --use-npm --no-git",
        "start_cmd": "cd app && npm run dev",
        "port": 3000,
    },
    "vue": {
        "name": "Vue 3 (Vite)",
        "scaffold_cmd": "npm create vite@5 app -- --template vue && cd app && npm install",
        "start_cmd": "cd app && npm run dev -- --host 0.0.0.0",
        "port": 5173,
    },
    "express": {
        "name": "Express.js",
        "scaffold_cmd": "mkdir -p app && cd app && npm init -y && npm install express",
        "start_cmd": "cd app && node index.js",
        "port": 3000,
    },
    "fastapi": {
        "name": "FastAPI",
        "scaffold_cmd": "mkdir -p app && cd app && pip install fastapi uvicorn",
        "start_cmd": "cd app && uvicorn main:app --host 0.0.0.0 --port 8000 --reload",
        "port": 8000,
    },
    "flask": {
        "name": "Flask",
        "scaffold_cmd": "mkdir -p app && cd app && pip install flask",
        "start_cmd": "cd app && flask run --host 0.0.0.0 --port 5000",
        "port": 5000,
    },
    "static": {
        "name": "Static HTML",
        "scaffold_cmd": "mkdir -p app && npx -y serve app",
        "start_cmd": "npx -y serve app -l 3000",
        "port": 3000,
    },
}


@dataclass
class AppProcess:
    """Tracks a running app process."""

    pid: int | None = None
    command: str = ""
    started_at: datetime = field(default_factory=datetime.utcnow)
    is_running: bool = False


@dataclass
class AppSandboxSession:
    """Tracks an active app development sandbox session."""

    sandbox: AsyncSandbox
    session_key: str
    template: str = "react"
    project_dir: str = "/home/user/app"
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    timeout: timedelta = field(default_factory=get_default_app_session_timeout)

    # Running process info
    app_process: AppProcess | None = None
    preview_url: str | None = None

    @property
    def sandbox_id(self) -> str | None:
        """Get the underlying sandbox ID."""
        if self.sandbox:
            return self.sandbox.sandbox_id
        return None

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        return datetime.utcnow() > (self.last_accessed + self.timeout)

    def touch(self) -> None:
        """Update last accessed time to prevent expiry."""
        self.last_accessed = datetime.utcnow()


class AppSandboxManager:
    """Manages app development sandbox sessions across multiple tool invocations.

    Uses a session key (user_id:task_id) to enable sandbox reuse
    within the same context. Provides automatic cleanup of expired
    sessions via background task.
    """

    _instance: "AppSandboxManager | None" = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self) -> None:
        """Initialize the app sandbox manager."""
        self._sessions: dict[str, AppSandboxSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None
        self._session_lock = asyncio.Lock()
        # Metrics counters
        self._total_created: int = 0
        self._total_cleaned: int = 0
        self._total_reused: int = 0
        self._health_check_failures: int = 0

    @classmethod
    def get_instance(cls) -> "AppSandboxManager":
        """Get the singleton instance of AppSandboxManager."""
        if cls._instance is None:
            cls._instance = AppSandboxManager()
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
        return f"app:{user}:{task}"

    async def get_or_create_sandbox(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
        template: str = "react",
        timeout: timedelta | None = None,
    ) -> AppSandboxSession:
        """Get an existing sandbox session or create a new one.

        Args:
            user_id: User identifier
            task_id: Task identifier
            template: App template to use (react, nextjs, vue, express, fastapi, etc.)
            timeout: Session timeout (defaults to 30 minutes)

        Returns:
            AppSandboxSession with active sandbox

        Raises:
            ValueError: If E2B API key not configured or invalid template
        """
        # Validate prerequisites at manager level (fail fast)
        if not settings.e2b_api_key:
            raise ValueError(
                "E2B API key not configured. Set E2B_API_KEY environment variable."
            )

        if template not in APP_TEMPLATES:
            raise ValueError(
                f"Invalid template: {template}. Available: {list(APP_TEMPLATES.keys())}"
            )

        session_key = self.make_session_key(user_id, task_id)
        session_timeout = timeout or get_default_app_session_timeout()

        async with self._session_lock:
            # Check for existing valid session
            if session_key in self._sessions:
                session = self._sessions[session_key]
                # Perform health check: not expired and sandbox still alive
                if not session.is_expired and await self._is_sandbox_healthy(session):
                    session.touch()
                    self._total_reused += 1
                    logger.info(
                        "app_sandbox_session_reused",
                        session_key=session_key,
                        sandbox_id=session.sandbox_id,
                    )
                    return session
                else:
                    # Clean up unhealthy or expired session
                    await self._cleanup_session_internal(session_key)

            # Create new sandbox with longer timeout
            breaker = get_e2b_breaker()

            try:
                async with breaker.call():
                    sandbox = await AsyncSandbox.create(
                        api_key=settings.e2b_api_key,
                        timeout=1800,  # 30 minutes for app development
                    )
                logger.info("app_sandbox_created", sandbox_id=sandbox.sandbox_id)
            except CircuitBreakerOpen as e:
                logger.warning(
                    "app_sandbox_circuit_open",
                    service="e2b",
                    retry_after=e.retry_after,
                )
                raise
            except Exception as e:
                logger.error("app_sandbox_creation_failed", error=str(e))
                raise

            session = AppSandboxSession(
                sandbox=sandbox,
                session_key=session_key,
                template=template,
                timeout=session_timeout,
            )
            self._sessions[session_key] = session
            self._total_created += 1

            logger.info(
                "app_sandbox_session_created",
                session_key=session_key,
                sandbox_id=session.sandbox_id,
                template=template,
            )

            # Start cleanup task if not running
            self._ensure_cleanup_task()

            return session

    async def scaffold_project(
        self,
        session: AppSandboxSession,
        template: str | None = None,
    ) -> dict[str, Any]:
        """Scaffold a new project in the sandbox.

        Args:
            session: Active sandbox session
            template: Template to use (defaults to session template)

        Returns:
            Dict with scaffold result info
        """
        template = template or session.template
        template_config = APP_TEMPLATES.get(template)

        if not template_config:
            return {
                "success": False,
                "error": f"Unknown template: {template}",
            }

        logger.info(
            "app_scaffold_starting",
            template=template,
            sandbox_id=session.sandbox_id,
        )

        try:
            # Run scaffold command
            result = await session.sandbox.commands.run(
                template_config["scaffold_cmd"],
                timeout=300,  # 5 minutes for scaffolding
                cwd="/home/user",
            )

            if result.exit_code != 0:
                logger.error(
                    "app_scaffold_failed",
                    template=template,
                    exit_code=result.exit_code,
                    stderr=result.stderr,
                )
                return {
                    "success": False,
                    "error": result.stderr or "Scaffold command failed",
                    "exit_code": result.exit_code,
                }

            session.template = template
            session.project_dir = "/home/user/app"

            logger.info(
                "app_scaffold_completed",
                template=template,
                sandbox_id=session.sandbox_id,
            )

            return {
                "success": True,
                "template": template,
                "project_dir": session.project_dir,
                "message": f"Project scaffolded with {template_config['name']} template",
            }

        except Exception as e:
            logger.error("app_scaffold_error", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def start_dev_server(
        self,
        session: AppSandboxSession,
        custom_command: str | None = None,
        port: int | None = None,
        max_wait_seconds: int = 60,
    ) -> dict[str, Any]:
        """Start the development server and return the preview URL.

        Args:
            session: Active sandbox session
            custom_command: Custom start command (uses template default if not provided)
            port: Custom port (uses template default if not provided)
            max_wait_seconds: Maximum time to wait for server to be ready (default 60s)

        Returns:
            Dict with server info including preview URL
        """
        template_config = APP_TEMPLATES.get(session.template, APP_TEMPLATES["react"])
        start_cmd = custom_command or template_config["start_cmd"]
        server_port = port or template_config["port"]

        logger.info(
            "app_dev_server_starting",
            command=start_cmd,
            port=server_port,
            sandbox_id=session.sandbox_id,
        )

        try:
            # Stop any existing process
            if session.app_process and session.app_process.is_running:
                await self.stop_dev_server(session)

            # Get the public URL for the port first (before starting server)
            preview_url = session.sandbox.get_host(server_port)

            # Start the dev server using E2B's background mode
            # The background=True flag runs the command asynchronously
            logger.info(
                "app_dev_server_launching",
                command=start_cmd,
                sandbox_id=session.sandbox_id,
            )

            # Use setsid with bash -c to create a new session and disown the process
            # This ensures the process continues running even after the command returns
            # We need to wrap in bash -c because setsid needs an executable, not shell built-ins
            background_cmd = f"setsid bash -c '{start_cmd} > /tmp/dev_server.log 2>&1' &"
            result = await session.sandbox.commands.run(
                background_cmd,
                timeout=30,
                cwd="/home/user",
            )

            logger.info(
                "app_dev_server_background_started",
                exit_code=result.exit_code,
                stdout=result.stdout[:200] if result.stdout else "",
                stderr=result.stderr[:200] if result.stderr else "",
                sandbox_id=session.sandbox_id,
            )

            # Store process info
            session.app_process = AppProcess(
                pid=None,  # PID not easily available with background process
                command=start_cmd,
                is_running=True,
            )
            session.preview_url = f"https://{preview_url}"

            # Give the server a moment to initialize before polling
            await asyncio.sleep(2)

            # Poll to check if the server is actually listening on the port
            server_ready = False
            poll_interval = 2  # seconds between checks
            max_attempts = max_wait_seconds // poll_interval

            logger.info(
                "app_dev_server_waiting_for_port",
                port=server_port,
                max_wait_seconds=max_wait_seconds,
                sandbox_id=session.sandbox_id,
            )

            for attempt in range(max_attempts):
                # Check if something is listening on the port using multiple methods
                # Try: 1) curl, 2) /dev/tcp (bash built-in), 3) lsof, 4) ss
                port_check_script = f"""
if curl -s --connect-timeout 2 http://localhost:{server_port} >/dev/null 2>&1; then
    echo 'PORT_OPEN'
elif (echo >/dev/tcp/localhost/{server_port}) 2>/dev/null; then
    echo 'PORT_OPEN'
elif lsof -i:{server_port} -sTCP:LISTEN >/dev/null 2>&1; then
    echo 'PORT_OPEN'
elif ss -tlnp | grep -q ':{server_port} ' 2>/dev/null; then
    echo 'PORT_OPEN'
else
    echo 'PORT_CLOSED'
fi
"""
                check_result = await session.sandbox.commands.run(
                    port_check_script,
                    timeout=10,
                    cwd="/home/user",
                )

                if check_result.stdout and "PORT_OPEN" in check_result.stdout:
                    server_ready = True
                    logger.info(
                        "app_dev_server_port_ready",
                        port=server_port,
                        attempt=attempt + 1,
                        sandbox_id=session.sandbox_id,
                    )
                    break

                # Also check if the process crashed by looking at the log
                if attempt > 0 and attempt % 5 == 0:
                    log_result = await session.sandbox.commands.run(
                        "tail -20 /tmp/dev_server.log 2>/dev/null || echo 'No log yet'",
                        timeout=5,
                        cwd="/home/user",
                    )
                    logger.debug(
                        "app_dev_server_log_check",
                        attempt=attempt + 1,
                        log_tail=log_result.stdout[:500] if log_result.stdout else "empty",
                    )

                await asyncio.sleep(poll_interval)

            if not server_ready:
                # Get the server log to help debug
                log_result = await session.sandbox.commands.run(
                    "cat /tmp/dev_server.log 2>/dev/null || echo 'No log available'",
                    timeout=5,
                    cwd="/home/user",
                )
                error_log = log_result.stdout[:2000] if log_result.stdout else "No log"

                logger.warning(
                    "app_dev_server_not_ready",
                    port=server_port,
                    max_wait_seconds=max_wait_seconds,
                    server_log=error_log,
                    sandbox_id=session.sandbox_id,
                )

                # Still return the URL, but indicate the server might not be ready
                return {
                    "success": True,  # Sandbox is running, just server might be slow
                    "preview_url": session.preview_url,
                    "port": server_port,
                    "command": start_cmd,
                    "message": (
                        f"Dev server starting at {session.preview_url} "
                        "(may take a moment to be ready)"
                    ),
                    "warning": "Server port not yet responding. It may still be starting up.",
                    "server_log": error_log,
                }

            logger.info(
                "app_dev_server_started",
                preview_url=session.preview_url,
                sandbox_id=session.sandbox_id,
            )

            return {
                "success": True,
                "preview_url": session.preview_url,
                "port": server_port,
                "command": start_cmd,
                "message": f"Dev server running at {session.preview_url}",
            }

        except Exception as e:
            logger.error("app_dev_server_start_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def stop_dev_server(
        self,
        session: AppSandboxSession,
    ) -> dict[str, Any]:
        """Stop the running development server.

        Args:
            session: Active sandbox session

        Returns:
            Dict with stop result
        """
        if not session.app_process or not session.app_process.is_running:
            return {
                "success": True,
                "message": "No server running",
            }

        try:
            # Kill any node/python processes running on the expected port
            template_config = APP_TEMPLATES.get(session.template, {})
            port = template_config.get("port", 3000)

            # More comprehensive kill commands to handle nohup-launched processes
            kill_commands = [
                f"fuser -k {port}/tcp 2>/dev/null || true",  # Kill process using the port
                "pkill -f 'vite' || true",  # Kill vite processes
                "pkill -f 'npm run dev' || true",  # Kill npm dev processes
                f"pkill -f 'node.*{port}' || true",  # Kill node processes on port
                f"pkill -f 'python.*{port}' || true",  # Kill python processes on port
            ]

            for cmd in kill_commands:
                await session.sandbox.commands.run(cmd, timeout=5)

            session.app_process.is_running = False
            session.preview_url = None

            logger.info(
                "app_dev_server_stopped",
                sandbox_id=session.sandbox_id,
            )

            return {
                "success": True,
                "message": "Dev server stopped",
            }

        except Exception as e:
            logger.error("app_dev_server_stop_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def write_file(
        self,
        session: AppSandboxSession,
        path: str,
        content: str,
    ) -> dict[str, Any]:
        """Write a file to the sandbox.

        Args:
            session: Active sandbox session
            path: File path (relative to project dir or absolute)
            content: File content

        Returns:
            Dict with write result
        """
        # Make path absolute if relative
        if not path.startswith("/"):
            path = f"{session.project_dir}/{path}"

        # Use shared file operations
        return await file_operations.write_file(session.sandbox, path, content, is_binary=False)

    async def read_file(
        self,
        session: AppSandboxSession,
        path: str,
    ) -> dict[str, Any]:
        """Read a file from the sandbox.

        Args:
            session: Active sandbox session
            path: File path (relative to project dir or absolute)

        Returns:
            Dict with file content
        """
        # Make path absolute if relative
        if not path.startswith("/"):
            path = f"{session.project_dir}/{path}"

        # Use shared file operations
        return await file_operations.read_file(session.sandbox, path)

    async def list_files(
        self,
        session: AppSandboxSession,
        path: str = "",
    ) -> dict[str, Any]:
        """List files in a directory.

        Args:
            session: Active sandbox session
            path: Directory path (relative to project dir or absolute)

        Returns:
            Dict with file listing
        """
        # Make path absolute if relative
        if not path:
            path = session.project_dir
        elif not path.startswith("/"):
            path = f"{session.project_dir}/{path}"

        # Use shared file operations
        return await file_operations.list_directory(session.sandbox, path)

    async def install_dependencies(
        self,
        session: AppSandboxSession,
        packages: list[str],
        package_manager: Literal["npm", "pip"] = "npm",
    ) -> dict[str, Any]:
        """Install dependencies in the sandbox.

        Args:
            session: Active sandbox session
            packages: List of packages to install
            package_manager: Package manager to use (npm or pip)

        Returns:
            Dict with installation result
        """
        if not packages:
            return {
                "success": True,
                "message": "No packages to install",
            }

        packages_str = " ".join(packages)

        if package_manager == "npm":
            cmd = f"cd {session.project_dir} && npm install {packages_str}"
        elif package_manager == "pip":
            cmd = f"pip install {packages_str}"
        else:
            return {
                "success": False,
                "error": f"Unknown package manager: {package_manager}",
            }

        logger.info(
            "app_installing_deps",
            packages=packages,
            manager=package_manager,
            sandbox_id=session.sandbox_id,
        )

        try:
            result = await session.sandbox.commands.run(cmd, timeout=300)

            if result.exit_code != 0:
                return {
                    "success": False,
                    "error": result.stderr or "Installation failed",
                    "stdout": result.stdout,
                }

            logger.info(
                "app_deps_installed",
                packages=packages,
                sandbox_id=session.sandbox_id,
            )

            return {
                "success": True,
                "packages": packages,
                "message": f"Installed {len(packages)} package(s)",
            }

        except Exception as e:
            logger.error("app_install_deps_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def run_command(
        self,
        session: AppSandboxSession,
        command: str,
        timeout: int = 60,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        """Run an arbitrary command in the sandbox.

        Args:
            session: Active sandbox session
            command: Command to run
            timeout: Command timeout in seconds
            cwd: Working directory (defaults to project dir)

        Returns:
            Dict with command result
        """
        working_dir = cwd or session.project_dir

        try:
            result = await session.sandbox.commands.run(
                command,
                timeout=timeout,
                cwd=working_dir,
            )

            return {
                "success": result.exit_code == 0,
                "exit_code": result.exit_code,
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
            }

        except Exception as e:
            logger.error("app_run_command_failed", command=command, error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    async def get_session(
        self,
        user_id: str | None = None,
        task_id: str | None = None,
    ) -> AppSandboxSession | None:
        """Get an existing sandbox session without creating one.

        Args:
            user_id: User identifier
            task_id: Task identifier

        Returns:
            AppSandboxSession if exists and valid, None otherwise
        """
        session_key = self.make_session_key(user_id, task_id)

        async with self._session_lock:
            session = self._sessions.get(session_key)
            if session and not session.is_expired and await self._is_sandbox_healthy(session):
                session.touch()
                return session
            return None

    async def _is_sandbox_healthy(self, session: AppSandboxSession) -> bool:
        """Check if a sandbox session is still healthy and responsive.

        Args:
            session: The session to check

        Returns:
            True if sandbox is healthy, False otherwise
        """
        if not session.sandbox:
            return False

        try:
            # Perform a lightweight health check
            result = await session.sandbox.commands.run(
                "echo 'health_check'",
                timeout=5,
            )
            return result.exit_code == 0 and "health_check" in (result.stdout or "")
        except Exception as e:
            self._health_check_failures += 1
            logger.warning(
                "app_sandbox_health_check_failed",
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
                await session.sandbox.kill()
                self._total_cleaned += 1
                logger.info(
                    "app_sandbox_session_cleaned",
                    session_key=session_key,
                    sandbox_id=session.sandbox_id,
                )
                return True
            except Exception as e:
                logger.warning(
                    "app_sandbox_session_cleanup_failed",
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
            logger.info("app_expired_sessions_cleaned", count=cleaned)

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

        logger.info("app_all_sessions_cleaned", count=cleaned)
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
                logger.error("app_cleanup_loop_error", error=str(e))

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self._sessions)

    def get_metrics(self) -> dict[str, Any]:
        """Get sandbox manager metrics.

        Returns:
            Dict with metrics
        """
        return {
            "active_sessions": len(self._sessions),
            "total_created": self._total_created,
            "total_cleaned": self._total_cleaned,
            "total_reused": self._total_reused,
            "health_check_failures": self._health_check_failures,
        }

    def get_available_templates(self) -> dict[str, dict[str, Any]]:
        """Get available app templates.

        Returns:
            Dict of template name to template info
        """
        return {
            name: {"name": config["name"], "port": config["port"]}
            for name, config in APP_TEMPLATES.items()
        }


# Singleton accessor
def get_app_sandbox_manager() -> AppSandboxManager:
    """Get the global AppSandboxManager instance.

    Returns:
        AppSandboxManager singleton
    """
    return AppSandboxManager.get_instance()
