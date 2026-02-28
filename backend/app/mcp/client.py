"""MCP (Model Context Protocol) client for HyperAgent.

Connects to MCP servers via stdio or SSE transport, discovers tools,
and wraps them as LangChain StructuredTool instances for the agent system.

Uses the JSON-RPC based MCP protocol:
  - initialize handshake
  - tools/list to discover available tools
  - tools/call to invoke a tool
"""

import asyncio
import json
import os
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from app.core.logging import get_logger

logger = get_logger(__name__)

# JSON-RPC request ID counter
_request_id = 0


def _next_id() -> int:
    global _request_id
    _request_id += 1
    return _request_id


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    name: str  # Human-readable name
    transport: str = "stdio"  # "stdio" or "sse"
    command: str | None = None  # For stdio transport
    args: list[str] = []  # Command arguments for stdio
    env: dict[str, str] = {}  # Additional environment variables for stdio
    url: str | None = None  # For SSE transport, or legacy compatibility
    auth_token: str | None = None
    description: str = ""
    enabled: bool = True


class MCPToolInfo(BaseModel):
    """Information about a tool discovered from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any] = {}
    server_name: str = ""


class _StdioConnection:
    """Manages a subprocess connection to an MCP server via stdio transport."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._read_buffer = b""

    async def start(self) -> None:
        """Spawn the MCP server subprocess."""
        if not self.config.command:
            raise ValueError(f"No command specified for stdio server '{self.config.name}'")

        env = {**os.environ, **self.config.env}

        self.process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        logger.info(
            "mcp_stdio_process_started",
            server=self.config.name,
            command=self.config.command,
            pid=self.process.pid,
        )

    async def send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and wait for the response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError(f"MCP server '{self.config.name}' is not connected")

        async with self._lock:
            request_id = _next_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }
            if params is not None:
                request["params"] = params

            payload = json.dumps(request)
            # MCP uses Content-Length header framing over stdio
            message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"

            self.process.stdin.write(message.encode())
            await self.process.stdin.drain()

            # Read response with Content-Length framing
            response = await self._read_response()
            return response

    async def _read_response(self) -> dict:
        """Read a JSON-RPC response with Content-Length framing."""
        if not self.process or not self.process.stdout:
            raise RuntimeError("Process stdout not available")

        # Read headers until we find Content-Length
        headers = b""
        while True:
            byte = await asyncio.wait_for(
                self.process.stdout.read(1),
                timeout=30.0,
            )
            if not byte:
                raise RuntimeError("MCP server closed connection")
            headers += byte
            if headers.endswith(b"\r\n\r\n"):
                break

        # Parse Content-Length
        content_length = 0
        for line in headers.decode().split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break

        if content_length == 0:
            raise RuntimeError("Missing Content-Length in MCP response")

        # Read the body
        body = await asyncio.wait_for(
            self.process.stdout.readexactly(content_length),
            timeout=30.0,
        )

        data = json.loads(body.decode())

        # Skip notifications (no "id" field) and read next response
        if "id" not in data:
            return await self._read_response()

        if "error" in data:
            error = data["error"]
            raise RuntimeError(
                f"MCP error ({error.get('code', 'unknown')}): {error.get('message', 'Unknown error')}"
            )

        return data.get("result", {})

    async def stop(self) -> None:
        """Terminate the subprocess."""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
            finally:
                self.process = None
            logger.info("mcp_stdio_process_stopped", server=self.config.name)


class _SSEConnection:
    """Manages an SSE (Server-Sent Events) connection to an MCP server."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session = None
        self._endpoint_url: str | None = None

    async def start(self) -> None:
        """Connect to the SSE endpoint and discover the message endpoint."""
        try:
            import aiohttp
        except ImportError:
            raise RuntimeError(
                "aiohttp is required for SSE transport. Install it with: pip install aiohttp"
            )

        if not self.config.url:
            raise ValueError(f"No URL specified for SSE server '{self.config.name}'")

        self._session = aiohttp.ClientSession()

        headers = {}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        # Connect to the SSE endpoint to get the message posting URL
        # MCP SSE servers expose an SSE endpoint that sends an 'endpoint' event
        try:
            async with self._session.get(
                self.config.url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        f"SSE connection failed with status {resp.status}"
                    )
                # Read until we get the endpoint event
                async for line in resp.content:
                    decoded = line.decode().strip()
                    if decoded.startswith("data:"):
                        data = decoded[5:].strip()
                        try:
                            event_data = json.loads(data)
                            if "endpoint" in event_data:
                                self._endpoint_url = event_data["endpoint"]
                                break
                        except json.JSONDecodeError:
                            # Some SSE servers send the endpoint URL directly
                            if data.startswith("http"):
                                self._endpoint_url = data
                                break
        except Exception:
            # Fall back to using the base URL + /message for posting
            base = self.config.url.rstrip("/")
            self._endpoint_url = f"{base}/message"

        logger.info(
            "mcp_sse_connected",
            server=self.config.name,
            url=self.config.url,
        )

    async def send_request(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request via HTTP POST."""
        try:
            import aiohttp
        except ImportError:
            raise RuntimeError("aiohttp is required for SSE transport")

        if not self._session or not self._endpoint_url:
            raise RuntimeError(f"MCP SSE server '{self.config.name}' is not connected")

        request_id = _next_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        headers = {"Content-Type": "application/json"}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        async with self._session.post(
            self._endpoint_url,
            json=request,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"MCP SSE request failed ({resp.status}): {text}")

            data = await resp.json()

            if "error" in data:
                error = data["error"]
                raise RuntimeError(
                    f"MCP error ({error.get('code', 'unknown')}): {error.get('message', 'Unknown error')}"
                )

            return data.get("result", {})

    async def stop(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("mcp_sse_disconnected", server=self.config.name)


class MCPClient:
    """Client for connecting to MCP servers and discovering tools.

    Manages connections to multiple MCP servers, discovers their tools,
    and creates LangChain StructuredTool wrappers.

    Supports two transport types:
    - stdio: Spawns a subprocess and communicates via stdin/stdout
    - sse: Connects to an HTTP SSE endpoint
    """

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._connections: dict[str, _StdioConnection | _SSEConnection] = {}
        self._tools: dict[str, StructuredTool] = {}  # tool_name -> wrapped tool
        self._tool_infos: dict[str, MCPToolInfo] = {}
        self._connected: set[str] = set()

    async def add_server(self, config: MCPServerConfig) -> bool:
        """Register and connect to an MCP server.

        Args:
            config: Server configuration

        Returns:
            True if connection succeeded
        """
        self._servers[config.name] = config

        if not config.enabled:
            logger.info("mcp_server_disabled", name=config.name)
            return False

        try:
            # Create and start the connection
            connection = self._create_connection(config)
            await connection.start()
            self._connections[config.name] = connection

            # Perform MCP initialize handshake
            await self._initialize_handshake(config.name)

            # Discover tools
            tools = await self._discover_tools(config)

            for tool_info in tools:
                tool_info.server_name = config.name
                wrapped = self._wrap_tool(tool_info, config)
                self._tools[tool_info.name] = wrapped
                self._tool_infos[tool_info.name] = tool_info

                # Dynamic registration in the agent tool registry
                try:
                    from app.agents.tools.registry import ToolCategory, register_tool
                    register_tool(ToolCategory.MCP, wrapped)
                except Exception as reg_err:
                    logger.debug(
                        "mcp_tool_registry_failed",
                        tool=tool_info.name,
                        error=str(reg_err),
                    )

            self._connected.add(config.name)
            logger.info(
                "mcp_server_connected",
                name=config.name,
                tool_count=len(tools),
            )
            return True

        except Exception as e:
            logger.error("mcp_server_connection_failed", name=config.name, error=str(e))
            # Clean up partial connection
            if config.name in self._connections:
                try:
                    await self._connections[config.name].stop()
                except Exception:
                    pass
                del self._connections[config.name]
            return False

    def _create_connection(self, config: MCPServerConfig) -> _StdioConnection | _SSEConnection:
        """Create the appropriate connection type based on transport config."""
        if config.transport == "sse":
            return _SSEConnection(config)
        else:
            # Default to stdio
            return _StdioConnection(config)

    async def _initialize_handshake(self, server_name: str) -> None:
        """Perform the MCP initialize handshake with a connected server."""
        connection = self._connections.get(server_name)
        if not connection:
            raise RuntimeError(f"No connection for server '{server_name}'")

        result = await connection.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "HyperAgent",
                    "version": "0.1.0",
                },
            },
        )
        logger.debug(
            "mcp_handshake_complete",
            server=server_name,
            server_info=result.get("serverInfo", {}),
        )

        # Send initialized notification
        if connection and hasattr(connection, "process") and isinstance(connection, _StdioConnection):
            # For stdio, send notification (no response expected)
            if connection.process and connection.process.stdin:
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                }
                payload = json.dumps(notification)
                message = f"Content-Length: {len(payload)}\r\n\r\n{payload}"
                connection.process.stdin.write(message.encode())
                await connection.process.stdin.drain()

    async def _discover_tools(self, config: MCPServerConfig) -> list[MCPToolInfo]:
        """Discover tools from an MCP server using the tools/list method.

        Args:
            config: Server configuration

        Returns:
            List of discovered tool infos
        """
        connection = self._connections.get(config.name)
        if not connection:
            logger.warning("mcp_no_connection_for_discovery", server=config.name)
            return []

        result = await connection.send_request("tools/list")
        raw_tools = result.get("tools", [])

        tools = []
        for t in raw_tools:
            tool_info = MCPToolInfo(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=config.name,
            )
            tools.append(tool_info)

        logger.info(
            "mcp_tools_discovered",
            server=config.name,
            count=len(tools),
            tool_names=[t.name for t in tools],
        )
        return tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """Call a tool on a connected MCP server.

        Args:
            server_name: Name of the server
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        connection = self._connections.get(server_name)
        if not connection:
            raise RuntimeError(f"MCP server '{server_name}' is not connected")

        result = await connection.send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
        return result

    async def remove_server(self, name: str) -> bool:
        """Disconnect and remove an MCP server.

        Args:
            name: Server name

        Returns:
            True if server was removed
        """
        if name not in self._servers:
            return False

        # Stop the connection
        connection = self._connections.pop(name, None)
        if connection:
            try:
                await connection.stop()
            except Exception as e:
                logger.warning("mcp_connection_stop_error", server=name, error=str(e))

        # Remove tools from this server and unregister from agent registry
        tools_to_remove = [
            tool_name
            for tool_name, info in self._tool_infos.items()
            if info.server_name == name
        ]
        for tool_name in tools_to_remove:
            tool = self._tools.pop(tool_name, None)
            self._tool_infos.pop(tool_name, None)
            if tool:
                try:
                    from app.agents.tools.registry import ToolCategory, unregister_tool
                    unregister_tool(ToolCategory.MCP, tool.name)
                except Exception:
                    pass

        self._servers.pop(name, None)
        self._connected.discard(name)

        logger.info("mcp_server_removed", name=name, tools_removed=len(tools_to_remove))
        return True

    def _wrap_tool(self, tool_info: MCPToolInfo, config: MCPServerConfig) -> StructuredTool:
        """Wrap an MCP tool as a LangChain StructuredTool.

        Creates a dynamic Pydantic model for the input schema and wraps
        the MCP tool call in a LangChain-compatible function.

        Args:
            tool_info: Tool information from MCP server
            config: Server configuration for making calls

        Returns:
            LangChain StructuredTool
        """
        # Build dynamic input model from JSON schema
        fields: dict[str, Any] = {}
        properties = tool_info.input_schema.get("properties", {})
        required = set(tool_info.input_schema.get("required", []))

        type_map: dict[str, type] = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        for prop_name, prop_schema in properties.items():
            prop_type = type_map.get(prop_schema.get("type", "string"), str)
            prop_desc = prop_schema.get("description", "")
            default = ... if prop_name in required else prop_schema.get("default")
            fields[prop_name] = (prop_type, Field(default=default, description=prop_desc))

        # Create dynamic Pydantic model for args
        if fields:
            InputModel = create_model(f"{tool_info.name}_input", **fields)
        else:
            InputModel = create_model(f"{tool_info.name}_input")

        # Capture variables for the closure
        server_name = config.name
        tool_name = tool_info.name
        client = self

        async def _call_mcp_tool(**kwargs) -> str:
            """Call the MCP tool on the remote server."""
            try:
                result = await client.call_tool(server_name, tool_name, kwargs)

                # Format the result
                if isinstance(result, dict):
                    # MCP tool results have a 'content' field with list of content items
                    content_items = result.get("content", [])
                    if content_items:
                        texts = []
                        for item in content_items:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    texts.append(item.get("text", ""))
                                elif item.get("type") == "image":
                                    texts.append(f"[Image: {item.get('mimeType', 'unknown')}]")
                                else:
                                    texts.append(json.dumps(item))
                            else:
                                texts.append(str(item))
                        return "\n".join(texts)
                    return json.dumps(result)
                return str(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

        return StructuredTool(
            name=f"mcp_{tool_info.name}",
            description=f"[MCP: {config.name}] {tool_info.description}",
            func=lambda **kwargs: asyncio.run(_call_mcp_tool(**kwargs)),
            coroutine=_call_mcp_tool,
            args_schema=InputModel,
        )

    def get_tools(self) -> list[StructuredTool]:
        """Get all wrapped MCP tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> StructuredTool | None:
        """Get a specific MCP tool by name."""
        return self._tools.get(name)

    def get_tool_infos(self) -> list[MCPToolInfo]:
        """Get info about all discovered tools."""
        return list(self._tool_infos.values())

    def get_connected_servers(self) -> list[str]:
        """Get names of currently connected servers."""
        return list(self._connected)

    def get_server_configs(self) -> list[MCPServerConfig]:
        """Get all server configurations."""
        return list(self._servers.values())

    @property
    def is_connected(self) -> bool:
        """Whether any MCP server is connected."""
        return len(self._connected) > 0
