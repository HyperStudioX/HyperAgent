"""Tests for current deterministic passthrough routing behavior."""

from unittest.mock import patch

import pytest

from app.agents.routing import route_query


@pytest.mark.asyncio
async def test_deterministic_routing_skips_llm():
    state = {"query": "hello world", "mode": "task"}
    with patch("app.agents.routing.settings.routing_mode", "deterministic"):
        result = await route_query(state)
        assert result["selected_agent"] == "task"
        assert result["routing_confidence"] == 1.0
        assert "Deterministic routing" in result["routing_reason"]


@pytest.mark.asyncio
async def test_non_deterministic_mode_still_passthrough_routes_to_task():
    state = {"query": "hello world"}
    with patch("app.agents.routing.settings.routing_mode", "llm"):
        result = await route_query(state)
        assert result["selected_agent"] == "task"
        assert result["routing_confidence"] == 1.0
        assert result["routing_reason"] == "Deterministic passthrough routing"
