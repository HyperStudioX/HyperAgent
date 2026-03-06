import json

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.context_compression import inject_summary_as_context, is_context_summary_message
from app.agents.context_policy import apply_context_policy
from app.agents.tools.handoff import truncate_shared_memory
from app.agents.tools.scratchpad import read_scratchpad, write_scratchpad


def test_summary_injection_is_singleton():
    messages = [SystemMessage(content="sys"), HumanMessage(content="hello")]
    once = inject_summary_as_context(messages, "summary v1")
    twice = inject_summary_as_context(once, "summary v2")

    summary_messages = [m for m in twice if is_context_summary_message(m)]
    assert len(summary_messages) == 1
    assert "summary v2" in summary_messages[0].content
    assert "summary v1" not in summary_messages[0].content


@pytest.mark.asyncio
async def test_context_policy_does_not_double_count_existing_summary(monkeypatch):
    messages = [SystemMessage(content="sys"), HumanMessage(content="hello")]
    messages = inject_summary_as_context(messages, "existing summary")
    called = {"compress": False}

    async def _fake_compress(self, *args, **kwargs):
        called["compress"] = True
        return "new summary", args[0]

    monkeypatch.setattr("app.agents.context_compression.ContextCompressor.compress", _fake_compress)

    def _no_op_truncator(msgs, max_tokens=0, preserve_recent=0):
        return msgs, False

    _, _, events, _ = await apply_context_policy(
        messages,
        existing_summary="x" * 5000,
        provider="anthropic",
        locale="en",
        compression_enabled=True,
        compression_token_threshold=200,
        compression_preserve_recent=10,
        truncate_max_tokens=100000,
        truncate_preserve_recent=4,
        truncator=_no_op_truncator,
        enforce_summary_singleton_flag=True,
    )

    assert called["compress"] is False
    assert not any(e.get("description", "").startswith("Context compressed") for e in events)


def test_shared_memory_truncation_respects_budget():
    memory = {
        "research_findings": "A" * 5000,
        "research_sources": "B" * 5000,
        "generated_code": "C" * 5000,
        "code_language": "python" * 300,
        "execution_results": "D" * 5000,
        "additional_context": "E" * 5000,
    }
    budget = 800
    truncated = truncate_shared_memory(memory, budget=budget)
    total_size = sum(len(v) for v in truncated.values() if isinstance(v, str))
    assert total_size <= budget


@pytest.mark.asyncio
async def test_scratchpad_tools_session_scope(monkeypatch):
    monkeypatch.setattr("app.config.settings.context_offloading_enabled", True)

    write_result = await write_scratchpad.ainvoke({
        "notes": "session notes",
        "scope": "session",
        "user_id": "u1",
        "task_id": "t1",
    })
    write_payload = json.loads(write_result)
    assert write_payload["success"] is True

    read_result = await read_scratchpad.ainvoke({
        "reasoning": "need notes",
        "scope": "session",
        "user_id": "u1",
        "task_id": "t1",
    })
    read_payload = json.loads(read_result)
    assert read_payload["found"] is True
    assert "session notes" in read_payload["notes"]


@pytest.mark.asyncio
async def test_scratchpad_tools_persistent_cross_thread_with_namespace(monkeypatch):
    monkeypatch.setattr("app.config.settings.context_offloading_enabled", True)
    monkeypatch.setattr("app.config.settings.context_offloading_persistent_enabled", True)

    await write_scratchpad.ainvoke({
        "notes": "shared persistent notes",
        "scope": "persistent",
        "namespace": "shared-key",
        "user_id": "u2",
        "task_id": "thread-a",
    })

    read_result = await read_scratchpad.ainvoke({
        "reasoning": "reuse previous thread notes",
        "scope": "persistent",
        "namespace": "shared-key",
        "user_id": "u2",
        "task_id": "thread-b",
    })
    payload = json.loads(read_result)
    assert payload["found"] is True
    assert "shared persistent notes" in payload["notes"]

