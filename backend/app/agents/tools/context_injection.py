"""Centralized tool context injection for user_id/task_id.

Tools that need session management (browser, app builder, skills, etc.)
require user_id and task_id to be injected into their args. This module
provides a single source of truth for which tools need context injection.
"""

# Tools that need both user_id and task_id
_SESSION_TOOLS: set[str] = set()
# Tools that only need user_id
_USER_ONLY_TOOLS: set[str] = {"generate_image", "generate_slides"}

# Lazily populated sets of tool names by category
_browser_tool_names: set[str] | None = None
_app_builder_tool_names: set[str] | None = None


def _get_session_tool_names() -> set[str]:
    """Get the set of tool names that need both user_id and task_id."""
    global _browser_tool_names, _app_builder_tool_names, _SESSION_TOOLS

    if not _SESSION_TOOLS:
        from app.agents.tools import ToolCategory, get_tools_by_category

        if _browser_tool_names is None:
            _browser_tool_names = {t.name for t in get_tools_by_category(ToolCategory.BROWSER)}
        if _app_builder_tool_names is None:
            _app_builder_tool_names = {
                t.name for t in get_tools_by_category(ToolCategory.APP_BUILDER)
            }

        _SESSION_TOOLS.update(_browser_tool_names)
        _SESSION_TOOLS.update(_app_builder_tool_names)
        _SESSION_TOOLS.add("invoke_skill")
        _SESSION_TOOLS.add("execute_code")
        _SESSION_TOOLS.add("sandbox_file")

    return _SESSION_TOOLS


def inject_tool_context(
    tool_name: str,
    args: dict,
    user_id: str | None,
    task_id: str | None,
) -> dict:
    """Inject user_id/task_id into tool args based on tool category.

    Args:
        tool_name: Name of the tool being invoked
        args: Current tool arguments (modified in-place)
        user_id: User ID for context injection
        task_id: Task ID for context injection

    Returns:
        The args dict (same reference, modified in-place)
    """
    session_tools = _get_session_tool_names()

    if tool_name in session_tools:
        args["user_id"] = user_id
        args["task_id"] = task_id
    elif tool_name in _USER_ONLY_TOOLS:
        args["user_id"] = user_id

    return args
