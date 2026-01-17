"""Conversation Memory Management.

This module provides memory management utilities for handling long conversations
with windowing and summarization strategies. It helps prevent context overflow
while maintaining conversation coherence.
"""

from typing import Any

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


class SharedAgentContext:
    """Shared context for multi-agent collaboration.

    Provides a centralized store for information that needs to be
    shared across agents during a multi-agent workflow.
    """

    def __init__(self):
        """Initialize shared context."""
        self._research_findings: str | None = None
        self._research_sources: list[dict[str, Any]] = []
        self._generated_code: str | None = None
        self._code_language: str | None = None
        self._execution_results: str | None = None
        self._writing_outline: str | None = None
        self._writing_draft: str | None = None
        self._data_analysis: str | None = None
        self._visualizations: list[dict[str, str]] = []
        self._additional_context: str | None = None
        self._handoff_history: list[dict[str, str]] = []

    def set_research_findings(
        self,
        findings: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> None:
        """Set research findings and sources.

        Args:
            findings: Research findings text
            sources: Optional list of source dicts
        """
        self._research_findings = findings
        if sources:
            self._research_sources = sources
        logger.debug("research_findings_set", length=len(findings))

    def set_code(
        self,
        code: str,
        language: str = "python",
        execution_results: str | None = None,
    ) -> None:
        """Set generated code and optional execution results.

        Args:
            code: Generated code
            language: Programming language
            execution_results: Optional execution output
        """
        self._generated_code = code
        self._code_language = language
        if execution_results:
            self._execution_results = execution_results
        logger.debug("code_set", language=language, length=len(code))

    def set_writing(
        self,
        outline: str | None = None,
        draft: str | None = None,
    ) -> None:
        """Set writing context.

        Args:
            outline: Writing outline
            draft: Writing draft
        """
        if outline:
            self._writing_outline = outline
        if draft:
            self._writing_draft = draft
        logger.debug("writing_context_set")

    def set_data_analysis(
        self,
        analysis: str,
        visualizations: list[dict[str, str]] | None = None,
    ) -> None:
        """Set data analysis results.

        Args:
            analysis: Analysis text
            visualizations: Optional list of visualization dicts
        """
        self._data_analysis = analysis
        if visualizations:
            self._visualizations = visualizations
        logger.debug("data_analysis_set", viz_count=len(visualizations or []))

    def add_visualization(self, data: str, mime_type: str = "image/png") -> None:
        """Add a visualization.

        Args:
            data: Base64-encoded visualization data
            mime_type: MIME type
        """
        self._visualizations.append({
            "data": data,
            "type": mime_type,
        })

    def record_handoff(
        self,
        source: str,
        target: str,
        task: str,
    ) -> None:
        """Record a handoff for tracking.

        Args:
            source: Source agent
            target: Target agent
            task: Task description
        """
        self._handoff_history.append({
            "from": source,
            "to": target,
            "task": task,
        })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for state storage.

        Returns:
            Dict representation of shared context
        """
        return {
            "research_findings": self._research_findings,
            "research_sources": self._research_sources,
            "generated_code": self._generated_code,
            "code_language": self._code_language,
            "execution_results": self._execution_results,
            "writing_outline": self._writing_outline,
            "writing_draft": self._writing_draft,
            "data_analysis": self._data_analysis,
            "visualizations": self._visualizations,
            "additional_context": self._additional_context,
            "handoff_history": self._handoff_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SharedAgentContext":
        """Create from dictionary.

        Args:
            data: Dict representation

        Returns:
            SharedAgentContext instance
        """
        ctx = cls()
        ctx._research_findings = data.get("research_findings")
        ctx._research_sources = data.get("research_sources", [])
        ctx._generated_code = data.get("generated_code")
        ctx._code_language = data.get("code_language")
        ctx._execution_results = data.get("execution_results")
        ctx._writing_outline = data.get("writing_outline")
        ctx._writing_draft = data.get("writing_draft")
        ctx._data_analysis = data.get("data_analysis")
        ctx._visualizations = data.get("visualizations", [])
        ctx._additional_context = data.get("additional_context")
        ctx._handoff_history = data.get("handoff_history", [])
        return ctx

    def format_for_prompt(self, max_length: int = 4000) -> str:
        """Format shared context for injection into agent prompts.

        Args:
            max_length: Maximum total length

        Returns:
            Formatted context string
        """
        parts: list[str] = []
        remaining = max_length

        # Add research findings
        if self._research_findings and remaining > 0:
            section = f"## Research Findings\n{self._research_findings[:2000]}"
            parts.append(section)
            remaining -= len(section)

        # Add sources
        if self._research_sources and remaining > 200:
            source_lines = []
            for src in self._research_sources[:10]:
                title = src.get("title", "Source")
                url = src.get("url", "")
                source_lines.append(f"- [{title}]({url})")
            section = "## Sources\n" + "\n".join(source_lines)
            parts.append(section)
            remaining -= len(section)

        # Add code
        if self._generated_code and remaining > 200:
            lang = self._code_language or "python"
            code_preview = self._generated_code[:1500]
            section = f"## Generated Code\n```{lang}\n{code_preview}\n```"
            parts.append(section)
            remaining -= len(section)

        # Add execution results
        if self._execution_results and remaining > 200:
            results_preview = self._execution_results[:1000]
            section = f"## Execution Results\n```\n{results_preview}\n```"
            parts.append(section)
            remaining -= len(section)

        # Add writing context
        if self._writing_outline and remaining > 200:
            outline_preview = self._writing_outline[:1000]
            section = f"## Writing Outline\n{outline_preview}"
            parts.append(section)
            remaining -= len(section)

        # Add data analysis
        if self._data_analysis and remaining > 200:
            analysis_preview = self._data_analysis[:1000]
            section = f"## Data Analysis\n{analysis_preview}"
            parts.append(section)

        if not parts:
            return ""

        return "---\n# Context from Previous Agents\n\n" + "\n\n".join(parts)


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


def convert_history_to_messages(history: list[dict]) -> list[BaseMessage]:
    """Convert dict-based history to LangChain messages.

    Args:
        history: List of message dicts with 'role' and 'content'

    Returns:
        List of LangChain BaseMessage objects
    """
    messages: list[BaseMessage] = []

    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "system":
            messages.append(SystemMessage(content=content))
        elif role == "tool":
            # Tool messages need additional fields
            messages.append(ToolMessage(
                content=content,
                tool_call_id=msg.get("tool_call_id", ""),
                name=msg.get("name", ""),
            ))

    return messages


def messages_to_history(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain messages to dict-based history.

    Args:
        messages: List of LangChain messages

    Returns:
        List of message dicts
    """
    history: list[dict] = []

    for msg in messages:
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, SystemMessage):
            role = "system"
        elif isinstance(msg, ToolMessage):
            history.append({
                "role": "tool",
                "content": msg.content if isinstance(msg.content, str) else str(msg.content),
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
            })
            continue
        else:
            continue

        history.append({
            "role": role,
            "content": msg.content if isinstance(msg.content, str) else str(msg.content),
        })

    return history
