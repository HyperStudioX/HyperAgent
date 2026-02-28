"""OpenAI-compatible LLM wrapper with thinking/reasoning mode support.

Providers like DeepSeek, Kimi, and Qwen can return ``reasoning_content``
alongside the regular ``content``.  Standard ``ChatOpenAI`` from
langchain-openai silently drops this field from both outgoing replay
messages and incoming responses.

This module provides:

* **ThinkingAwareChatOpenAI** – a ``ChatOpenAI`` subclass that:
  1. **Always** captures ``reasoning_content`` from incoming API responses
     (both streaming and non-streaming) and stores it in
     ``AIMessage.additional_kwargs["reasoning_content"]``.  This is done
     unconditionally so that reasoning content is never lost, even when the
     provider enables thinking by default without explicit configuration.
  2. **Auto-detects** thinking mode: when ``reasoning_content`` is first
     seen in a response, ``thinking_mode`` is set to ``True`` so that
     outgoing payload patching is enabled for subsequent calls.
  3. When ``thinking_mode`` is ``True``, patches *outgoing* assistant
     messages to include ``reasoning_content`` (required by some providers
     for multi-turn tool-calling conversations).

* **extract_reasoning_content(message)** – helper to pull the reasoning
  text from any LangChain ``BaseMessage``.
"""

from __future__ import annotations

from typing import Any

import openai
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_reasoning_content(message: BaseMessage) -> str | None:
    """Extract reasoning/thinking content from a LangChain message.

    Checks ``additional_kwargs["reasoning_content"]`` which is populated by
    :class:`ThinkingAwareChatOpenAI`.

    Args:
        message: Any LangChain message (typically ``AIMessage``).

    Returns:
        The reasoning text if present, otherwise ``None``.
    """
    if not isinstance(message, (AIMessage, AIMessageChunk)):
        return None
    return message.additional_kwargs.get("reasoning_content") or None


class ThinkingAwareChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that supports providers with "thinking" mode.

    Incoming ``reasoning_content`` is **always** captured from API responses
    regardless of the ``thinking_mode`` flag.  This ensures that providers
    which enable thinking by default (e.g. Qwen with ``qwen3.5-plus``) have
    their reasoning content preserved for replay in multi-turn conversations.

    When ``thinking_content`` is detected for the first time,
    ``thinking_mode`` is automatically set to ``True`` so that outgoing
    payload patching kicks in for all subsequent API calls.

    * **Outgoing** (requires ``thinking_mode=True``) – injects
      ``reasoning_content`` on every assistant message that has
      ``tool_calls`` but is missing the field.

    * **Incoming (non-streaming)** – reads ``reasoning_content`` from the
      raw API response and stores it in ``AIMessage.additional_kwargs``.

    * **Incoming (streaming)** – reads ``reasoning_content`` from each
      streamed chunk delta and stores it in ``AIMessageChunk.additional_kwargs``.
    """

    thinking_mode: bool = False

    # ------------------------------------------------------------------
    # Outgoing: patch the request payload to include reasoning_content
    # ------------------------------------------------------------------

    def _get_request_payload(
        self, input_: Any, *, stop: list[str] | None = None, **kwargs: Any
    ) -> dict:
        if not self.thinking_mode:
            return super()._get_request_payload(input_, stop=stop, **kwargs)

        # Retrieve the original LangChain messages BEFORE they are converted
        # to dicts by super().  We need them to recover any reasoning_content
        # that was previously captured in additional_kwargs (which
        # _convert_message_to_dict silently drops).
        lc_messages = self._convert_input(input_).to_messages()
        reasoning_by_index: dict[int, str] = {}
        for idx, msg in enumerate(lc_messages):
            if isinstance(msg, AIMessage):
                rc = msg.additional_kwargs.get("reasoning_content")
                if rc:
                    reasoning_by_index[idx] = rc

        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        if "messages" not in payload:
            return payload

        patched = 0
        for idx, msg_dict in enumerate(payload["messages"]):
            if (
                msg_dict.get("role") == "assistant"
                and msg_dict.get("tool_calls")
                and "reasoning_content" not in msg_dict
            ):
                # Prefer the real reasoning_content captured from the
                # provider's earlier response; fall back to empty string
                # (which satisfies the "field must exist" requirement).
                msg_dict["reasoning_content"] = reasoning_by_index.get(idx, "")
                patched += 1

        if patched:
            restored = sum(1 for i in reasoning_by_index if i in {
                idx for idx, m in enumerate(payload["messages"])
                if m.get("role") == "assistant" and m.get("tool_calls")
            })
            logger.info(
                "thinking_mode_payload_patched",
                patched_count=patched,
                restored_count=restored,
                total_messages=len(payload["messages"]),
            )

        return payload

    # ------------------------------------------------------------------
    # Incoming (non-streaming): capture reasoning_content from response
    # ------------------------------------------------------------------

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)

        # Always attempt to capture reasoning_content, regardless of
        # thinking_mode.  Some providers (e.g. Qwen qwen3.5-plus) return
        # reasoning_content by default.  If we don't capture it here, it's
        # lost forever and cannot be replayed in subsequent multi-turn calls.
        captured = False

        if isinstance(response, openai.BaseModel):
            choices = getattr(response, "choices", None) or []
            for i, choice in enumerate(choices):
                msg = getattr(choice, "message", None)
                reasoning = getattr(msg, "reasoning_content", None)
                if reasoning and i < len(result.generations):
                    result.generations[i].message.additional_kwargs[
                        "reasoning_content"
                    ] = reasoning
                    captured = True
                    logger.debug(
                        "reasoning_content_captured",
                        length=len(reasoning),
                    )
        else:
            response_dict = response if isinstance(response, dict) else {}
            for i, choice in enumerate(response_dict.get("choices", [])):
                reasoning = (choice.get("message") or {}).get("reasoning_content")
                if reasoning and i < len(result.generations):
                    result.generations[i].message.additional_kwargs[
                        "reasoning_content"
                    ] = reasoning
                    captured = True
                    logger.debug(
                        "reasoning_content_captured",
                        length=len(reasoning),
                    )

        # Auto-enable thinking_mode when reasoning_content is first detected
        if captured and not self.thinking_mode:
            self.thinking_mode = True
            logger.info(
                "thinking_mode_auto_enabled",
                reason="reasoning_content detected in API response",
            )

        return result

    # ------------------------------------------------------------------
    # Incoming (streaming): capture reasoning_content from chunk deltas
    # ------------------------------------------------------------------

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )

        if generation_chunk is None:
            return generation_chunk

        # Always attempt to capture reasoning_content from streamed chunks.
        choices = (
            chunk.get("choices", [])
            or chunk.get("chunk", {}).get("choices", [])
        )
        if choices:
            delta = choices[0].get("delta") or {}
            reasoning = delta.get("reasoning_content")
            if reasoning:
                generation_chunk.message.additional_kwargs[
                    "reasoning_content"
                ] = reasoning
                logger.debug(
                    "reasoning_content_chunk_captured",
                    length=len(reasoning),
                )
                # Auto-enable thinking_mode on first detection
                if not self.thinking_mode:
                    self.thinking_mode = True
                    logger.info(
                        "thinking_mode_auto_enabled",
                        reason="reasoning_content detected in streaming chunk",
                    )

        return generation_chunk
