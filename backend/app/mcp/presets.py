"""Built-in MCP server presets.

Pre-configured MCP server definitions for common tools that can be
enabled with a single toggle instead of manual configuration.
"""

from app.mcp.client import MCPServerConfig

# Built-in MCP server presets
MCP_PRESETS: dict[str, MCPServerConfig] = {
    "playwright": MCPServerConfig(
        name="playwright",
        transport="stdio",
        command="npx",
        args=["@playwright/mcp@latest"],
        description="Browser automation via Playwright accessibility tree snapshots",
    ),
    "filesystem": MCPServerConfig(
        name="filesystem",
        transport="stdio",
        command="npx",
        args=["@anthropic/mcp-filesystem"],
        description="Enhanced file system operations (read, write, search, directory listing)",
    ),
    "sqlite": MCPServerConfig(
        name="sqlite",
        transport="stdio",
        command="npx",
        args=["@anthropic/mcp-sqlite"],
        description="SQLite database operations (query, schema inspection, data manipulation)",
    ),
    "git": MCPServerConfig(
        name="git",
        transport="stdio",
        command="npx",
        args=["@anthropic/mcp-git"],
        description="Git version control operations (status, diff, commit, log, branch)",
    ),
    "fetch": MCPServerConfig(
        name="fetch",
        transport="stdio",
        command="npx",
        args=["@anthropic/mcp-fetch"],
        description="HTTP fetch tool for retrieving web content and APIs",
    ),
}


def get_preset(name: str) -> MCPServerConfig | None:
    """Get a preset MCP server configuration by name.

    Args:
        name: Preset name (e.g. "playwright", "filesystem")

    Returns:
        MCPServerConfig if found, None otherwise
    """
    return MCP_PRESETS.get(name)


def list_presets() -> list[dict]:
    """List all available MCP server presets.

    Returns:
        List of preset info dicts with name, description, command
    """
    return [
        {
            "name": config.name,
            "description": config.description,
            "transport": config.transport,
            "command": config.command,
            "args": config.args,
        }
        for config in MCP_PRESETS.values()
    ]
