"""Tool Registry with Categorization.

This module provides a centralized registry for all agent tools,
organized by category. Agents can request tools by category to get
only the tools relevant to their specialization.
"""

from enum import Enum
from typing import Any

from langchain_core.tools import BaseTool

from app.agents.state import AgentType
from app.agents.tools.handoff import get_handoff_tools_for_agent
from app.agents.tools.web_search import web_search
from app.agents.tools.browser import (
    browser_navigate,
    browser_screenshot,
    browser_click,
    browser_type,
    browser_press_key,
    browser_scroll,
    browser_get_stream_url,
)
from app.agents.tools.image_generation import generate_image
from app.agents.tools.vision import analyze_image
from app.agents.tools.code_execution import execute_code
from app.agents.tools.sandbox_file import sandbox_file
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolCategory(str, Enum):
    """Categories of tools available to agents."""

    SEARCH = "search"  # Web search capabilities
    IMAGE = "image"  # Image generation and analysis
    BROWSER = "browser"  # Browser automation (E2B Desktop sandbox)
    CODE_EXEC = "code_exec"  # Code execution in sandbox
    DATA = "data"  # Data processing and analysis
    HANDOFF = "handoff"  # Agent-to-agent delegation


# Tool instances by category
# Note: Some tools may belong to multiple categories
TOOL_CATALOG: dict[ToolCategory, list[BaseTool]] = {
    ToolCategory.SEARCH: [web_search],
    ToolCategory.IMAGE: [generate_image, analyze_image],
    ToolCategory.BROWSER: [
        browser_navigate,
        browser_screenshot,
        browser_click,
        browser_type,
        browser_press_key,
        browser_scroll,
        browser_get_stream_url,
    ],
    ToolCategory.CODE_EXEC: [execute_code],
    ToolCategory.DATA: [sandbox_file],
    # HANDOFF tools are created dynamically per agent
    ToolCategory.HANDOFF: [],
}


# Define which tool categories each agent type can access
AGENT_TOOL_MAPPING: dict[str, list[ToolCategory]] = {
    AgentType.CHAT.value: [
        ToolCategory.SEARCH,
        ToolCategory.IMAGE,
        ToolCategory.BROWSER,
        ToolCategory.HANDOFF,
    ],
    AgentType.RESEARCH.value: [
        ToolCategory.SEARCH,
        ToolCategory.IMAGE,
        ToolCategory.BROWSER,
        ToolCategory.HANDOFF,
    ],
    AgentType.CODE.value: [
        ToolCategory.SEARCH,
        ToolCategory.CODE_EXEC,
        ToolCategory.HANDOFF,
    ],
    AgentType.WRITING.value: [
        ToolCategory.SEARCH,
        ToolCategory.IMAGE,
        ToolCategory.HANDOFF,
    ],
    AgentType.DATA.value: [
        ToolCategory.CODE_EXEC,
        ToolCategory.DATA,
        ToolCategory.HANDOFF,
    ],
}


def get_tools_by_category(category: ToolCategory) -> list[BaseTool]:
    """Get all tools in a specific category.

    Args:
        category: The tool category to retrieve

    Returns:
        List of tools in that category
    """
    return TOOL_CATALOG.get(category, []).copy()


def get_tools_for_agent(
    agent_type: str,
    include_handoffs: bool = True,
    enable_search: bool = True,
    enable_image: bool = True,
    enable_browser: bool = True,
) -> list[BaseTool]:
    """Get all tools available to a specific agent type.

    This function retrieves tools based on the agent's allowed categories
    and optional feature flags for runtime control.

    Args:
        agent_type: The agent type (e.g., "chat", "research")
        include_handoffs: Whether to include handoff tools
        enable_search: Whether to enable search tools (for gating)
        enable_image: Whether to enable image tools (for gating)
        enable_browser: Whether to enable browser tools (E2B Desktop)

    Returns:
        List of tools available to the agent
    """
    allowed_categories = AGENT_TOOL_MAPPING.get(agent_type, [])
    tools: list[BaseTool] = []
    seen_names: set[str] = set()

    # Feature flag mapping for categories
    category_enabled = {
        ToolCategory.SEARCH: enable_search,
        ToolCategory.IMAGE: enable_image,
        ToolCategory.BROWSER: enable_browser,
        ToolCategory.HANDOFF: False,  # Handled separately
    }

    def add_tools(tool_list: list[BaseTool]) -> None:
        """Add tools to the result list, avoiding duplicates."""
        for tool in tool_list:
            if tool.name not in seen_names:
                tools.append(tool)
                seen_names.add(tool.name)

    for category in allowed_categories:
        # Skip disabled categories (defaults to enabled if not in map)
        if not category_enabled.get(category, True):
            continue

        add_tools(TOOL_CATALOG.get(category, []))

    # Add handoff tools if enabled
    if include_handoffs and ToolCategory.HANDOFF in allowed_categories:
        add_tools(get_handoff_tools_for_agent(agent_type))

    logger.debug(
        "tools_retrieved_for_agent",
        agent=agent_type,
        tool_count=len(tools),
        tools=[t.name for t in tools],
    )

    return tools


def get_tool_names_for_agent(agent_type: str) -> list[str]:
    """Get names of all tools available to an agent.

    Useful for logging and debugging without instantiating tools.

    Args:
        agent_type: The agent type

    Returns:
        List of tool names
    """
    tools = get_tools_for_agent(agent_type, include_handoffs=False)
    return [tool.name for tool in tools]


def get_agent_categories(agent_type: str) -> list[ToolCategory]:
    """Get the tool categories available to an agent.

    Args:
        agent_type: The agent type

    Returns:
        List of tool categories the agent can access
    """
    return AGENT_TOOL_MAPPING.get(agent_type, []).copy()


def register_tool(category: ToolCategory, tool: BaseTool) -> None:
    """Register a new tool in a category.

    Use this to dynamically add tools (e.g., custom code execution tools)
    at runtime.

    Args:
        category: The category to register the tool in
        tool: The tool to register
    """
    if category not in TOOL_CATALOG:
        TOOL_CATALOG[category] = []

    # Avoid duplicates
    existing_names = {t.name for t in TOOL_CATALOG[category]}
    if tool.name not in existing_names:
        TOOL_CATALOG[category].append(tool)
        logger.info(
            "tool_registered",
            category=category.value,
            tool=tool.name,
        )


def unregister_tool(category: ToolCategory, tool_name: str) -> bool:
    """Remove a tool from a category.

    Args:
        category: The category to remove from
        tool_name: Name of the tool to remove

    Returns:
        True if tool was removed, False if not found
    """
    if category not in TOOL_CATALOG:
        return False

    original_len = len(TOOL_CATALOG[category])
    TOOL_CATALOG[category] = [
        t for t in TOOL_CATALOG[category] if t.name != tool_name
    ]

    if len(TOOL_CATALOG[category]) < original_len:
        logger.info(
            "tool_unregistered",
            category=category.value,
            tool=tool_name,
        )
        return True

    return False


def get_all_tools() -> list[BaseTool]:
    """Get all registered tools across all categories.

    Returns:
        List of all unique tools
    """
    seen_names: set[str] = set()
    tools: list[BaseTool] = []

    for category_tools in TOOL_CATALOG.values():
        for tool in category_tools:
            if tool.name not in seen_names:
                tools.append(tool)
                seen_names.add(tool.name)

    return tools


def get_tool_info() -> dict[str, Any]:
    """Get information about the tool registry for debugging.

    Returns:
        Dict with registry state information
    """
    return {
        "categories": {
            cat.value: [t.name for t in tools]
            for cat, tools in TOOL_CATALOG.items()
        },
        "agent_mappings": {
            agent: [cat.value for cat in cats]
            for agent, cats in AGENT_TOOL_MAPPING.items()
        },
        "total_tools": len(get_all_tools()),
    }
