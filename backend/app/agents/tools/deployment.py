"""Deployment / Port Exposure Tools for Sandbox.

Provides LangChain tools for exposing sandbox services via public URLs,
enabling users to access dev servers, APIs, and web apps running inside
the sandbox from their browser.
"""

import json
import re
import uuid
from datetime import datetime, timezone

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sandbox.execution_sandbox_manager import get_execution_sandbox_manager

logger = get_logger(__name__)

# Module-level storage for active deployments
# Maps deployment_id -> {port, url, name, sandbox_id, created_at}
_active_deployments: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class DeployExposePortInput(BaseModel):
    """Input schema for deploy_expose_port tool."""

    port: int = Field(
        ...,
        description="Port number of the running service in the sandbox to expose",
    )
    name: str | None = Field(
        default=None,
        description="Optional friendly name for this deployment (e.g., 'frontend', 'api')",
    )
    # Context fields (injected by agent, not provided by LLM)
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )


class DeployGetUrlInput(BaseModel):
    """Input schema for deploy_get_url tool."""

    deployment_id: str = Field(
        ...,
        description="Deployment ID returned by deploy_expose_port",
    )
    # Context fields (injected by agent, not provided by LLM)
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_sandbox_runtime(user_id: str | None, task_id: str | None):
    """Get sandbox runtime and sandbox_id for deployment operations.

    Returns:
        Tuple of (runtime, sandbox_id).
    """
    from app.sandbox.provider import is_provider_available

    available, issue = is_provider_available("execution")
    if not available:
        raise RuntimeError(issue)

    manager = get_execution_sandbox_manager()
    session = await manager.get_or_create_sandbox(
        user_id=user_id,
        task_id=task_id,
    )
    executor = session.executor

    if not executor.sandbox_id:
        raise RuntimeError("Sandbox not available")

    return executor.get_runtime(), session.sandbox_id


def _error_result(**kwargs) -> str:
    """Create a JSON error response."""
    return json.dumps({"success": False, **kwargs})


def _success_result(**kwargs) -> str:
    """Create a JSON success response."""
    return json.dumps({"success": True, **kwargs})


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(args_schema=DeployExposePortInput)
async def deploy_expose_port(
    port: int,
    name: str | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Expose a port from the sandbox to create a temporary public URL.

    Use this to make dev servers, APIs, or web apps accessible externally.
    The service on the specified port must already be running in the sandbox.

    Args:
        port: Port number of the running service to expose
        name: Optional friendly name for this deployment
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with deployment_id, port, url, and name
    """
    logger.info("deploy_expose_port_invoked", port=port, name=name)

    try:
        runtime, sandbox_id = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        logger.error("deploy_expose_port_sandbox_error", error=str(e))
        return _error_result(operation="expose_port", port=port, error=str(e))

    try:
        url = await runtime.get_host_url(port)

        deployment_id = f"deploy_{uuid.uuid4().hex[:8]}"
        deployment_name = name or f"port-{port}"

        _active_deployments[deployment_id] = {
            "port": port,
            "url": url,
            "name": deployment_name,
            "sandbox_id": sandbox_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "deploy_expose_port_completed",
            deployment_id=deployment_id,
            port=port,
            url=url,
            sandbox_id=sandbox_id,
        )

        return _success_result(
            operation="expose_port",
            deployment_id=deployment_id,
            port=port,
            url=url,
            name=deployment_name,
            sandbox_id=sandbox_id,
        )

    except Exception as e:
        logger.error("deploy_expose_port_error", port=port, error=str(e))
        return _error_result(operation="expose_port", port=port, error=str(e))


class DeployToProductionInput(BaseModel):
    """Input schema for deploy_to_production tool."""

    sandbox_id: str | None = Field(
        default=None,
        description="The sandbox ID containing the app. Uses current sandbox if not provided.",
    )
    app_directory: str = Field(
        default="/app",
        description="Directory in sandbox containing the app to deploy",
    )
    platform: str = Field(
        default="vercel",
        description="Deployment platform: 'vercel' or 'netlify'",
    )
    project_name: str | None = Field(
        default=None,
        description="Optional project name for the deployment",
    )
    # Context fields (injected by agent, not provided by LLM)
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only)",
        json_schema_extra={"exclude": True},
    )


@tool(args_schema=DeployToProductionInput)
async def deploy_to_production(
    sandbox_id: str | None = None,
    app_directory: str = "/app",
    platform: str = "vercel",
    project_name: str | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Deploy an app from the sandbox to a production hosting platform.

    Deploys the application to Vercel or Netlify using their CLI tools.
    The app must already be built and ready for deployment inside the sandbox.

    Requires the appropriate token to be set:
    - Vercel: VERCEL_TOKEN environment variable
    - Netlify: NETLIFY_AUTH_TOKEN environment variable

    Args:
        sandbox_id: The sandbox ID containing the app (uses current sandbox if not provided)
        app_directory: Directory in sandbox containing the app (default: /app)
        platform: Deployment platform ('vercel' or 'netlify')
        project_name: Optional project name for the deployment
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        Production URL and deployment status
    """
    logger.info(
        "deploy_to_production_invoked",
        platform=platform,
        app_directory=app_directory,
        project_name=project_name,
    )

    platform_lower = platform.lower()
    if platform_lower not in ("vercel", "netlify"):
        return _error_result(
            operation="deploy_to_production",
            error=f"Unsupported platform: {platform}. Use 'vercel' or 'netlify'.",
        )

    try:
        runtime, sid = await _get_sandbox_runtime(user_id, task_id)
    except RuntimeError as e:
        logger.error("deploy_to_production_sandbox_error", error=str(e))
        return _error_result(operation="deploy_to_production", error=str(e))

    try:
        # Build the deployment command
        if platform_lower == "vercel":
            cmd_parts = [f"cd {app_directory}"]
            deploy_cmd = "npx vercel --yes --prod"
            if project_name:
                deploy_cmd += f" --name {project_name}"
            cmd_parts.append(deploy_cmd)
            cmd = " && ".join(cmd_parts)
            token_env = "VERCEL_TOKEN"
        else:  # netlify
            cmd_parts = [f"cd {app_directory}"]
            deploy_cmd = "npx netlify deploy --prod --dir=."
            if project_name:
                deploy_cmd += f" --site {project_name}"
            cmd_parts.append(deploy_cmd)
            cmd = " && ".join(cmd_parts)
            token_env = "NETLIFY_AUTH_TOKEN"

        # Execute deployment command in sandbox
        result = await runtime.run_command(cmd, timeout=300)

        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.exit_code != 0:
            logger.warning(
                "deploy_to_production_command_failed",
                exit_code=result.exit_code,
                stderr=stderr[:500],
            )

            # Check for missing token
            if "token" in stderr.lower() or "auth" in stderr.lower() or "login" in stderr.lower():
                return _error_result(
                    operation="deploy_to_production",
                    platform=platform_lower,
                    error=f"Authentication failed. Ensure {token_env} environment variable is set in the sandbox.",
                    stderr=stderr[:500],
                )

            return _error_result(
                operation="deploy_to_production",
                platform=platform_lower,
                exit_code=result.exit_code,
                error=f"Deployment command failed with exit code {result.exit_code}",
                stdout=stdout[:1000],
                stderr=stderr[:500],
            )

        # Try to extract the production URL from output
        production_url = None

        # Vercel outputs URLs like https://project-xxx.vercel.app
        # Netlify outputs URLs like https://xxx.netlify.app
        url_pattern = re.compile(r"https?://[^\s]+(?:vercel\.app|netlify\.app)[^\s]*")
        urls = url_pattern.findall(stdout + stderr)
        if urls:
            production_url = urls[-1].rstrip(")")  # Take last URL, strip trailing paren

        deployment_id = f"prod_{uuid.uuid4().hex[:8]}"

        _active_deployments[deployment_id] = {
            "url": production_url,
            "platform": platform_lower,
            "project_name": project_name,
            "sandbox_id": sid,
            "app_directory": app_directory,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            "deploy_to_production_completed",
            deployment_id=deployment_id,
            platform=platform_lower,
            production_url=production_url,
        )

        return _success_result(
            operation="deploy_to_production",
            deployment_id=deployment_id,
            platform=platform_lower,
            production_url=production_url,
            project_name=project_name,
            sandbox_id=sid,
            stdout=stdout[:2000],
        )

    except Exception as e:
        logger.error("deploy_to_production_failed", error=str(e))
        return _error_result(operation="deploy_to_production", error=str(e))


@tool(args_schema=DeployGetUrlInput)
async def deploy_get_url(
    deployment_id: str,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Get the public URL for a previously exposed port.

    Use the deployment_id returned by deploy_expose_port to retrieve
    the URL and deployment details.

    Args:
        deployment_id: Deployment ID from deploy_expose_port result
        user_id: User ID for session management (injected)
        task_id: Task ID for session management (injected)

    Returns:
        JSON string with deployment_id, port, url, name, and status
    """
    logger.info("deploy_get_url_invoked", deployment_id=deployment_id)

    deployment = _active_deployments.get(deployment_id)
    if not deployment:
        logger.warning("deploy_get_url_not_found", deployment_id=deployment_id)
        return _error_result(
            operation="get_url",
            deployment_id=deployment_id,
            error=f"Deployment '{deployment_id}' not found. Active deployments: {list(_active_deployments.keys())}",
        )

    logger.info(
        "deploy_get_url_completed",
        deployment_id=deployment_id,
        url=deployment["url"],
    )

    return _success_result(
        operation="get_url",
        deployment_id=deployment_id,
        port=deployment["port"],
        url=deployment["url"],
        name=deployment["name"],
        sandbox_id=deployment["sandbox_id"],
        created_at=deployment["created_at"],
        status="active",
    )
