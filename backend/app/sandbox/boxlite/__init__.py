"""BoxLite local sandbox provider.

Contains BoxLite-specific implementations of sandbox runtime, code executor,
and desktop executor for local Docker-based sandbox execution.
"""

try:
    from app.sandbox.boxlite.code_executor import BoxLiteCodeExecutor
    from app.sandbox.boxlite.desktop_executor import BoxLiteDesktopExecutor
    from app.sandbox.boxlite.runtime import BoxLiteRuntime

    BOXLITE_AVAILABLE = True
except ImportError:
    BOXLITE_AVAILABLE = False
    BoxLiteRuntime = None  # type: ignore[assignment,misc]
    BoxLiteCodeExecutor = None  # type: ignore[assignment,misc]
    BoxLiteDesktopExecutor = None  # type: ignore[assignment,misc]

__all__ = [
    "BOXLITE_AVAILABLE",
    "BoxLiteRuntime",
    "BoxLiteCodeExecutor",
    "BoxLiteDesktopExecutor",
]
