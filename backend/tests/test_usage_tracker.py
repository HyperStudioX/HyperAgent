"""Tests for the usage tracking service."""

import pytest

from app.services.usage_tracker import (
    UsageRecord,
    UsageTracker,
    _lookup_pricing,
    calculate_cost,
    clear_records,
    create_usage_tracker,
    get_all_records,
    get_usage_summary,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_records():
    """Ensure global records are clean before and after each test."""
    clear_records()
    yield
    clear_records()


# ---------------------------------------------------------------------------
# Pricing / cost tests
# ---------------------------------------------------------------------------


class TestPricingLookup:
    def test_claude_opus(self):
        inp, out, cached = _lookup_pricing("claude-opus-4-20250514")
        assert inp == 15.0
        assert out == 75.0
        assert cached == 1.5

    def test_claude_sonnet(self):
        inp, out, cached = _lookup_pricing("claude-sonnet-4-20250514")
        assert inp == 3.0
        assert out == 15.0
        assert cached == 0.3

    def test_claude_haiku(self):
        inp, out, cached = _lookup_pricing("claude-3-5-haiku-20241022")
        assert inp == 0.25
        assert out == 1.25

    def test_gpt4o(self):
        inp, out, _ = _lookup_pricing("gpt-4o")
        assert inp == 2.50
        assert out == 10.0

    def test_gpt4o_mini_most_specific_match(self):
        """gpt-4o-mini should match the more specific key, not gpt-4o."""
        inp, out, _ = _lookup_pricing("gpt-4o-mini")
        assert inp == 0.15
        assert out == 0.60

    def test_gemini_flash(self):
        inp, out, _ = _lookup_pricing("gemini-2.5-flash")
        assert inp == 0.15
        assert out == 0.60

    def test_unknown_model_falls_back(self):
        inp, out, cached = _lookup_pricing("some-unknown-model-v99")
        # Should return default pricing
        assert inp == 3.0
        assert out == 15.0
        assert cached == 0.3


class TestCostCalculation:
    def test_basic_cost(self):
        # 1000 input tokens + 500 output tokens with claude-sonnet pricing
        cost = calculate_cost("claude-sonnet-4-20250514", 1000, 500)
        # (1000/1M)*3.0 + (500/1M)*15.0 = 0.003 + 0.0075 = 0.0105
        assert cost == pytest.approx(0.0105, abs=1e-6)

    def test_cost_with_cached_tokens(self):
        # 1000 total input, 600 cached, 500 output with claude-opus
        cost = calculate_cost("claude-opus-4-20250514", 1000, 500, cached_tokens=600)
        # regular_input = 400, cached = 600
        # (400/1M)*15.0 + (600/1M)*1.5 + (500/1M)*75.0
        # = 0.006 + 0.0009 + 0.0375 = 0.0444
        assert cost == pytest.approx(0.0444, abs=1e-6)

    def test_zero_tokens(self):
        cost = calculate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_cached_greater_than_input_clamps_to_zero(self):
        # Edge case: cached > input should not go negative
        cost = calculate_cost("claude-sonnet-4-20250514", 100, 200, cached_tokens=500)
        # regular_input = max(100-500, 0) = 0
        # (0)*3.0 + (500/1M)*0.3 + (200/1M)*15.0 = 0 + 0.00015 + 0.003 = 0.00315
        assert cost == pytest.approx(0.00315, abs=1e-6)


# ---------------------------------------------------------------------------
# UsageRecord tests
# ---------------------------------------------------------------------------


class TestUsageRecord:
    def test_record_creation(self):
        record = UsageRecord(
            conversation_id="conv-123",
            user_id="user-456",
            model="claude-sonnet-4-20250514",
            tier="pro",
            provider="anthropic",
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=200,
            cost_usd=0.01,
        )
        assert record.conversation_id == "conv-123"
        assert record.user_id == "user-456"
        assert record.model == "claude-sonnet-4-20250514"
        assert record.tier == "pro"
        assert record.input_tokens == 1000
        assert record.timestamp is not None


# ---------------------------------------------------------------------------
# UsageTracker callback tests
# ---------------------------------------------------------------------------


class TestUsageTracker:
    @pytest.mark.asyncio
    async def test_on_llm_end_captures_tokens(self):
        """Verify the callback extracts token data from LLM response."""
        from unittest.mock import MagicMock

        tracker = UsageTracker(
            conversation_id="conv-1",
            user_id="user-1",
            tier="pro",
            provider="anthropic",
        )

        # Simulate an LLMResult with token usage
        response = MagicMock()
        response.llm_output = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
            "model_name": "claude-sonnet-4-20250514",
        }

        await tracker.on_llm_end(response)

        assert len(tracker.records) == 1
        record = tracker.records[0]
        assert record.input_tokens == 100
        assert record.output_tokens == 50
        assert record.cached_tokens == 0
        assert record.model == "claude-sonnet-4-20250514"
        assert record.cost_usd > 0

    @pytest.mark.asyncio
    async def test_on_llm_end_with_cached_tokens(self):
        from unittest.mock import MagicMock

        tracker = UsageTracker(conversation_id="conv-2", tier="max", provider="anthropic")

        response = MagicMock()
        response.llm_output = {
            "token_usage": {
                "prompt_tokens": 500,
                "completion_tokens": 200,
                "cache_read_input_tokens": 300,
            },
            "model_name": "claude-opus-4-20250514",
        }

        await tracker.on_llm_end(response)

        assert len(tracker.records) == 1
        record = tracker.records[0]
        assert record.input_tokens == 500
        assert record.output_tokens == 200
        assert record.cached_tokens == 300

    @pytest.mark.asyncio
    async def test_on_llm_end_skips_zero_tokens(self):
        from unittest.mock import MagicMock

        tracker = UsageTracker(conversation_id="conv-3")

        response = MagicMock()
        response.llm_output = {
            "token_usage": {},
            "model_name": "unknown",
        }

        await tracker.on_llm_end(response)
        assert len(tracker.records) == 0

    @pytest.mark.asyncio
    async def test_on_llm_end_handles_missing_llm_output(self):
        from unittest.mock import MagicMock

        tracker = UsageTracker(conversation_id="conv-4")

        response = MagicMock()
        response.llm_output = None

        # Should not raise
        await tracker.on_llm_end(response)
        assert len(tracker.records) == 0

    @pytest.mark.asyncio
    async def test_on_llm_end_does_not_raise_on_error(self):
        """The callback should never let errors propagate."""
        from unittest.mock import MagicMock, PropertyMock

        tracker = UsageTracker(conversation_id="conv-5")

        response = MagicMock()
        # Force an exception when accessing llm_output
        type(response).llm_output = PropertyMock(side_effect=RuntimeError("boom"))

        # Should not raise
        await tracker.on_llm_end(response)
        assert len(tracker.records) == 0

    def test_get_total_tokens(self):
        tracker = UsageTracker(conversation_id="conv-6")
        tracker.records.append(
            UsageRecord(
                conversation_id="conv-6",
                user_id=None,
                model="gpt-4o",
                tier="pro",
                provider="openai",
                input_tokens=100,
                output_tokens=50,
                cached_tokens=0,
                cost_usd=0.001,
            )
        )
        tracker.records.append(
            UsageRecord(
                conversation_id="conv-6",
                user_id=None,
                model="gpt-4o",
                tier="pro",
                provider="openai",
                input_tokens=200,
                output_tokens=100,
                cached_tokens=50,
                cost_usd=0.002,
            )
        )

        totals = tracker.get_total_tokens()
        assert totals["input_tokens"] == 300
        assert totals["output_tokens"] == 150
        assert totals["cached_tokens"] == 50
        assert totals["total_tokens"] == 450
        assert totals["cost_usd"] == 0.003
        assert totals["call_count"] == 2


# ---------------------------------------------------------------------------
# Global storage / summary tests
# ---------------------------------------------------------------------------


class TestUsageSummary:
    def test_empty_summary(self):
        summary = get_usage_summary()
        assert summary["total_tokens"] == 0
        assert summary["call_count"] == 0
        assert summary["by_model"] == {}
        assert summary["by_tier"] == {}

    @pytest.mark.asyncio
    async def test_summary_aggregation(self):
        from unittest.mock import MagicMock

        tracker1 = create_usage_tracker(conversation_id="c1", tier="pro", provider="anthropic")
        tracker2 = create_usage_tracker(conversation_id="c2", tier="max", provider="openai")

        r1 = MagicMock()
        r1.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "model_name": "claude-sonnet-4-20250514",
        }
        r2 = MagicMock()
        r2.llm_output = {
            "token_usage": {"prompt_tokens": 200, "completion_tokens": 100},
            "model_name": "gpt-4o",
        }

        await tracker1.on_llm_end(r1)
        await tracker2.on_llm_end(r2)

        # Full summary
        summary = get_usage_summary()
        assert summary["call_count"] == 2
        assert summary["total_input_tokens"] == 300
        assert summary["total_output_tokens"] == 150
        assert len(summary["by_model"]) == 2
        assert len(summary["by_tier"]) == 2

    @pytest.mark.asyncio
    async def test_summary_filter_by_conversation(self):
        from unittest.mock import MagicMock

        t1 = create_usage_tracker(conversation_id="conv-a", tier="pro", provider="anthropic")
        t2 = create_usage_tracker(conversation_id="conv-b", tier="pro", provider="anthropic")

        r = MagicMock()
        r.llm_output = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "model_name": "claude-sonnet-4-20250514",
        }

        await t1.on_llm_end(r)
        await t2.on_llm_end(r)

        summary_a = get_usage_summary(conversation_id="conv-a")
        assert summary_a["call_count"] == 1
        assert summary_a["total_input_tokens"] == 100

        summary_b = get_usage_summary(conversation_id="conv-b")
        assert summary_b["call_count"] == 1

    def test_clear_records(self):
        from app.services.usage_tracker import _store_record

        _store_record(
            UsageRecord(
                conversation_id="x",
                user_id=None,
                model="m",
                tier="pro",
                provider="p",
                input_tokens=1,
                output_tokens=1,
                cached_tokens=0,
                cost_usd=0.0,
            )
        )
        assert len(get_all_records()) == 1
        clear_records()
        assert len(get_all_records()) == 0
