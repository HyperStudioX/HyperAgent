"""Type-safe event schema definitions for the multi-agent system.

This module provides structured event types and factory functions for
consistent event emission across all agents.
"""

import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def _timestamp() -> int:
    """Return current timestamp in milliseconds."""
    return int(time.time() * 1000)


class EventType(str, Enum):
    """Available event types for streaming to clients."""

    # Lifecycle events
    STAGE = "stage"
    COMPLETE = "complete"
    ERROR = "error"

    # Content events
    TOKEN = "token"
    VISUALIZATION = "visualization"

    # Tool events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    # Routing events
    ROUTING = "routing"
    HANDOFF = "handoff"
    CONFIG = "config"

    # Research-specific events
    SOURCE = "source"

    # Code-specific events
    CODE_RESULT = "code_result"


class StageStatus(str, Enum):
    """Stage lifecycle statuses."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Pydantic models for type-safe event creation


class StageEvent(BaseModel):
    """Event indicating a processing stage change."""

    type: Literal["stage"] = "stage"
    name: str = Field(..., description="Stage name (e.g., 'search', 'analyze')")
    description: str = Field(..., description="Human-readable description")
    status: StageStatus = Field(default=StageStatus.RUNNING)
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class TokenEvent(BaseModel):
    """Event for streaming token content."""

    type: Literal["token"] = "token"
    content: str = Field(..., description="Token content to stream")


class VisualizationEvent(BaseModel):
    """Event containing visualization data."""

    type: Literal["visualization"] = "visualization"
    data: str = Field(..., description="Base64-encoded visualization data")
    mime_type: str = Field(default="image/png", description="MIME type of the visualization")


class ToolCallEvent(BaseModel):
    """Event indicating a tool is being called."""

    type: Literal["tool_call"] = "tool_call"
    tool: str = Field(..., description="Tool name")
    args: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    id: str | None = Field(default=None, description="Unique tool call ID for matching results")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class ToolResultEvent(BaseModel):
    """Event containing tool execution result."""

    type: Literal["tool_result"] = "tool_result"
    tool: str = Field(..., description="Tool name")
    content: str = Field(..., description="Tool result content (may be truncated)")
    id: str | None = Field(default=None, description="Tool call ID to match with corresponding tool_call")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class RoutingEvent(BaseModel):
    """Event indicating agent routing decision."""

    type: Literal["routing"] = "routing"
    agent: str = Field(..., description="Selected agent name")
    reason: str = Field(..., description="Routing reason")
    confidence: float | None = Field(default=None, description="Confidence score (0.0 to 1.0)")
    low_confidence: bool = Field(default=False, description="True if confidence is below threshold")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class HandoffEvent(BaseModel):
    """Event indicating agent handoff."""

    type: Literal["handoff"] = "handoff"
    source: str = Field(..., description="Source agent")
    target: str = Field(..., description="Target agent")
    task: str = Field(..., description="Delegated task description")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class ErrorEvent(BaseModel):
    """Event indicating an error occurred."""

    type: Literal["error"] = "error"
    error: str = Field(..., description="Error message")
    node: str | None = Field(default=None, description="Node where error occurred")
    name: str | None = Field(default=None, description="Stage/component name")
    description: str | None = Field(default=None, description="Human-readable description")
    status: Literal["failed"] = "failed"
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class CompleteEvent(BaseModel):
    """Event indicating processing is complete."""

    type: Literal["complete"] = "complete"


class SourceEvent(BaseModel):
    """Event containing a research source."""

    type: Literal["source"] = "source"
    title: str = Field(..., description="Source title")
    url: str = Field(..., description="Source URL")
    snippet: str = Field(..., description="Source snippet/description")
    relevance_score: float | None = Field(default=None, description="Relevance score")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class CodeResultEvent(BaseModel):
    """Event containing code execution result."""

    type: Literal["code_result"] = "code_result"
    output: str = Field(..., description="Execution output")
    exit_code: int | None = Field(default=None, description="Exit code")
    error: str | None = Field(default=None, description="Error message if failed")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class ConfigEvent(BaseModel):
    """Event containing configuration info."""

    type: Literal["config"] = "config"
    depth: str | None = Field(default=None, description="Research depth")
    scenario: str | None = Field(default=None, description="Research scenario")


# Factory functions for backward compatibility and convenience


def stage(
    name: str,
    description: str,
    status: str = "running",
) -> dict[str, Any]:
    """Create a stage event dictionary.

    Args:
        name: Stage name
        description: Human-readable description
        status: Stage status

    Returns:
        Stage event dictionary
    """
    return StageEvent(
        name=name,
        description=description,
        status=StageStatus(status),
    ).model_dump()


def token(content: str) -> dict[str, Any]:
    """Create a token event dictionary.

    Args:
        content: Token content

    Returns:
        Token event dictionary
    """
    return TokenEvent(content=content).model_dump()


def visualization(data: str, mime_type: str = "image/png") -> dict[str, Any]:
    """Create a visualization event dictionary.

    Args:
        data: Base64-encoded visualization data
        mime_type: MIME type

    Returns:
        Visualization event dictionary
    """
    return VisualizationEvent(data=data, mime_type=mime_type).model_dump()


def tool_call(
    tool: str,
    args: dict[str, Any] | None = None,
    tool_id: str | None = None,
) -> dict[str, Any]:
    """Create a tool call event dictionary.

    Args:
        tool: Tool name
        args: Tool arguments
        tool_id: Unique ID for matching with tool_result

    Returns:
        Tool call event dictionary
    """
    return ToolCallEvent(tool=tool, args=args or {}, id=tool_id).model_dump()


def tool_result(
    tool: str,
    content: str,
    max_length: int = 500,
    tool_id: str | None = None,
) -> dict[str, Any]:
    """Create a tool result event dictionary.

    Args:
        tool: Tool name
        content: Tool result content
        max_length: Maximum content length
        tool_id: ID to match with corresponding tool_call

    Returns:
        Tool result event dictionary
    """
    truncated = content[:max_length] if len(content) > max_length else content
    return ToolResultEvent(tool=tool, content=truncated, id=tool_id).model_dump()


def routing(
    agent: str,
    reason: str,
    confidence: float | None = None,
    low_confidence: bool = False,
) -> dict[str, Any]:
    """Create a routing event dictionary.

    Args:
        agent: Selected agent name
        reason: Routing reason
        confidence: Confidence score (0.0 to 1.0)
        low_confidence: Whether confidence is below threshold

    Returns:
        Routing event dictionary
    """
    return RoutingEvent(
        agent=agent,
        reason=reason,
        confidence=confidence,
        low_confidence=low_confidence,
    ).model_dump()


def handoff(source: str, target: str, task: str) -> dict[str, Any]:
    """Create a handoff event dictionary.

    Args:
        source: Source agent
        target: Target agent
        task: Delegated task

    Returns:
        Handoff event dictionary
    """
    return HandoffEvent(source=source, target=target, task=task).model_dump()


def error(
    error_msg: str,
    node: str | None = None,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Create an error event dictionary.

    Args:
        error_msg: Error message
        node: Node where error occurred
        name: Stage/component name
        description: Human-readable description

    Returns:
        Error event dictionary
    """
    return ErrorEvent(
        error=error_msg,
        node=node,
        name=name,
        description=description,
    ).model_dump()


def complete() -> dict[str, Any]:
    """Create a complete event dictionary.

    Returns:
        Complete event dictionary
    """
    return CompleteEvent().model_dump()


def source(
    title: str,
    url: str,
    snippet: str,
    relevance_score: float | None = None,
) -> dict[str, Any]:
    """Create a source event dictionary.

    Args:
        title: Source title
        url: Source URL
        snippet: Source snippet
        relevance_score: Relevance score

    Returns:
        Source event dictionary
    """
    return SourceEvent(
        title=title,
        url=url,
        snippet=snippet,
        relevance_score=relevance_score,
    ).model_dump()


def code_result(
    output: str,
    exit_code: int | None = None,
    error_msg: str | None = None,
) -> dict[str, Any]:
    """Create a code result event dictionary.

    Args:
        output: Execution output
        exit_code: Exit code
        error_msg: Error message

    Returns:
        Code result event dictionary
    """
    return CodeResultEvent(
        output=output,
        exit_code=exit_code,
        error=error_msg,
    ).model_dump()


def config(
    depth: str | None = None,
    scenario: str | None = None,
) -> dict[str, Any]:
    """Create a config event dictionary.

    Args:
        depth: Research depth
        scenario: Research scenario

    Returns:
        Config event dictionary
    """
    return ConfigEvent(depth=depth, scenario=scenario).model_dump()
