"""Tests for skill-driven loop hardening changes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.agents.supervisor import task_node
from app.models.schemas import UnifiedQueryRequest
from app.workers.tasks.research import run_research_task


@pytest.mark.asyncio
async def test_task_node_skips_parallel_executor_when_explicit_skill_selected():
    """Explicit skills must bypass parallel decomposition and run task subgraph."""
    state = {
        "query": "Research this topic deeply",
        "mode": "task",
        "parallel_eligible": True,
        "skills": ["deep_research"],
        "messages": [],
        "attachment_ids": [],
        "image_attachments": [],
    }

    with (
        patch("app.config.settings.parallel_executor_v1", True),
        patch("app.agents.parallel.GeneralParallelExecutor") as mock_executor_cls,
        patch(
            "app.agents.supervisor.task_subgraph.ainvoke",
            new=AsyncMock(return_value={"response": "ok", "events": []}),
        ) as mock_task_invoke,
        patch("app.agents.supervisor._process_handoff", new=AsyncMock(return_value={})),
    ):
        result = await task_node(state)

    assert result["response"] == "ok"
    assert any(
        e.get("type") == "reasoning" and "Skipping parallel decomposition" in e.get("thinking", "")
        for e in result.get("events", [])
    )
    mock_task_invoke.assert_awaited_once()
    mock_executor_cls.assert_not_called()


@pytest.mark.asyncio
async def test_run_research_task_passes_user_and_task_identity_to_supervisor():
    """Background worker should preserve user_id/task_id when invoking supervisor."""

    class _DummyResult:
        def fetchone(self):
            return ("task-1",)

    class _DummySession:
        def __init__(self):
            self.commit = AsyncMock()
            self.rollback = AsyncMock()

        async def execute(self, *args, **kwargs):
            return _DummyResult()

        def expire_all(self):
            return None

    class _SessionContext:
        def __init__(self, db):
            self.db = db

        async def __aenter__(self):
            return self.db

        async def __aexit__(self, exc_type, exc, tb):
            return False

    db = _DummySession()
    ctx = {
        "redis": SimpleNamespace(publish=AsyncMock(return_value=1)),
        "job_id": "job-123",
        "worker_name": "worker-a",
    }

    async def _run_events(**kwargs):
        yield {"type": "complete"}

    with (
        patch("app.workers.tasks.research.async_session_maker", return_value=_SessionContext(db)),
        patch(
            "app.workers.tasks.research.agent_supervisor.run",
            side_effect=_run_events,
        ) as mock_run,
        patch(
            "app.workers.tasks.research.deep_research_repository.get_task",
            new=AsyncMock(return_value=MagicMock()),
        ),
        patch("app.workers.tasks.research.deep_research_repository.clear_task_steps", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.clear_task_sources", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.update_task_report", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.update_task_status", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.update_task_worker_info", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.update_task_progress", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.add_step", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.update_step_status", new=AsyncMock()),
        patch("app.workers.tasks.research.deep_research_repository.add_source", new=AsyncMock()),
    ):
        result = await run_research_task(
            ctx=ctx,
            task_id="task-1",
            query="Investigate market trends",
            depth="fast",
            user_id="user-1",
        )

    assert result["status"] == "completed"
    assert mock_run.call_args.kwargs["task_id"] == "task-1"
    assert mock_run.call_args.kwargs["user_id"] == "user-1"


def test_unified_query_request_rejects_multiple_skills():
    """API schema should reject requests that include multiple skills."""
    with pytest.raises(ValidationError, match="Only one skill can be selected per request"):
        UnifiedQueryRequest(
            message="test",
            skills=["deep_research", "data_analysis"],
        )


def test_unified_query_request_accepts_single_skill():
    """API schema should accept a request with exactly one skill."""
    with patch(
        "app.services.skill_registry.skill_registry.list_skills",
        return_value=[SimpleNamespace(id="deep_research")],
    ):
        req = UnifiedQueryRequest(
            message="test",
            skills=["deep_research"],
        )
    assert req.skills == ["deep_research"]
