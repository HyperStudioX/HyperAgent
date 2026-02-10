"""Code Executor — re-export shim.

This module re-exports from the E2B provider for backward compatibility.
All new code should import from app.sandbox.e2b.code_executor or use
the base class from app.sandbox.base_code_executor.
"""

from app.sandbox.e2b.code_executor import (
    E2BSandboxExecutor,
    execute_python_with_data,
    get_e2b_executor,
)

__all__ = [
    "E2BSandboxExecutor",
    "execute_python_with_data",
    "get_e2b_executor",
]
