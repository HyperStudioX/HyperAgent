"""MCP server registry and lifecycle management."""

from app.core.logging import get_logger
from app.mcp.client import MCPClient, MCPServerConfig

logger = get_logger(__name__)

# Global MCP client singleton
_mcp_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
    return _mcp_client


def _sync_tools_to_registry(client: MCPClient) -> None:
    """Register all current MCP tools in the tool registry."""
    from app.agents.tools.registry import ToolCategory, register_tool

    for tool in client.get_tools():
        register_tool(ToolCategory.MCP, tool)


async def connect_server(config: MCPServerConfig) -> bool:
    """Connect to an MCP server and register its tools.

    Args:
        config: Server configuration

    Returns:
        True if connection succeeded
    """
    client = get_mcp_client()
    success = await client.add_server(config)

    if success:
        _sync_tools_to_registry(client)

    return success


async def disconnect_server(name: str) -> bool:
    """Disconnect from an MCP server and unregister its tools.

    Args:
        name: Server name

    Returns:
        True if server was removed
    """
    client = get_mcp_client()

    # Unregister tools from the tool registry before removing
    from app.agents.tools.registry import ToolCategory, unregister_tool

    tool_infos = [t for t in client.get_tool_infos() if t.server_name == name]
    for tool_info in tool_infos:
        unregister_tool(ToolCategory.MCP, f"mcp_{tool_info.name}")

    return await client.remove_server(name)


async def initialize_mcp(server_configs: list[dict] | None = None) -> None:
    """Initialize MCP connections from configuration.

    Args:
        server_configs: Optional list of server config dicts
    """
    client = get_mcp_client()

    if not server_configs:
        logger.info("mcp_no_servers_configured")
        return

    for config_dict in server_configs:
        try:
            config = MCPServerConfig(**config_dict)
            await client.add_server(config)
        except Exception as e:
            logger.error("mcp_server_init_failed", error=str(e), config=config_dict)

    # Register MCP tools in the tool registry
    _sync_tools_to_registry(client)

    logger.info(
        "mcp_initialized",
        servers=len(client.get_connected_servers()),
        tools=len(client.get_tools()),
    )


async def shutdown_mcp() -> None:
    """Shut down all MCP connections."""
    client = get_mcp_client()
    for server_name in list(client.get_connected_servers()):
        await client.remove_server(server_name)
    logger.info("mcp_shutdown_complete")
