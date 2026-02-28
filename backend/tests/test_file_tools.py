"""Tests for file management tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.tools.file_tools import (
    file_find_by_name,
    file_find_in_content,
    file_read,
    file_str_replace,
    file_write,
)
from app.sandbox.runtime import CommandResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_runtime():
    """Create a mock SandboxRuntime."""
    runtime = AsyncMock()
    runtime.sandbox_id = "test-sandbox-123"
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


def _patch_sandbox(mock_sandbox_manager):
    """Return patch context managers for sandbox availability and manager."""
    return (
        patch(
            "app.agents.tools.file_tools.get_execution_sandbox_manager",
            return_value=mock_sandbox_manager,
        ),
        patch(
            "app.sandbox.provider.is_provider_available",
            return_value=(True, None),
        ),
    )


# ---------------------------------------------------------------------------
# file_read tests
# ---------------------------------------------------------------------------


class TestFileRead:
    """Tests for file_read tool."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, mock_sandbox_manager, mock_runtime):
        """Successfully read a file."""
        mock_runtime.read_file.return_value = "line1\nline2\nline3"
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_read.ainvoke({"path": "/home/user/test.txt"})
            )

        assert result["success"] is True
        assert result["content"] == "line1\nline2\nline3"

    @pytest.mark.asyncio
    async def test_read_file_with_offset_limit(self, mock_sandbox_manager, mock_runtime):
        """Read file with offset and limit."""
        mock_runtime.read_file.return_value = "line1\nline2\nline3\nline4\nline5"
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_read.ainvoke({"path": "/home/user/test.txt", "offset": 2, "limit": 2})
            )

        assert result["success"] is True
        assert result["content"] == "line2\nline3"
        assert result["lines_shown"] == 2
        assert result["total_lines"] == 5

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, mock_sandbox_manager, mock_runtime):
        """Reading a non-existent file returns error."""
        mock_runtime.read_file.side_effect = FileNotFoundError("No such file")
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_read.ainvoke({"path": "/home/user/missing.txt"})
            )

        # The error is caught by file_operations.read_file and returns success=False
        assert result["success"] is False


# ---------------------------------------------------------------------------
# file_write tests
# ---------------------------------------------------------------------------


class TestFileWrite:
    """Tests for file_write tool."""

    @pytest.mark.asyncio
    async def test_write_file_overwrite(self, mock_sandbox_manager, mock_runtime):
        """Successfully write a file in overwrite mode."""
        mock_runtime.run_command.return_value = CommandResult(exit_code=0, stdout="", stderr="")
        mock_runtime.write_file.return_value = None
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_write.ainvoke({
                    "path": "/home/user/output.txt",
                    "content": "hello world",
                })
            )

        assert result["success"] is True
        assert result["mode"] == "overwrite"

    @pytest.mark.asyncio
    async def test_write_file_append(self, mock_sandbox_manager, mock_runtime):
        """Successfully append to a file."""
        mock_runtime.read_file.return_value = "existing\n"
        mock_runtime.run_command.return_value = CommandResult(exit_code=0, stdout="", stderr="")
        mock_runtime.write_file.return_value = None
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_write.ainvoke({
                    "path": "/home/user/output.txt",
                    "content": "new line",
                    "mode": "append",
                })
            )

        assert result["success"] is True
        assert result["mode"] == "append"

    @pytest.mark.asyncio
    async def test_write_file_invalid_mode(self, mock_sandbox_manager):
        """Invalid mode returns error."""
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_write.ainvoke({
                    "path": "/home/user/output.txt",
                    "content": "hello",
                    "mode": "invalid",
                })
            )

        assert result["success"] is False
        assert "Invalid mode" in result["error"]


# ---------------------------------------------------------------------------
# file_str_replace tests
# ---------------------------------------------------------------------------


class TestFileStrReplace:
    """Tests for file_str_replace tool."""

    @pytest.mark.asyncio
    async def test_str_replace_success(self, mock_sandbox_manager, mock_runtime):
        """Successfully replace a unique string."""
        mock_runtime.read_file.return_value = "hello world"
        mock_runtime.run_command.return_value = CommandResult(exit_code=0, stdout="", stderr="")
        mock_runtime.write_file.return_value = None
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_str_replace.ainvoke({
                    "path": "/home/user/test.py",
                    "old_str": "hello",
                    "new_str": "goodbye",
                })
            )

        assert result["success"] is True
        assert result["operation"] == "str_replace"

    @pytest.mark.asyncio
    async def test_str_replace_not_found(self, mock_sandbox_manager, mock_runtime):
        """Replacing a string that doesn't exist returns error."""
        mock_runtime.read_file.return_value = "hello world"
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_str_replace.ainvoke({
                    "path": "/home/user/test.py",
                    "old_str": "missing",
                    "new_str": "replacement",
                })
            )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_str_replace_multiple_occurrences(self, mock_sandbox_manager, mock_runtime):
        """Replacing a string that appears multiple times returns error."""
        mock_runtime.read_file.return_value = "hello hello world"
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_str_replace.ainvoke({
                    "path": "/home/user/test.py",
                    "old_str": "hello",
                    "new_str": "goodbye",
                })
            )

        assert result["success"] is False
        assert "2 times" in result["error"]


# ---------------------------------------------------------------------------
# file_find_by_name tests
# ---------------------------------------------------------------------------


class TestFileFindByName:
    """Tests for file_find_by_name tool."""

    @pytest.mark.asyncio
    async def test_find_files_success(self, mock_sandbox_manager, mock_runtime):
        """Successfully find files by pattern."""
        mock_runtime.run_command.return_value = CommandResult(
            exit_code=0,
            stdout="/home/user/app.py\n/home/user/lib/utils.py\n",
            stderr="",
        )
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_find_by_name.ainvoke({"pattern": "*.py"})
            )

        assert result["success"] is True
        assert result["count"] == 2
        assert "/home/user/app.py" in result["files"]

    @pytest.mark.asyncio
    async def test_find_files_no_matches(self, mock_sandbox_manager, mock_runtime):
        """Finding no files returns empty list."""
        mock_runtime.run_command.return_value = CommandResult(
            exit_code=0, stdout="", stderr=""
        )
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_find_by_name.ainvoke({"pattern": "*.xyz"})
            )

        assert result["success"] is True
        assert result["count"] == 0
        assert result["files"] == []


# ---------------------------------------------------------------------------
# file_find_in_content tests
# ---------------------------------------------------------------------------


class TestFileFindInContent:
    """Tests for file_find_in_content tool."""

    @pytest.mark.asyncio
    async def test_find_in_content_success(self, mock_sandbox_manager, mock_runtime):
        """Successfully search file contents."""
        mock_runtime.run_command.return_value = CommandResult(
            exit_code=0,
            stdout="/home/user/app.py:10:def hello():\n/home/user/lib.py:5:    hello()\n",
            stderr="",
        )
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_find_in_content.ainvoke({"pattern": "hello"})
            )

        assert result["success"] is True
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_find_in_content_with_include(self, mock_sandbox_manager, mock_runtime):
        """Search with file pattern filter."""
        mock_runtime.run_command.return_value = CommandResult(
            exit_code=0,
            stdout="/home/user/app.py:10:import os\n",
            stderr="",
        )
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_find_in_content.ainvoke({
                    "pattern": "import os",
                    "include": "*.py",
                })
            )

        assert result["success"] is True
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_find_in_content_no_matches(self, mock_sandbox_manager, mock_runtime):
        """No matches returns empty list."""
        mock_runtime.run_command.return_value = CommandResult(
            exit_code=1, stdout="", stderr=""
        )
        p1, p2 = _patch_sandbox(mock_sandbox_manager)

        with p1, p2:
            result = json.loads(
                await file_find_in_content.ainvoke({"pattern": "nonexistent_xyz"})
            )

        assert result["success"] is True
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# Registry integration tests
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tests that file tools are properly registered."""

    def test_file_ops_category_exists(self):
        """FILE_OPS category should exist in ToolCategory."""
        from app.agents.tools.registry import ToolCategory

        assert hasattr(ToolCategory, "FILE_OPS")
        assert ToolCategory.FILE_OPS.value == "file_ops"

    def test_file_tools_in_catalog(self):
        """File tools should be in the TOOL_CATALOG."""
        from app.agents.tools.registry import TOOL_CATALOG, ToolCategory

        file_tools = TOOL_CATALOG.get(ToolCategory.FILE_OPS, [])
        tool_names = {t.name for t in file_tools}

        assert "file_read" in tool_names
        assert "file_write" in tool_names
        assert "file_str_replace" in tool_names
        assert "file_find_by_name" in tool_names
        assert "file_find_in_content" in tool_names

    def test_file_ops_in_task_agent_mapping(self):
        """FILE_OPS should be in the TASK agent's tool mapping."""
        from app.agents.state import AgentType
        from app.agents.tools.registry import AGENT_TOOL_MAPPING, ToolCategory

        task_categories = AGENT_TOOL_MAPPING[AgentType.TASK.value]
        assert ToolCategory.FILE_OPS in task_categories
