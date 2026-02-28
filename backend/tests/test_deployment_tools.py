"""Tests for deployment / port exposure tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.tools.deployment import (
    _active_deployments,
    deploy_expose_port,
    deploy_get_url,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runtime():
    """Create a mock SandboxRuntime."""
    runtime = AsyncMock()
    runtime.sandbox_id = "test-sandbox-123"
    runtime.get_host_url.return_value = "https://test-sandbox-123-3000.e2b.dev"
    return runtime


@pytest.fixture
def mock_session(mock_runtime):
    """Create a mock ExecutionSandboxSession."""
    executor = MagicMock()
    executor.sandbox_id = "test-sandbox-123"
    executor.get_runtime.return_value = mock_runtime

    session = MagicMock()
    session.executor = executor
    session.sandbox_id = "test-sandbox-123"
    return session


@pytest.fixture
def mock_sandbox_manager(mock_session):
    """Create a mock ExecutionSandboxManager."""
    manager = AsyncMock()
    manager.get_or_create_sandbox.return_value = mock_session
    return manager


@pytest.fixture(autouse=True)
def clean_active_deployments():
    """Clean up active deployments before and after each test."""
    _active_deployments.clear()
    yield
    _active_deployments.clear()


def _patch_sandbox(mock_sandbox_manager):
    """Return patch context managers for sandbox availability and manager."""
    return (
        patch(
            "app.agents.tools.deployment.get_execution_sandbox_manager",
            return_value=mock_sandbox_manager,
        ),
        patch(
            "app.sandbox.provider.is_provider_available",
            return_value=(True, None),
        ),
    )


# ---------------------------------------------------------------------------
# deploy_expose_port tests
# ---------------------------------------------------------------------------


class TestDeployExposePort:
    """Tests for deploy_expose_port tool."""

    @pytest.mark.asyncio
    async def test_expose_port_success(self, mock_sandbox_manager, mock_runtime):
        """Successfully expose a port and get a public URL."""
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await deploy_expose_port.ainvoke({"port": 3000})
            )

        assert result["success"] is True
        assert result["operation"] == "expose_port"
        assert result["port"] == 3000
        assert result["url"] == "https://test-sandbox-123-3000.e2b.dev"
        assert "deployment_id" in result
        assert result["deployment_id"].startswith("deploy_")
        assert result["name"] == "port-3000"
        assert result["sandbox_id"] == "test-sandbox-123"

    @pytest.mark.asyncio
    async def test_expose_port_with_name(self, mock_sandbox_manager, mock_runtime):
        """Expose a port with a custom friendly name."""
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await deploy_expose_port.ainvoke({
                    "port": 8080,
                    "name": "my-api",
                })
            )

        assert result["success"] is True
        assert result["name"] == "my-api"
        assert result["port"] == 8080

    @pytest.mark.asyncio
    async def test_expose_port_tracks_deployment(self, mock_sandbox_manager, mock_runtime):
        """Exposing a port stores the deployment in _active_deployments."""
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await deploy_expose_port.ainvoke({"port": 5000})
            )

        deployment_id = result["deployment_id"]
        assert deployment_id in _active_deployments
        deployment = _active_deployments[deployment_id]
        assert deployment["port"] == 5000
        assert deployment["url"] == "https://test-sandbox-123-3000.e2b.dev"
        assert deployment["sandbox_id"] == "test-sandbox-123"
        assert "created_at" in deployment

    @pytest.mark.asyncio
    async def test_expose_port_sandbox_unavailable(self, mock_sandbox_manager):
        """Returns error when sandbox is unavailable."""
        with patch(
            "app.agents.tools.deployment.get_execution_sandbox_manager",
            return_value=mock_sandbox_manager,
        ), patch(
            "app.sandbox.provider.is_provider_available",
            return_value=(False, "No sandbox configured"),
        ):
            result = json.loads(
                await deploy_expose_port.ainvoke({"port": 3000})
            )

        assert result["success"] is False
        assert "No sandbox configured" in result["error"]

    @pytest.mark.asyncio
    async def test_expose_port_runtime_error(self, mock_sandbox_manager, mock_runtime):
        """Returns error when get_host_url raises an exception."""
        mock_runtime.get_host_url.side_effect = Exception("Port not available")
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await deploy_expose_port.ainvoke({"port": 9999})
            )

        assert result["success"] is False
        assert "Port not available" in result["error"]


# ---------------------------------------------------------------------------
# deploy_get_url tests
# ---------------------------------------------------------------------------


class TestDeployGetUrl:
    """Tests for deploy_get_url tool."""

    @pytest.mark.asyncio
    async def test_get_url_success(self):
        """Retrieve URL for an existing deployment."""
        _active_deployments["deploy_abc12345"] = {
            "port": 3000,
            "url": "https://test-sandbox-123-3000.e2b.dev",
            "name": "frontend",
            "sandbox_id": "test-sandbox-123",
            "created_at": "2026-02-28T12:00:00+00:00",
        }

        result = json.loads(
            await deploy_get_url.ainvoke({"deployment_id": "deploy_abc12345"})
        )

        assert result["success"] is True
        assert result["operation"] == "get_url"
        assert result["deployment_id"] == "deploy_abc12345"
        assert result["port"] == 3000
        assert result["url"] == "https://test-sandbox-123-3000.e2b.dev"
        assert result["name"] == "frontend"
        assert result["sandbox_id"] == "test-sandbox-123"
        assert result["status"] == "active"
        assert result["created_at"] == "2026-02-28T12:00:00+00:00"

    @pytest.mark.asyncio
    async def test_get_url_not_found(self):
        """Returns error for unknown deployment_id."""
        result = json.loads(
            await deploy_get_url.ainvoke({"deployment_id": "deploy_nonexistent"})
        )

        assert result["success"] is False
        assert "not found" in result["error"]
        assert "deploy_nonexistent" in result["error"]

    @pytest.mark.asyncio
    async def test_get_url_lists_active_deployments(self):
        """Error message includes list of active deployment IDs."""
        _active_deployments["deploy_aaa"] = {
            "port": 3000,
            "url": "http://localhost:3000",
            "name": "app",
            "sandbox_id": "sb-1",
            "created_at": "2026-02-28T12:00:00+00:00",
        }
        _active_deployments["deploy_bbb"] = {
            "port": 8080,
            "url": "http://localhost:8080",
            "name": "api",
            "sandbox_id": "sb-1",
            "created_at": "2026-02-28T12:00:00+00:00",
        }

        result = json.loads(
            await deploy_get_url.ainvoke({"deployment_id": "deploy_unknown"})
        )

        assert result["success"] is False
        assert "deploy_aaa" in result["error"]
        assert "deploy_bbb" in result["error"]


# ---------------------------------------------------------------------------
# _active_deployments tracking tests
# ---------------------------------------------------------------------------


class TestActiveDeploymentsTracking:
    """Tests for module-level _active_deployments dictionary."""

    @pytest.mark.asyncio
    async def test_multiple_deployments_tracked(self, mock_sandbox_manager, mock_runtime):
        """Multiple deploy_expose_port calls create separate entries."""
        mock_runtime.get_host_url.side_effect = [
            "https://sb-3000.e2b.dev",
            "https://sb-8080.e2b.dev",
        ]
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result1 = json.loads(
                await deploy_expose_port.ainvoke({"port": 3000, "name": "frontend"})
            )
            result2 = json.loads(
                await deploy_expose_port.ainvoke({"port": 8080, "name": "api"})
            )

        assert len(_active_deployments) == 2
        assert result1["deployment_id"] != result2["deployment_id"]

        dep1 = _active_deployments[result1["deployment_id"]]
        dep2 = _active_deployments[result2["deployment_id"]]
        assert dep1["port"] == 3000
        assert dep1["name"] == "frontend"
        assert dep2["port"] == 8080
        assert dep2["name"] == "api"

    @pytest.mark.asyncio
    async def test_deployment_created_at_populated(self, mock_sandbox_manager, mock_runtime):
        """Deployment entries have a created_at timestamp."""
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await deploy_expose_port.ainvoke({"port": 4000})
            )

        deployment = _active_deployments[result["deployment_id"]]
        assert "created_at" in deployment
        # Should be a valid ISO format string
        assert "T" in deployment["created_at"]


# ---------------------------------------------------------------------------
# Registry integration tests
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tests that deployment tools are properly registered."""

    def test_deploy_category_exists(self):
        """DEPLOY category should exist in ToolCategory."""
        from app.agents.tools.registry import ToolCategory

        assert hasattr(ToolCategory, "DEPLOY")
        assert ToolCategory.DEPLOY.value == "deploy"

    def test_deploy_tools_in_catalog(self):
        """Deployment tools should be in the TOOL_CATALOG."""
        from app.agents.tools.registry import TOOL_CATALOG, ToolCategory

        deploy_tools = TOOL_CATALOG.get(ToolCategory.DEPLOY, [])
        tool_names = {t.name for t in deploy_tools}

        assert "deploy_expose_port" in tool_names
        assert "deploy_get_url" in tool_names

    def test_deploy_in_task_agent_mapping(self):
        """DEPLOY should be in the TASK agent's tool mapping."""
        from app.agents.state import AgentType
        from app.agents.tools.registry import AGENT_TOOL_MAPPING, ToolCategory

        task_categories = AGENT_TOOL_MAPPING[AgentType.TASK.value]
        assert ToolCategory.DEPLOY in task_categories

    def test_deploy_not_in_research_agent_mapping(self):
        """DEPLOY should NOT be in the RESEARCH agent's tool mapping."""
        from app.agents.state import AgentType
        from app.agents.tools.registry import AGENT_TOOL_MAPPING, ToolCategory

        research_categories = AGENT_TOOL_MAPPING[AgentType.RESEARCH.value]
        assert ToolCategory.DEPLOY not in research_categories
