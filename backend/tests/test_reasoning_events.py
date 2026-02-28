"""Tests for the reasoning transparency event type."""

import pytest

from app.agents.events import (
    EventType,
    ReasoningEvent,
    reasoning,
)


class TestReasoningEventModel:
    """Tests for the ReasoningEvent Pydantic model."""

    def test_create_with_required_fields(self):
        event = ReasoningEvent(thinking="Routing to task agent for code generation")
        assert event.type == "reasoning"
        assert event.thinking == "Routing to task agent for code generation"
        assert event.confidence is None
        assert event.context is None
        assert event.timestamp > 0

    def test_create_with_all_fields(self):
        event = ReasoningEvent(
            thinking="High confidence routing to research agent",
            confidence=0.95,
            context="routing",
        )
        assert event.type == "reasoning"
        assert event.thinking == "High confidence routing to research agent"
        assert event.confidence == 0.95
        assert event.context == "routing"

    def test_serialization(self):
        event = ReasoningEvent(
            thinking="Error recovery: retrying with corrected inputs",
            confidence=0.7,
            context="error_recovery",
        )
        data = event.model_dump()
        assert data["type"] == "reasoning"
        assert data["thinking"] == "Error recovery: retrying with corrected inputs"
        assert data["confidence"] == 0.7
        assert data["context"] == "error_recovery"
        assert "timestamp" in data

    def test_serialization_minimal(self):
        event = ReasoningEvent(thinking="Simple reasoning")
        data = event.model_dump()
        assert data["type"] == "reasoning"
        assert data["thinking"] == "Simple reasoning"
        assert data["confidence"] is None
        assert data["context"] is None


class TestReasoningFactory:
    """Tests for the reasoning() factory function."""

    def test_basic_call(self):
        result = reasoning(thinking="Selecting web_search tool")
        assert result["type"] == "reasoning"
        assert result["thinking"] == "Selecting web_search tool"
        assert result["confidence"] is None
        assert result["context"] is None
        assert "timestamp" in result

    def test_with_confidence(self):
        result = reasoning(
            thinking="Routing to task agent",
            confidence=0.9,
        )
        assert result["confidence"] == 0.9

    def test_with_context(self):
        result = reasoning(
            thinking="Tool error classified as input. Recovery: check arguments",
            context="error_recovery",
        )
        assert result["context"] == "error_recovery"

    def test_with_all_args(self):
        result = reasoning(
            thinking="Routing to research: comprehensive multi-source analysis needed",
            confidence=0.85,
            context="routing",
        )
        assert result["type"] == "reasoning"
        assert result["thinking"] == "Routing to research: comprehensive multi-source analysis needed"
        assert result["confidence"] == 0.85
        assert result["context"] == "routing"

    def test_returns_dict(self):
        result = reasoning(thinking="test")
        assert isinstance(result, dict)


class TestEventTypeEnum:
    """Tests that the REASONING enum value exists."""

    def test_reasoning_enum_exists(self):
        assert EventType.REASONING == "reasoning"
        assert EventType.REASONING.value == "reasoning"
