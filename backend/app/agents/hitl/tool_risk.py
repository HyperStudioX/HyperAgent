"""Tool risk registry for Human-in-the-Loop approvals.

Defines which tools require user approval before execution based on
their potential impact:

- HIGH_RISK: Always requires approval (browser automation, code execution, file ops)
- MEDIUM_RISK: May require approval based on settings
- LOW_RISK: No approval needed (search, read-only operations)
"""

from enum import Enum
from typing import Literal


class ToolRiskLevel(str, Enum):
    """Risk levels for tool categorization."""

    HIGH = "high"  # Always requires approval
    MEDIUM = "medium"  # May require approval based on settings
    LOW = "low"  # No approval needed


# Tools that always require user approval before execution
HIGH_RISK_TOOLS: set[str] = {
    # Browser automation - can access arbitrary URLs and perform actions
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_screenshot",
    "browser_close",
    "computer_tool",  # E2B desktop/browser tool
    # Code execution - can run arbitrary code
    "execute_code",
    "code_interpreter",
    "python_repl",
    "sandbox_execute",
    # File operations - can read/write files
    "sandbox_file",
    "file_write",
    "file_delete",
    # System operations
    "shell_command",
    "bash",
}

# Tools that may require approval depending on settings
MEDIUM_RISK_TOOLS: set[str] = {
    # External API calls
    "api_call",
    "http_request",
    # Data modification
    "database_write",
    "database_delete",
    # File reading (could expose sensitive data)
    "file_read",
    "sandbox_file_read",
}

# All tools not in HIGH or MEDIUM risk are considered LOW risk
# and do not require approval


def get_tool_risk_level(tool_name: str) -> ToolRiskLevel:
    """Get the risk level for a tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Risk level for the tool
    """
    if tool_name in HIGH_RISK_TOOLS:
        return ToolRiskLevel.HIGH
    elif tool_name in MEDIUM_RISK_TOOLS:
        return ToolRiskLevel.MEDIUM
    else:
        return ToolRiskLevel.LOW


def requires_approval(
    tool_name: str,
    auto_approve_tools: list[str] | None = None,
    hitl_enabled: bool = True,
    risk_threshold: Literal["high", "medium", "all"] = "high",
) -> bool:
    """Check if a tool requires user approval.

    Args:
        tool_name: Name of the tool to check
        auto_approve_tools: List of tools user has auto-approved
        hitl_enabled: Whether HITL is enabled
        risk_threshold: Minimum risk level requiring approval
            - "high": Only HIGH risk tools require approval
            - "medium": HIGH and MEDIUM risk tools require approval
            - "all": All tools require approval

    Returns:
        True if the tool requires approval
    """
    if not hitl_enabled:
        return False

    # Check if user has auto-approved this tool for the session
    if auto_approve_tools and tool_name in auto_approve_tools:
        return False

    risk_level = get_tool_risk_level(tool_name)

    if risk_threshold == "high":
        return risk_level == ToolRiskLevel.HIGH
    elif risk_threshold == "medium":
        return risk_level in (ToolRiskLevel.HIGH, ToolRiskLevel.MEDIUM)
    else:  # "all"
        return True


def get_tool_approval_message(tool_name: str, args: dict) -> tuple[str, str]:
    """Generate approval title and message for a tool.

    Args:
        tool_name: Name of the tool
        args: Tool arguments

    Returns:
        Tuple of (title, message) for the approval dialog
    """
    risk_level = get_tool_risk_level(tool_name)

    if tool_name in ("browser_navigate", "computer_tool"):
        url = args.get("url", args.get("action", {}).get("text", "unknown"))
        return (
            "Browser Navigation",
            f"The agent wants to navigate to:\n\n**{url}**\n\nThis will open a browser and access external content.",
        )
    elif tool_name in ("browser_click", "browser_type"):
        target = args.get("selector", args.get("text", "element"))
        action = "click" if tool_name == "browser_click" else "type into"
        return (
            f"Browser {action.title()}",
            f"The agent wants to {action} **{target}** in the browser.\n\nThis may trigger actions on the current page.",
        )
    elif tool_name in ("execute_code", "code_interpreter", "python_repl", "sandbox_execute"):
        code_preview = args.get("code", "")[:200]
        if len(args.get("code", "")) > 200:
            code_preview += "..."
        return (
            "Code Execution",
            f"The agent wants to execute code:\n\n```\n{code_preview}\n```\n\nThis code will run in a sandboxed environment.",
        )
    elif tool_name in ("sandbox_file", "file_write", "file_delete"):
        path = args.get("path", args.get("filename", "unknown"))
        operation = "modify" if "write" in tool_name else "delete"
        return (
            f"File {operation.title()}",
            f"The agent wants to {operation} the file:\n\n**{path}**",
        )
    else:
        # Generic message for other high-risk tools
        return (
            f"Tool Approval: {tool_name}",
            f"The agent wants to use the **{tool_name}** tool.\n\nRisk level: **{risk_level.value}**",
        )
