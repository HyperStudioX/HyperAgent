"""Shared context policy utilities for compression and truncation."""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import BaseMessage

from app.agents.context_compression import (
    CompressionConfig,
    ContextCompressor,
    estimate_message_tokens,
    estimate_tokens,
    has_context_summary_message,
    inject_summary_as_context,
    is_context_summary_message,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


def enforce_summary_singleton(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Remove duplicate injected summary messages, keeping only the latest one."""
    summary_indices = [
        i for i, msg in enumerate(messages) if is_context_summary_message(msg)
    ]
    if len(summary_indices) <= 1:
        return messages

    keep_index = summary_indices[-1]
    cleaned: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        if i in summary_indices and i != keep_index:
            continue
        cleaned.append(msg)
    return cleaned


async def apply_context_policy(
    messages: list[BaseMessage],
    *,
    existing_summary: str | None,
    provider: str | None,
    locale: str,
    compression_enabled: bool,
    compression_token_threshold: int,
    compression_preserve_recent: int,
    truncate_max_tokens: int,
    truncate_preserve_recent: int,
    truncator: Callable[..., tuple[list[BaseMessage], bool]],
    enforce_summary_singleton_flag: bool = True,
) -> tuple[list[BaseMessage], str | None, list[dict[str, Any]], bool]:
    """Apply shared compression + truncation policy to a message list."""
    events: list[dict[str, Any]] = []
    new_summary: str | None = None

    working_messages = list(messages)
    if enforce_summary_singleton_flag:
        working_messages = enforce_summary_singleton(working_messages)

    # Compression pass (semantic preservation) before truncation.
    if compression_enabled and len(working_messages) > compression_preserve_recent:
        estimated_tokens = sum(estimate_message_tokens(m) for m in working_messages)
        # Only add state summary estimate when no summary message is currently injected.
        if existing_summary and not has_context_summary_message(working_messages):
            estimated_tokens += estimate_tokens(existing_summary)

        if estimated_tokens > compression_token_threshold:
            compression_config = CompressionConfig(
                token_threshold=compression_token_threshold,
                preserve_recent=compression_preserve_recent,
                enabled=True,
            )
            compressor = ContextCompressor(compression_config)
            try:
                compressed_summary, compressed_messages = await compressor.compress(
                    working_messages,
                    existing_summary,
                    provider or "anthropic",
                    locale=locale,
                )
                if compressed_summary:
                    working_messages = inject_summary_as_context(
                        compressed_messages,
                        compressed_summary,
                        enforce_singleton=enforce_summary_singleton_flag,
                    )
                    new_summary = compressed_summary
                    events.append({
                        "type": "stage",
                        "name": "context",
                        "description": "Context compressed to preserve conversation history",
                        "status": "completed",
                    })
            except Exception as e:
                logger.warning("context_policy_compression_skipped", error=str(e))

    # Truncation fallback (hard budget).
    working_messages, was_truncated = truncator(
        working_messages,
        max_tokens=truncate_max_tokens,
        preserve_recent=truncate_preserve_recent,
    )
    if was_truncated:
        events.append({
            "type": "stage",
            "name": "context",
            "description": "Message history truncated to fit context window",
            "status": "completed",
        })

    return working_messages, new_summary, events, was_truncated

