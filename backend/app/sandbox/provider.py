"""Sandbox Provider Factory.

Provides factory functions that create the correct executor/runtime
implementation based on the configured sandbox provider (e2b or boxlite).
"""

from app.config import settings
from app.core.logging import get_logger
from app.sandbox.base_code_executor import BaseCodeExecutor
from app.sandbox.base_desktop_executor import BaseDesktopExecutor
from app.sandbox.runtime import SandboxRuntime

logger = get_logger(__name__)


def get_sandbox_provider() -> str:
    """Get the configured sandbox provider name.

    Returns:
        Provider name: "e2b" or "boxlite"
    """
    return settings.sandbox_provider


def is_provider_available(sandbox_type: str = "execution") -> tuple[bool, str]:
    """Check if the configured sandbox provider is available.

    Args:
        sandbox_type: Type of sandbox to check ("execution", "desktop", "app")

    Returns:
        Tuple of (is_available, issue_description)
    """
    provider = get_sandbox_provider()

    if provider == "e2b":
        return _check_e2b_available(sandbox_type)
    elif provider == "boxlite":
        return _check_boxlite_available(sandbox_type)
    else:
        return False, f"Unknown sandbox provider: {provider}"


def _check_e2b_available(sandbox_type: str) -> tuple[bool, str]:
    """Check E2B provider availability."""
    if not settings.e2b_api_key:
        return False, "E2B API key not configured. Set E2B_API_KEY environment variable."

    if sandbox_type == "desktop":
        from app.sandbox.e2b.desktop_executor import E2B_DESKTOP_AVAILABLE

        if not E2B_DESKTOP_AVAILABLE:
            return False, "E2B Desktop not available. Install with: pip install e2b-desktop"

    return True, ""


def _check_boxlite_available(sandbox_type: str) -> tuple[bool, str]:
    """Check BoxLite provider availability."""
    try:
        import boxlite  # noqa: F401

        return True, ""
    except ImportError:
        return False, (
            "BoxLite not installed. Install with: pip install 'hyperagent-api[local-sandbox]'"
        )


def create_code_executor(**kwargs) -> BaseCodeExecutor:
    """Create a code executor for the configured provider.

    Args:
        **kwargs: Provider-specific keyword arguments

    Returns:
        BaseCodeExecutor implementation

    Raises:
        ValueError: If provider is not available
    """
    provider = get_sandbox_provider()

    if provider == "e2b":
        from app.sandbox.e2b.code_executor import E2BSandboxExecutor

        return E2BSandboxExecutor(**kwargs)

    elif provider == "boxlite":
        from app.sandbox.boxlite.code_executor import BoxLiteCodeExecutor

        return BoxLiteCodeExecutor(**kwargs)

    else:
        raise ValueError(f"Unknown sandbox provider: {provider}")


def create_desktop_executor(**kwargs) -> BaseDesktopExecutor:
    """Create a desktop executor for the configured provider.

    Args:
        **kwargs: Provider-specific keyword arguments

    Returns:
        BaseDesktopExecutor implementation

    Raises:
        ValueError: If provider is not available
    """
    provider = get_sandbox_provider()

    if provider == "e2b":
        from app.sandbox.e2b.desktop_executor import E2BDesktopExecutor

        return E2BDesktopExecutor(**kwargs)

    elif provider == "boxlite":
        from app.sandbox.boxlite.desktop_executor import BoxLiteDesktopExecutor

        return BoxLiteDesktopExecutor(**kwargs)

    else:
        raise ValueError(f"Unknown sandbox provider: {provider}")


async def create_app_runtime(**kwargs) -> SandboxRuntime:
    """Create an app sandbox runtime for the configured provider.

    Args:
        **kwargs: Provider-specific keyword arguments

    Returns:
        SandboxRuntime implementation

    Raises:
        ValueError: If provider is not available
    """
    provider = get_sandbox_provider()

    if provider == "e2b":
        from e2b import AsyncSandbox

        from app.middleware.circuit_breaker import CircuitBreakerOpen, get_e2b_breaker
        from app.sandbox.e2b.runtime import E2BRuntime

        if not settings.e2b_api_key:
            raise ValueError("E2B API key not configured. Set E2B_API_KEY environment variable.")

        breaker = get_e2b_breaker()

        try:
            async with breaker.call():
                sandbox = await AsyncSandbox.create(
                    api_key=settings.e2b_api_key,
                    timeout=kwargs.get("timeout", 1800),
                )
            return E2BRuntime(sandbox)
        except CircuitBreakerOpen as e:
            logger.warning(
                "app_sandbox_circuit_open",
                service="e2b",
                retry_after=e.retry_after,
            )
            raise

    elif provider == "boxlite":
        from app.sandbox.boxlite.runtime import BoxLiteRuntime

        return await BoxLiteRuntime.create(
            image=kwargs.get("image", settings.boxlite_app_image),
            cpus=kwargs.get("cpus", settings.boxlite_cpus),
            memory_mib=kwargs.get("memory_mib", settings.boxlite_memory_mib),
            disk_size_gb=kwargs.get("disk_size_gb", settings.boxlite_disk_size_gb),
        )

    else:
        raise ValueError(f"Unknown sandbox provider: {provider}")
