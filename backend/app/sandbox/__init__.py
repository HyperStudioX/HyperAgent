"""Sandbox package for E2B sandbox management and operations.

This package contains:
- Execution sandbox management (code execution sandboxes)
- Desktop sandbox management (desktop/browser sandboxes)
- Sandbox file operations
- Unified metrics for all sandbox managers
- Availability checks for graceful degradation
"""

from typing import Any

from app.config import settings
from app.sandbox import file_operations
from app.sandbox.app_sandbox_manager import (
    APP_TEMPLATES,
    AppSandboxManager,
    AppSandboxSession,
    get_app_sandbox_manager,
)
from app.sandbox.desktop_executor import E2B_DESKTOP_AVAILABLE
from app.sandbox.desktop_sandbox_manager import (
    DesktopSandboxManager,
    DesktopSandboxSession,
    get_desktop_sandbox_manager,
)
from app.sandbox.execution_sandbox_manager import (
    ExecutionSandboxManager,
    ExecutionSandboxSession,
    get_execution_sandbox_manager,
)
from app.sandbox.file import (
    sandbox_file,
    sandbox_file_with_context,
)


def get_sandbox_metrics() -> dict[str, Any]:
    """Get unified metrics from all sandbox managers.

    Returns:
        Dict with metrics from execution, desktop, and app sandbox managers:
            - execution: Metrics from execution sandbox manager
            - desktop: Metrics from desktop sandbox manager
            - app: Metrics from app sandbox manager
            - totals: Aggregated totals across all managers
    """
    execution_manager = get_execution_sandbox_manager()
    desktop_manager = get_desktop_sandbox_manager()
    app_manager = get_app_sandbox_manager()

    execution_metrics = execution_manager.get_metrics()
    desktop_metrics = desktop_manager.get_metrics()
    app_metrics = app_manager.get_metrics()

    return {
        "execution": execution_metrics,
        "desktop": desktop_metrics,
        "app": app_metrics,
        "totals": {
            "active_sessions": (
                execution_metrics["active_sessions"]
                + desktop_metrics["active_sessions"]
                + app_metrics["active_sessions"]
            ),
            "total_created": (
                execution_metrics["total_created"]
                + desktop_metrics["total_created"]
                + app_metrics["total_created"]
            ),
            "total_cleaned": (
                execution_metrics["total_cleaned"]
                + desktop_metrics["total_cleaned"]
                + app_metrics["total_cleaned"]
            ),
            "total_reused": (
                execution_metrics["total_reused"]
                + desktop_metrics["total_reused"]
                + app_metrics["total_reused"]
            ),
            "health_check_failures": (
                execution_metrics["health_check_failures"]
                + desktop_metrics["health_check_failures"]
                + app_metrics["health_check_failures"]
            ),
        },
    }


def is_execution_sandbox_available() -> bool:
    """Check if execution sandbox functionality is available.

    Returns:
        True if E2B API key is configured, False otherwise
    """
    return bool(settings.e2b_api_key)


def is_desktop_sandbox_available() -> bool:
    """Check if desktop sandbox functionality is available.

    Returns:
        True if E2B Desktop SDK is installed and API key is configured
    """
    return E2B_DESKTOP_AVAILABLE and bool(settings.e2b_api_key)


def get_sandbox_availability() -> dict[str, Any]:
    """Get detailed availability status for all sandbox types.

    Returns:
        Dict with availability information:
            - execution_sandbox: Whether execution sandbox is available
            - desktop_sandbox: Whether desktop sandbox is available
            - e2b_api_key_configured: Whether E2B API key is set
            - e2b_desktop_sdk_installed: Whether e2b-desktop package is installed
            - issues: List of issues preventing sandbox usage
    """
    issues = []

    if not settings.e2b_api_key:
        issues.append("E2B API key not configured (set E2B_API_KEY)")

    if not E2B_DESKTOP_AVAILABLE:
        issues.append("E2B Desktop SDK not installed (pip install e2b-desktop)")

    return {
        "execution_sandbox": is_execution_sandbox_available(),
        "desktop_sandbox": is_desktop_sandbox_available(),
        "e2b_api_key_configured": bool(settings.e2b_api_key),
        "e2b_desktop_sdk_installed": E2B_DESKTOP_AVAILABLE,
        "issues": issues,
    }


def is_app_sandbox_available() -> bool:
    """Check if app sandbox functionality is available.

    Returns:
        True if E2B API key is configured, False otherwise
    """
    return bool(settings.e2b_api_key)


__all__ = [
    # Execution sandbox management
    "ExecutionSandboxSession",
    "ExecutionSandboxManager",
    "get_execution_sandbox_manager",
    # Desktop sandbox management
    "DesktopSandboxSession",
    "DesktopSandboxManager",
    "get_desktop_sandbox_manager",
    # App sandbox management
    "AppSandboxSession",
    "AppSandboxManager",
    "get_app_sandbox_manager",
    "APP_TEMPLATES",
    # Sandbox file operations
    "sandbox_file",
    "sandbox_file_with_context",
    "file_operations",
    # Metrics
    "get_sandbox_metrics",
    # Availability checks
    "is_execution_sandbox_available",
    "is_desktop_sandbox_available",
    "is_app_sandbox_available",
    "get_sandbox_availability",
    "E2B_DESKTOP_AVAILABLE",
]
