"""Usage tracking service for LLM token counts and costs.

Tracks token usage and estimated costs across all LLM calls using
LangChain's callback mechanism. Data is stored in-memory per process.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Pricing per million tokens (USD)
# ---------------------------------------------------------------------------

# {model_substring: (input_price_per_M, output_price_per_M, cached_input_price_per_M)}
MODEL_PRICING: dict[str, tuple[float, float, float]] = {
    # Anthropic
    "claude-opus": (15.0, 75.0, 1.5),
    "claude-sonnet": (3.0, 15.0, 0.3),
    "claude-haiku": (0.25, 1.25, 0.025),
    "haiku": (0.25, 1.25, 0.025),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60, 0.075),
    "gpt-4o": (2.50, 10.0, 1.25),
    "gpt-4-turbo": (10.0, 30.0, 5.0),
    "o1": (15.0, 60.0, 7.5),
    "o3": (10.0, 40.0, 5.0),
    # Google
    "gemini-2.5-pro": (1.25, 10.0, 0.3125),
    "gemini-2.5-flash": (0.15, 0.60, 0.0375),
    "gemini-2.0-flash": (0.10, 0.40, 0.025),
    "gemini-3": (1.25, 10.0, 0.3125),
}

# Fallback pricing when model is not recognized
_DEFAULT_PRICING = (3.0, 15.0, 0.3)


def _lookup_pricing(model: str) -> tuple[float, float, float]:
    """Find pricing for a model by substring match.

    Tries the most specific match first (longest substring).
    """
    model_lower = model.lower()
    best_key = ""
    for key in MODEL_PRICING:
        if key in model_lower and len(key) > len(best_key):
            best_key = key
    if best_key:
        return MODEL_PRICING[best_key]
    return _DEFAULT_PRICING


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate estimated cost in USD for a single LLM call."""
    input_price, output_price, cached_price = _lookup_pricing(model)
    # Non-cached input tokens = input_tokens - cached_tokens
    regular_input = max(input_tokens - cached_tokens, 0)
    cost = (
        (regular_input / 1_000_000) * input_price
        + (cached_tokens / 1_000_000) * cached_price
        + (output_tokens / 1_000_000) * output_price
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# UsageRecord
# ---------------------------------------------------------------------------


@dataclass
class UsageRecord:
    """A single LLM usage record."""

    conversation_id: str
    user_id: str | None
    model: str
    tier: str
    provider: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# In-memory storage (thread-safe)
# ---------------------------------------------------------------------------

_usage_records: list[UsageRecord] = []
_lock = threading.Lock()


def _store_record(record: UsageRecord) -> None:
    with _lock:
        _usage_records.append(record)


def get_all_records() -> list[UsageRecord]:
    """Return a shallow copy of all records."""
    with _lock:
        return list(_usage_records)


def clear_records() -> None:
    """Clear all stored records (useful for testing)."""
    with _lock:
        _usage_records.clear()


# ---------------------------------------------------------------------------
# UsageTracker — LangChain async callback handler
# ---------------------------------------------------------------------------


class UsageTracker(AsyncCallbackHandler):
    """Captures token usage from LLM responses and stores UsageRecords."""

    def __init__(
        self,
        conversation_id: str = "",
        user_id: str | None = None,
        tier: str = "pro",
        provider: str = "anthropic",
    ):
        super().__init__()
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.tier = tier
        self.provider = provider
        self.records: list[UsageRecord] = []

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Extract token usage from the LLM response and record it."""
        try:
            llm_output = response.llm_output or {}
            token_usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
            model_name = llm_output.get("model_name") or llm_output.get("model", "unknown")

            # Different providers expose tokens under different keys
            input_tokens = (
                token_usage.get("prompt_tokens")
                or token_usage.get("input_tokens")
                or 0
            )
            output_tokens = (
                token_usage.get("completion_tokens")
                or token_usage.get("output_tokens")
                or 0
            )
            cached_tokens = (
                token_usage.get("cache_read_input_tokens")
                or token_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
                if isinstance(token_usage.get("prompt_tokens_details"), dict)
                else token_usage.get("cache_read_input_tokens", 0)
            )
            if not isinstance(cached_tokens, int):
                cached_tokens = 0

            # Skip recording if we got no token data at all
            if input_tokens == 0 and output_tokens == 0:
                return

            cost = calculate_cost(model_name, input_tokens, output_tokens, cached_tokens)

            record = UsageRecord(
                conversation_id=self.conversation_id,
                user_id=self.user_id,
                model=model_name,
                tier=self.tier,
                provider=self.provider,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost,
            )
            self.records.append(record)
            _store_record(record)

            logger.debug(
                "usage_recorded",
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                cost_usd=cost,
                conversation_id=self.conversation_id,
            )
        except Exception:
            # Never let tracking errors interrupt the LLM pipeline
            logger.opt(exception=True).warning("usage_tracking_failed")

    def get_total_tokens(self) -> dict[str, Any]:
        """Return aggregated totals for this tracker instance."""
        total_input = sum(r.input_tokens for r in self.records)
        total_output = sum(r.output_tokens for r in self.records)
        total_cached = sum(r.cached_tokens for r in self.records)
        total_cost = round(sum(r.cost_usd for r in self.records), 6)
        return {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cached_tokens": total_cached,
            "total_tokens": total_input + total_output,
            "cost_usd": total_cost,
            "call_count": len(self.records),
        }


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def create_usage_tracker(
    conversation_id: str = "",
    user_id: str | None = None,
    tier: str = "pro",
    provider: str = "anthropic",
) -> UsageTracker:
    """Create a new UsageTracker callback handler."""
    return UsageTracker(
        conversation_id=conversation_id,
        user_id=user_id,
        tier=tier,
        provider=provider,
    )


def get_usage_summary(
    conversation_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate usage across all stored records, optionally filtered."""
    records = get_all_records()

    if conversation_id:
        records = [r for r in records if r.conversation_id == conversation_id]
    if user_id:
        records = [r for r in records if r.user_id == user_id]

    if not records:
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cached_tokens": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "call_count": 0,
            "by_model": {},
            "by_tier": {},
        }

    total_input = sum(r.input_tokens for r in records)
    total_output = sum(r.output_tokens for r in records)
    total_cached = sum(r.cached_tokens for r in records)
    total_cost = round(sum(r.cost_usd for r in records), 6)

    # Aggregate by model
    by_model: dict[str, dict[str, Any]] = {}
    for r in records:
        bucket = by_model.setdefault(r.model, {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cost_usd": 0.0,
            "call_count": 0,
        })
        bucket["input_tokens"] += r.input_tokens
        bucket["output_tokens"] += r.output_tokens
        bucket["cached_tokens"] += r.cached_tokens
        bucket["cost_usd"] = round(bucket["cost_usd"] + r.cost_usd, 6)
        bucket["call_count"] += 1

    # Aggregate by tier
    by_tier: dict[str, dict[str, Any]] = {}
    for r in records:
        bucket = by_tier.setdefault(r.tier, {
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "cost_usd": 0.0,
            "call_count": 0,
        })
        bucket["input_tokens"] += r.input_tokens
        bucket["output_tokens"] += r.output_tokens
        bucket["cached_tokens"] += r.cached_tokens
        bucket["cost_usd"] = round(bucket["cost_usd"] + r.cost_usd, 6)
        bucket["call_count"] += 1

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cached_tokens": total_cached,
        "total_tokens": total_input + total_output,
        "total_cost_usd": total_cost,
        "call_count": len(records),
        "by_model": by_model,
        "by_tier": by_tier,
    }
