"""Code Executor — re-export shim (DEPRECATED).

.. deprecated::
    This module re-exports from the E2B provider for backward compatibility.
    All new code should import from ``app.sandbox.e2b.code_executor`` or use
    the provider factory via ``app.sandbox.provider``.
"""

import warnings

warnings.warn(
    "app.sandbox.code_executor is deprecated. "
    "Import from app.sandbox.e2b.code_executor or use the provider factory instead.",
    DeprecationWarning,
    stacklevel=2,
)

from app.sandbox.e2b.code_executor import (
    E2BSandboxExecutor,
    execute_python_with_data,
)

__all__ = [
    "E2BSandboxExecutor",
    "execute_python_with_data",
]
