"""Agent tools for the multi-agent system."""

from app.agents.tools.web_search import parse_search_results, web_search
from app.agents.tools.browser_use import browser_use, browser_navigate
from app.agents.tools.image_generation import generate_image
from app.agents.tools.vision import analyze_image
from app.agents.tools.code_execution import execute_code, execute_code_with_context
from app.agents.tools.sandbox_file import sandbox_file, sandbox_file_with_context
from app.agents.tools.sandbox_manager import (
    SandboxSession,
    SandboxManager,
    get_sandbox_manager,
)
from app.agents.tools.handoff import (
    create_handoff_tool,
    get_handoff_tools_for_agent,
    is_handoff_response,
    parse_handoff_response,
    HandoffManager,
    HANDOFF_MATRIX,
)
from app.agents.tools.registry import (
    ToolCategory,
    TOOL_CATALOG,
    AGENT_TOOL_MAPPING,
    get_tools_by_category,
    get_tools_for_agent,
    get_tool_names_for_agent,
    get_agent_categories,
    register_tool,
    unregister_tool,
    get_all_tools,
    get_tool_info,
)
from app.agents.tools.validators import (
    ValidationResult,
    FileOperationOutput,
    validate_tool_output,
    validate_search_results,
    validate_image_generation,
    validate_code_execution,
    validate_file_operation,
    extract_search_sources,
    extract_visualizations,
    is_tool_error_response,
    get_error_message,
)
from app.agents.tools.react_tool import (
    ToolExecutionError,
    execute_with_retry,
    execute_tool_with_retry,
    execute_tool_calls,
    is_transient_error,
    build_ai_message_from_chunks,
    ReActLoopConfig,
    ReActLoopResult,
    execute_react_loop,
)

__all__ = [
    # Core tools
    "web_search",
    "parse_search_results",
    "browser_use",
    "browser_navigate",
    "generate_image",
    "analyze_image",
    # Code execution and sandbox tools
    "execute_code",
    "execute_code_with_context",
    "sandbox_file",
    "sandbox_file_with_context",
    # Sandbox management
    "SandboxSession",
    "SandboxManager",
    "get_sandbox_manager",
    # Handoff tools
    "create_handoff_tool",
    "get_handoff_tools_for_agent",
    "is_handoff_response",
    "parse_handoff_response",
    "HandoffManager",
    "HANDOFF_MATRIX",
    # Registry
    "ToolCategory",
    "TOOL_CATALOG",
    "AGENT_TOOL_MAPPING",
    "get_tools_by_category",
    "get_tools_for_agent",
    "get_tool_names_for_agent",
    "get_agent_categories",
    "register_tool",
    "unregister_tool",
    "get_all_tools",
    "get_tool_info",
    # Validators
    "ValidationResult",
    "FileOperationOutput",
    "validate_tool_output",
    "validate_search_results",
    "validate_image_generation",
    "validate_code_execution",
    "validate_file_operation",
    "extract_search_sources",
    "extract_visualizations",
    "is_tool_error_response",
    "get_error_message",
    # Execution utilities
    "ToolExecutionError",
    "execute_with_retry",
    "execute_tool_with_retry",
    "execute_tool_calls",
    "is_transient_error",
    "build_ai_message_from_chunks",
    # ReAct loop utilities
    "ReActLoopConfig",
    "ReActLoopResult",
    "execute_react_loop",
]
