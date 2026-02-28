"""Tests for Plan-Act-Verify enhancements."""

import pytest

from app.agents.subagents.task import _build_todo_md


class TestBuildTodoMd:
    """Tests for the _build_todo_md helper function."""

    def test_all_pending(self):
        steps = [
            {"step_number": 1, "action": "Search web", "tool_or_skill": "web_search"},
            {"step_number": 2, "action": "Analyze data", "tool_or_skill": "execute_code"},
        ]
        result = _build_todo_md(steps)
        assert "[ ] Step 1: Search web" in result
        assert "[ ] Step 2: Analyze data" in result
        assert "Tool: web_search" in result
        assert "[x]" not in result

    def test_some_completed(self):
        steps = [
            {"step_number": 1, "action": "Search web"},
            {"step_number": 2, "action": "Analyze data"},
            {"step_number": 3, "action": "Write report"},
        ]
        result = _build_todo_md(steps, completed_up_to=2)
        assert "[x] Step 1: Search web" in result
        assert "[x] Step 2: Analyze data" in result
        assert "[ ] Step 3: Write report" in result

    def test_all_completed(self):
        steps = [
            {"step_number": 1, "action": "Step A"},
            {"step_number": 2, "action": "Step B"},
        ]
        result = _build_todo_md(steps, completed_up_to=2)
        assert "[ ]" not in result
        assert "[x] Step 1" in result
        assert "[x] Step 2" in result

    def test_empty_steps(self):
        result = _build_todo_md([])
        assert "# Task Plan" in result

    def test_step_without_tool(self):
        steps = [{"step_number": 1, "action": "Think about it"}]
        result = _build_todo_md(steps)
        assert "[ ] Step 1: Think about it" in result
        assert "Tool:" not in result

    def test_header_present(self):
        result = _build_todo_md([{"step_number": 1, "action": "test"}])
        assert result.startswith("# Task Plan")


class TestPlanRevisionState:
    """Tests for plan_revision_count in TaskState."""

    def test_state_accepts_plan_revision_count(self):
        from app.agents.state import TaskState
        state: TaskState = {
            "query": "test",
            "plan_revision_count": 1,
        }
        assert state["plan_revision_count"] == 1

    def test_state_defaults_without_plan_revision(self):
        from app.agents.state import TaskState
        state: TaskState = {"query": "test"}
        assert state.get("plan_revision_count") is None
