"""Regression tests for deep research skill report-writing behavior."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agents.skills.builtin.deep_research_skill import DeepResearchSkill


class _FakeReactBoundLLM:
    async def ainvoke(self, _messages):
        # No tool calls -> finishes research gathering and proceeds to report writing
        return SimpleNamespace(content="SYNTHETIC_FINDINGS", tool_calls=[], usage_metadata={})


class _FakeReactLLM:
    def bind_tools(self, _tools):
        return _FakeReactBoundLLM()


class _FakeWriterLLM:
    def __init__(self, chunks: list[str] | None = None, error: Exception | None = None):
        self._chunks = chunks or []
        self._error = error

    async def astream(self, _messages):
        if self._error:
            raise self._error
        for chunk in self._chunks:
            yield SimpleNamespace(content=chunk, usage_metadata={})


def _initial_skill_state() -> dict:
    return {
        "skill_id": "deep_research",
        "input_params": {"query": "test query", "depth": "fast"},
        "output": {},
        "error": None,
        "events": [],
        "iterations": 0,
        "user_id": "user-1",
        "task_id": "task-1",
        "invocation_depth": 0,
        "tier": None,
        "pending_events": [],
    }


@pytest.mark.asyncio
async def test_deep_research_tokens_emit_only_after_guardrail_sanitization():
    """Token events should reflect sanitized final report, never raw unsafe chunks."""

    def _choose_llm(*_args, **_kwargs):
        # First call is react_loop, second call is write_report
        if not hasattr(_choose_llm, "count"):
            _choose_llm.count = 0  # type: ignore[attr-defined]
        _choose_llm.count += 1  # type: ignore[attr-defined]
        if _choose_llm.count == 1:  # type: ignore[attr-defined]
            return _FakeReactLLM()
        return _FakeWriterLLM(chunks=["UNSAFE_RAW_CONTENT"])

    async def _scan(_text, _query):
        return SimpleNamespace(blocked=False, sanitized_content="SAFE_REPORT")

    with (
        patch(
            "app.agents.skills.builtin.deep_research_skill.llm_service.choose_llm_for_task",
            side_effect=_choose_llm,
        ),
        patch(
            "app.agents.skills.builtin.deep_research_skill.output_scanner.scan",
            side_effect=_scan,
        ),
        patch(
            "app.agents.skills.builtin.deep_research_skill._get_research_tools",
            return_value=[],
        ),
    ):
        graph = DeepResearchSkill().create_graph()
        final_state = await graph.ainvoke(_initial_skill_state())

    pending_events = final_state.get("pending_events", [])
    token_text = "".join(e.get("content", "") for e in pending_events if e.get("type") == "token")
    assert "UNSAFE_RAW_CONTENT" not in token_text
    assert "SAFE_REPORT" in token_text
    assert final_state["output"]["report"] == "SAFE_REPORT"


@pytest.mark.asyncio
async def test_deep_research_report_stream_error_fails_skill_execution():
    """Report LLM failures should propagate as skill failure, not success output."""

    def _choose_llm(*_args, **_kwargs):
        if not hasattr(_choose_llm, "count"):
            _choose_llm.count = 0  # type: ignore[attr-defined]
        _choose_llm.count += 1  # type: ignore[attr-defined]
        if _choose_llm.count == 1:  # type: ignore[attr-defined]
            return _FakeReactLLM()
        return _FakeWriterLLM(error=RuntimeError("writer boom"))

    async def _scan(_text, _query):
        return SimpleNamespace(blocked=False, sanitized_content=None)

    with (
        patch(
            "app.agents.skills.builtin.deep_research_skill.llm_service.choose_llm_for_task",
            side_effect=_choose_llm,
        ),
        patch(
            "app.agents.skills.builtin.deep_research_skill.output_scanner.scan",
            side_effect=_scan,
        ),
        patch(
            "app.agents.skills.builtin.deep_research_skill._get_research_tools",
            return_value=[],
        ),
    ):
        graph = DeepResearchSkill().create_graph()
        final_state = await graph.ainvoke(_initial_skill_state())

    assert "Report generation failed" in (final_state.get("error") or "")
    assert final_state.get("output", {}) == {}
