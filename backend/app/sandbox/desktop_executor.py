"""Desktop Executor — re-export shim.

This module re-exports from the E2B provider for backward compatibility.
All new code should import from app.sandbox.e2b.desktop_executor or use
the base class from app.sandbox.base_desktop_executor.
"""

from app.sandbox.base_desktop_executor import get_screenshot_as_base64
from app.sandbox.e2b.desktop_executor import (
    E2B_DESKTOP_AVAILABLE,
    E2BDesktopExecutor,
)

__all__ = [
    "E2BDesktopExecutor",
    "E2B_DESKTOP_AVAILABLE",
    "get_screenshot_as_base64",
]
