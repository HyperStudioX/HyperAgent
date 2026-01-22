"""Sandbox package for E2B sandbox management and operations.

This package contains:
- Code sandbox management (code execution sandboxes)
- Browser sandbox management (browser/desktop sandboxes)
- Sandbox file operations
- Unified metrics for all sandbox managers
- Availability checks for graceful degradation
"""

from typing import Any

from app.config import settings
from app.sandbox.browser_sandbox_manager import (
    BrowserSandboxManager,
    BrowserSandboxSession,
    get_browser_sandbox_manager,
)
from app.sandbox.code_sandbox_manager import (
    CodeSandboxManager,
    CodeSandboxSession,
    get_code_sandbox_manager,
)
from app.sandbox.computer_executor import E2B_DESKTOP_AVAILABLE
from app.sandbox.file import (
    sandbox_file,
    sandbox_file_with_context,
)


def get_sandbox_metrics() -> dict[str, Any]:
    """Get unified metrics from all sandbox managers.

    Returns:
        Dict with metrics from code and browser sandbox managers:
            - code: Metrics from code sandbox manager
            - browser: Metrics from browser sandbox manager
            - totals: Aggregated totals across all managers
    """
    code_manager = get_code_sandbox_manager()
    browser_manager = get_browser_sandbox_manager()

    code_metrics = code_manager.get_metrics()
    browser_metrics = browser_manager.get_metrics()

    return {
        "code": code_metrics,
        "browser": browser_metrics,
        "totals": {
            "active_sessions": (
                code_metrics["active_sessions"] + browser_metrics["active_sessions"]
            ),
            "total_created": (
                code_metrics["total_created"] + browser_metrics["total_created"]
            ),
            "total_cleaned": (
                code_metrics["total_cleaned"] + browser_metrics["total_cleaned"]
            ),
            "total_reused": (
                code_metrics["total_reused"] + browser_metrics["total_reused"]
            ),
            "health_check_failures": (
                code_metrics["health_check_failures"]
                + browser_metrics["health_check_failures"]
            ),
        },
    }


def is_code_sandbox_available() -> bool:
    """Check if code sandbox functionality is available.

    Returns:
        True if E2B API key is configured, False otherwise
    """
    return bool(settings.e2b_api_key)


def is_browser_sandbox_available() -> bool:
    """Check if browser sandbox functionality is available.

    Returns:
        True if E2B Desktop SDK is installed and API key is configured
    """
    return E2B_DESKTOP_AVAILABLE and bool(settings.e2b_api_key)


def get_sandbox_availability() -> dict[str, Any]:
    """Get detailed availability status for all sandbox types.

    Returns:
        Dict with availability information:
            - code_sandbox: Whether code sandbox is available
            - browser_sandbox: Whether browser sandbox is available
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
        "code_sandbox": is_code_sandbox_available(),
        "browser_sandbox": is_browser_sandbox_available(),
        "e2b_api_key_configured": bool(settings.e2b_api_key),
        "e2b_desktop_sdk_installed": E2B_DESKTOP_AVAILABLE,
        "issues": issues,
    }


__all__ = [
    # Code sandbox management
    "CodeSandboxSession",
    "CodeSandboxManager",
    "get_code_sandbox_manager",
    # Browser sandbox management
    "BrowserSandboxSession",
    "BrowserSandboxManager",
    "get_browser_sandbox_manager",
    # Sandbox file operations
    "sandbox_file",
    "sandbox_file_with_context",
    # Metrics
    "get_sandbox_metrics",
    # Availability checks
    "is_code_sandbox_available",
    "is_browser_sandbox_available",
    "get_sandbox_availability",
    "E2B_DESKTOP_AVAILABLE",
]
