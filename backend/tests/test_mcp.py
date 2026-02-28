"""Tests for MCP (Model Context Protocol) integration."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.mcp.client import MCPClient, MCPServerConfig, MCPToolInfo


# ---------------------------------------------------------------------------
# MCPServerConfig validation tests
# ---------------------------------------------------------------------------


class TestMCPServerConfig:
    """Tests for MCPServerConfig model validation."""

    def test_minimal_config(self):
        """MCPServerConfig requires only name."""
        config = MCPServerConfig(name="test")
        assert config.name == "test"
        assert config.transport == "stdio"
        assert config.command is None
        assert config.args == []
        assert config.env == {}
        assert config.url is None
        assert config.auth_token is None
        assert config.description == ""
        assert config.enabled is True

    def test_stdio_config(self):
        """MCPServerConfig for stdio transport."""
        config = MCPServerConfig(
            name="playwright",
            transport="stdio",
            command="npx",
            args=["@playwright/mcp@latest"],
            description="Browser automation",
        )
        assert config.name == "playwright"
        assert config.transport == "stdio"
        assert config.command == "npx"
        assert config.args == ["@playwright/mcp@latest"]
        assert config.description == "Browser automation"

    def test_sse_config(self):
        """MCPServerConfig for SSE transport."""
        config = MCPServerConfig(
            name="remote-server",
            transport="sse",
            url="http://localhost:3001/sse",
            auth_token="token123",
            description="Remote MCP server",
        )
        assert config.transport == "sse"
        assert config.url == "http://localhost:3001/sse"
        assert config.auth_token == "token123"

    def test_disabled_config(self):
        """MCPServerConfig with enabled=False."""
        config = MCPServerConfig(
            name="disabled-server",
            transport="stdio",
            command="npx",
            args=["@anthropic/mcp-git"],
            enabled=False,
        )
        assert config.enabled is False

    def test_config_from_dict(self):
        """MCPServerConfig can be created from a dict."""
        data = {
            "name": "test",
            "transport": "stdio",
            "command": "npx",
            "args": ["@anthropic/mcp-filesystem"],
            "description": "File tools",
        }
        config = MCPServerConfig(**data)
        assert config.name == "test"
        assert config.command == "npx"

    def test_config_with_env(self):
        """MCPServerConfig supports environment variables."""
        config = MCPServerConfig(
            name="with-env",
            transport="stdio",
            command="npx",
            args=["some-server"],
            env={"API_KEY": "secret123", "DEBUG": "true"},
        )
        assert config.env == {"API_KEY": "secret123", "DEBUG": "true"}


# ---------------------------------------------------------------------------
# MCPToolInfo validation tests
# ---------------------------------------------------------------------------


class TestMCPToolInfo:
    """Tests for MCPToolInfo model validation."""

    def test_minimal_tool_info(self):
        """MCPToolInfo requires only name and description."""
        info = MCPToolInfo(name="query_db", description="Query a database")
        assert info.name == "query_db"
        assert info.description == "Query a database"
        assert info.input_schema == {}
        assert info.server_name == ""

    def test_full_tool_info(self):
        """MCPToolInfo accepts all fields including input_schema."""
        schema = {
            "properties": {
                "query": {"type": "string", "description": "SQL query"},
            },
            "required": ["query"],
        }
        info = MCPToolInfo(
            name="query_db",
            description="Query a database",
            input_schema=schema,
            server_name="db-server",
        )
        assert info.input_schema == schema
        assert info.server_name == "db-server"


# ---------------------------------------------------------------------------
# MCPClient tests
# ---------------------------------------------------------------------------


class TestMCPClient:
    """Tests for the MCPClient class."""

    def test_initial_state(self):
        """MCPClient starts with no servers, tools, or connections."""
        client = MCPClient()
        assert client.get_tools() == []
        assert client.get_tool_infos() == []
        assert client.get_connected_servers() == []
        assert client.get_server_configs() == []
        assert client.is_connected is False

    @pytest.mark.asyncio
    async def test_add_disabled_server(self):
        """add_server with enabled=False stores config but does not connect."""
        client = MCPClient()
        config = MCPServerConfig(
            name="disabled",
            transport="stdio",
            command="echo",
            enabled=False,
        )

        result = await client.add_server(config)

        assert result is False
        assert "disabled" not in client.get_connected_servers()
        # Config is still stored
        assert len(client.get_server_configs()) == 1

    @pytest.mark.asyncio
    async def test_add_server_connection_failure(self):
        """add_server returns False when connection fails."""
        client = MCPClient()
        config = MCPServerConfig(
            name="bad-server",
            transport="stdio",
            command="nonexistent_command_that_does_not_exist",
        )

        result = await client.add_server(config)

        assert result is False
        assert "bad-server" not in client.get_connected_servers()

    @pytest.mark.asyncio
    async def test_remove_nonexistent_server(self):
        """remove_server returns False for unknown server name."""
        client = MCPClient()

        result = await client.remove_server("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_server_cleans_up_tools(self):
        """remove_server removes tools associated with that server."""
        client = MCPClient()

        # Manually inject a tool and tool_info to simulate a connected server
        tool_info = MCPToolInfo(
            name="test_tool",
            description="A test tool",
            server_name="my-server",
        )
        config = MCPServerConfig(
            name="my-server",
            transport="stdio",
            command="echo",
        )
        client._servers["my-server"] = config
        client._connected.add("my-server")
        client._tool_infos["test_tool"] = tool_info

        # Create a mock wrapped tool using _wrap_tool for proper construction
        wrapped_info = MCPToolInfo(
            name="test_tool",
            description="A test tool",
            input_schema={},
        )
        mock_tool = client._wrap_tool(wrapped_info, config)
        client._tools["test_tool"] = mock_tool

        await client.remove_server("my-server")

        assert len(client._tools) == 0
        assert len(client._tool_infos) == 0

    def test_get_tools_returns_empty_initially(self):
        """get_tools returns an empty list when no servers are connected."""
        client = MCPClient()
        assert client.get_tools() == []

    def test_get_tool_returns_none_for_unknown(self):
        """get_tool returns None for an unknown tool name."""
        client = MCPClient()
        assert client.get_tool("nonexistent") is None

    def test_is_connected_property(self):
        """is_connected reflects whether any server is connected."""
        client = MCPClient()
        assert client.is_connected is False

        client._connected.add("some-server")
        assert client.is_connected is True


# ---------------------------------------------------------------------------
# MCPClient._wrap_tool tests
# ---------------------------------------------------------------------------


class TestMCPWrapTool:
    """Tests for the _wrap_tool method that creates LangChain tools."""

    def test_wrap_tool_creates_structured_tool(self):
        """_wrap_tool creates a valid LangChain StructuredTool."""
        client = MCPClient()
        config = MCPServerConfig(
            name="db-server",
            transport="stdio",
            command="echo",
        )
        tool_info = MCPToolInfo(
            name="query",
            description="Run a SQL query",
            input_schema={
                "properties": {
                    "sql": {"type": "string", "description": "The SQL query to execute"},
                },
                "required": ["sql"],
            },
        )

        tool = client._wrap_tool(tool_info, config)

        assert tool.name == "mcp_query"
        assert "Run a SQL query" in tool.description
        assert "[MCP: db-server]" in tool.description
        assert tool.coroutine is not None

    def test_wrap_tool_with_empty_schema(self):
        """_wrap_tool handles tools with no input parameters."""
        client = MCPClient()
        config = MCPServerConfig(
            name="server",
            transport="stdio",
            command="echo",
        )
        tool_info = MCPToolInfo(
            name="ping",
            description="Ping the server",
            input_schema={},
        )

        tool = client._wrap_tool(tool_info, config)

        assert tool.name == "mcp_ping"
        assert tool.coroutine is not None

    def test_wrap_tool_with_multiple_types(self):
        """_wrap_tool correctly maps various JSON schema types."""
        client = MCPClient()
        config = MCPServerConfig(
            name="server",
            transport="stdio",
            command="echo",
        )
        tool_info = MCPToolInfo(
            name="complex_tool",
            description="A tool with many parameter types",
            input_schema={
                "properties": {
                    "name": {"type": "string", "description": "A name"},
                    "count": {"type": "integer", "description": "A count"},
                    "score": {"type": "number", "description": "A score"},
                    "active": {"type": "boolean", "description": "Is active"},
                    "tags": {"type": "array", "description": "Tags list"},
                    "meta": {"type": "object", "description": "Metadata dict"},
                },
                "required": ["name"],
            },
        )

        tool = client._wrap_tool(tool_info, config)

        assert tool.name == "mcp_complex_tool"
        # Verify the args_schema has the correct fields
        schema = tool.args_schema
        assert schema is not None
        fields = schema.model_fields
        assert "name" in fields
        assert "count" in fields
        assert "score" in fields
        assert "active" in fields
        assert "tags" in fields
        assert "meta" in fields


# ---------------------------------------------------------------------------
# MCP registry tests
# ---------------------------------------------------------------------------


class TestMCPRegistry:
    """Tests for the MCP registry module."""

    def test_get_mcp_client_returns_singleton(self):
        """get_mcp_client returns the same instance on repeated calls."""
        from app.mcp import registry

        # Reset the global to ensure clean state
        original = registry._mcp_client
        registry._mcp_client = None

        try:
            client1 = registry.get_mcp_client()
            client2 = registry.get_mcp_client()
            assert client1 is client2
        finally:
            # Restore original state
            registry._mcp_client = original

    @pytest.mark.asyncio
    async def test_initialize_mcp_with_no_configs(self):
        """initialize_mcp with no configs does nothing."""
        from app.mcp import registry

        original = registry._mcp_client
        registry._mcp_client = None

        try:
            await registry.initialize_mcp(None)
            # Should not raise, client should exist but have no servers
            client = registry.get_mcp_client()
            assert len(client.get_connected_servers()) == 0
        finally:
            registry._mcp_client = original

    @pytest.mark.asyncio
    async def test_initialize_mcp_with_invalid_config(self):
        """initialize_mcp handles invalid config gracefully without crashing."""
        from app.mcp import registry

        original = registry._mcp_client
        registry._mcp_client = None

        try:
            # Missing required fields
            configs = [{"invalid": "config"}]
            # Should not raise
            await registry.initialize_mcp(configs)

            client = registry.get_mcp_client()
            assert len(client.get_connected_servers()) == 0
        finally:
            registry._mcp_client = original

    @pytest.mark.asyncio
    async def test_shutdown_mcp_empty(self):
        """shutdown_mcp with no servers doesn't crash."""
        from app.mcp import registry

        original = registry._mcp_client
        registry._mcp_client = None

        try:
            registry.get_mcp_client()
            await registry.shutdown_mcp()
        finally:
            registry._mcp_client = original


# ---------------------------------------------------------------------------
# MCP presets tests
# ---------------------------------------------------------------------------


class TestMCPPresets:
    """Tests for built-in MCP server presets."""

    def test_presets_exist(self):
        """Built-in presets should be defined."""
        from app.mcp.presets import MCP_PRESETS

        assert len(MCP_PRESETS) > 0

    def test_playwright_preset(self):
        """Playwright preset should be properly configured."""
        from app.mcp.presets import get_preset

        preset = get_preset("playwright")
        assert preset is not None
        assert preset.name == "playwright"
        assert preset.transport == "stdio"
        assert preset.command == "npx"
        assert "@playwright/mcp@latest" in preset.args

    def test_filesystem_preset(self):
        """Filesystem preset should be properly configured."""
        from app.mcp.presets import get_preset

        preset = get_preset("filesystem")
        assert preset is not None
        assert preset.transport == "stdio"
        assert preset.command == "npx"

    def test_get_preset_nonexistent(self):
        """get_preset returns None for unknown presets."""
        from app.mcp.presets import get_preset

        assert get_preset("nonexistent") is None

    def test_list_presets(self):
        """list_presets returns info dicts for all presets."""
        from app.mcp.presets import list_presets

        presets = list_presets()
        assert len(presets) > 0
        for p in presets:
            assert "name" in p
            assert "description" in p
            assert "transport" in p
            assert "command" in p

    def test_all_presets_are_stdio(self):
        """All built-in presets use stdio transport."""
        from app.mcp.presets import MCP_PRESETS

        for name, config in MCP_PRESETS.items():
            assert config.transport == "stdio", f"Preset '{name}' should use stdio"
            assert config.command is not None, f"Preset '{name}' must have a command"


# ---------------------------------------------------------------------------
# Tool registry integration tests
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    """Tests that MCP is properly integrated in the tool registry."""

    def test_mcp_category_exists(self):
        """MCP category should exist in ToolCategory."""
        from app.agents.tools.registry import ToolCategory

        assert hasattr(ToolCategory, "MCP")
        assert ToolCategory.MCP.value == "mcp"

    def test_mcp_in_tool_catalog(self):
        """MCP should be present in TOOL_CATALOG."""
        from app.agents.tools.registry import TOOL_CATALOG, ToolCategory

        assert ToolCategory.MCP in TOOL_CATALOG
        # Initially empty since no MCP servers are connected
        assert isinstance(TOOL_CATALOG[ToolCategory.MCP], list)

    def test_mcp_in_task_agent_mapping(self):
        """MCP should be in the Task agent's tool mapping."""
        from app.agents.state import AgentType
        from app.agents.tools.registry import AGENT_TOOL_MAPPING, ToolCategory

        task_categories = AGENT_TOOL_MAPPING[AgentType.TASK.value]
        assert ToolCategory.MCP in task_categories

    def test_register_and_unregister_mcp_tool(self):
        """Dynamic registration of MCP tools works correctly."""
        from app.agents.tools.registry import (
            TOOL_CATALOG,
            ToolCategory,
            register_tool,
            unregister_tool,
        )

        # Create a dummy MCP tool
        client = MCPClient()
        config = MCPServerConfig(name="test", transport="stdio", command="echo")
        tool_info = MCPToolInfo(name="test_reg", description="Test registration")
        tool = client._wrap_tool(tool_info, config)

        # Track initial count
        initial_count = len(TOOL_CATALOG[ToolCategory.MCP])

        # Register
        register_tool(ToolCategory.MCP, tool)
        assert len(TOOL_CATALOG[ToolCategory.MCP]) == initial_count + 1

        # Unregister
        unregister_tool(ToolCategory.MCP, "mcp_test_reg")
        assert len(TOOL_CATALOG[ToolCategory.MCP]) == initial_count
