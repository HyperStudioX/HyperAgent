"""Conversation Memory Management.

This module provides memory management utilities for handling long conversations
with windowing and summarization strategies. It helps prevent context overflow
while maintaining conversation coherence.
"""


from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConversationMemory:
    """Manages conversation memory with windowing and summarization.

    Provides strategies for handling long conversations:
    - Window-based: Keep only the most recent N messages
    - Token-based: Keep messages within a token budget
    - Summary-based: Summarize older messages
    """

    def __init__(
        self,
        max_messages: int = 50,
        max_tokens: int | None = None,
        preserve_system: bool = True,
        preserve_recent: int = 10,
    ):
        """Initialize conversation memory.

        Args:
            max_messages: Maximum number of messages to retain
            max_tokens: Optional maximum token count (estimate)
            preserve_system: Always preserve system messages
            preserve_recent: Minimum recent messages to always keep
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.preserve_system = preserve_system
        self.preserve_recent = preserve_recent
        self._messages: list[BaseMessage] = []
        self._summary: str | None = None

    @property
    def messages(self) -> list[BaseMessage]:
        """Get current messages."""
        return self._messages.copy()

    @property
    def summary(self) -> str | None:
        """Get conversation summary if available."""
        return self._summary

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to memory.

        Args:
            message: Message to add
        """
        self._messages.append(message)
        self._trim_if_needed()

    def add_messages(self, messages: list[BaseMessage]) -> None:
        """Add multiple messages to memory.

        Args:
            messages: Messages to add
        """
        self._messages.extend(messages)
        self._trim_if_needed()

    def get_messages(
        self,
        include_summary: bool = True,
        as_dicts: bool = False,
    ) -> list[BaseMessage] | list[dict]:
        """Get messages for use in prompts.

        Args:
            include_summary: Whether to include summary as first message
            as_dicts: Return as dict format instead of BaseMessage

        Returns:
            List of messages
        """
        result: list[BaseMessage] = []

        # Add summary as system message if available
        if include_summary and self._summary:
            summary_msg = SystemMessage(
                content=f"[Previous conversation summary]\n{self._summary}"
            )
            result.append(summary_msg)

        result.extend(self._messages)

        if as_dicts:
            return [self._message_to_dict(m) for m in result]

        return result

    def clear(self) -> None:
        """Clear all messages and summary."""
        self._messages = []
        self._summary = None

    def set_summary(self, summary: str) -> None:
        """Set conversation summary.

        Args:
            summary: Summary text
        """
        self._summary = summary
        logger.info("conversation_summary_set", length=len(summary))

    def _trim_if_needed(self) -> None:
        """Trim messages if over limits."""
        if len(self._messages) <= self.max_messages:
            return

        # Separate system messages if preserving them
        system_messages: list[BaseMessage] = []
        other_messages: list[BaseMessage] = []

        for msg in self._messages:
            if self.preserve_system and isinstance(msg, SystemMessage):
                system_messages.append(msg)
            else:
                other_messages.append(msg)

        # Calculate how many non-system messages to keep
        available_slots = self.max_messages - len(system_messages)
        keep_count = max(self.preserve_recent, available_slots)

        # Keep the most recent messages
        trimmed_other = other_messages[-keep_count:]

        # Reconstruct message list
        self._messages = system_messages + trimmed_other

        trimmed_count = len(other_messages) - len(trimmed_other)
        if trimmed_count > 0:
            logger.info(
                "messages_trimmed",
                trimmed=trimmed_count,
                remaining=len(self._messages),
            )

    def _message_to_dict(self, message: BaseMessage) -> dict:
        """Convert a message to dict format.

        Args:
            message: Message to convert

        Returns:
            Dict with role and content
        """
        if isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, ToolMessage):
            role = "tool"
        else:
            role = "unknown"

        return {
            "role": role,
            "content": message.content if isinstance(message.content, str) else str(message.content),
        }

    def estimate_tokens(self) -> int:
        """Estimate total tokens in current messages.

        Uses a simple heuristic of ~4 characters per token.

        Returns:
            Estimated token count
        """
        total_chars = sum(
            len(m.content) if isinstance(m.content, str) else len(str(m.content))
            for m in self._messages
        )
        return total_chars // 4


def window_messages(
    messages: list[BaseMessage],
    max_messages: int = 20,
    preserve_first: int = 2,
    preserve_last: int = 10,
) -> list[BaseMessage]:
    """Apply sliding window to message list.

    Keeps first N and last M messages, discarding middle messages.
    Useful for maintaining context while staying within token limits.

    Args:
        messages: Full message list
        max_messages: Maximum messages to return
        preserve_first: Number of first messages to always keep
        preserve_last: Number of last messages to always keep

    Returns:
        Windowed message list
    """
    if len(messages) <= max_messages:
        return messages.copy()

    # Ensure we can fit both preserved sections
    if preserve_first + preserve_last > max_messages:
        # Just keep most recent
        return messages[-max_messages:]

    first_part = messages[:preserve_first]
    last_part = messages[-preserve_last:]

    # Add marker for removed messages
    removed_count = len(messages) - preserve_first - preserve_last
    marker = SystemMessage(
        content=f"[{removed_count} earlier messages removed for context management]"
    )

    return first_part + [marker] + last_part


