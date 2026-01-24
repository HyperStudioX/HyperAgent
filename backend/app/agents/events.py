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
    IMAGE = "image"

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

    # Browser/sandbox events
    BROWSER_STREAM = "browser_stream"
    BROWSER_ACTION = "browser_action"

    # Skill events
    SKILL_OUTPUT = "skill_output"

    # Human-in-the-loop events
    INTERRUPT = "interrupt"
    INTERRUPT_RESPONSE = "interrupt_response"


class InterruptType(str, Enum):
    """Types of human-in-the-loop interrupts."""

    DECISION = "decision"  # Multiple choice decision point
    INPUT = "input"  # Free-form text input
    APPROVAL = "approval"  # Yes/no approval for high-risk action


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


class ImageEvent(BaseModel):
    """Event containing generated image data."""

    type: Literal["image"] = "image"
    data: str = Field(..., description="Base64-encoded image data")
    mime_type: str = Field(default="image/png", description="MIME type of the image")
    index: int | None = Field(default=None, description="Index for inline rendering with placeholders")


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


class BrowserStreamEvent(BaseModel):
    """Event containing browser stream URL for live viewing."""

    type: Literal["browser_stream"] = "browser_stream"
    stream_url: str = Field(..., description="URL to view the browser stream")
    sandbox_id: str = Field(..., description="Sandbox identifier")
    auth_key: str | None = Field(default=None, description="Authentication key if required")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class BrowserActionEvent(BaseModel):
    """Event indicating a browser action is being performed."""

    type: Literal["browser_action"] = "browser_action"
    action: str = Field(..., description="Action being performed (navigate, click, type, scroll, etc.)")
    description: str = Field(..., description="Human-readable description of the action")
    target: str | None = Field(default=None, description="Target of the action (URL, coordinates, text)")
    status: str = Field(default="running", description="Action status (running, completed)")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class SkillOutputEvent(BaseModel):
    """Event containing skill execution output."""

    type: Literal["skill_output"] = "skill_output"
    skill_id: str = Field(..., description="Skill identifier")
    output: dict[str, Any] = Field(..., description="Skill execution output")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class InterruptOption(BaseModel):
    """An option for a decision-type interrupt."""

    label: str = Field(..., description="Display text for the option")
    value: str = Field(..., description="Value to return when selected")
    description: str | None = Field(default=None, description="Additional description")


class InterruptEvent(BaseModel):
    """Event requesting human-in-the-loop input.

    Used to pause agent execution and collect user input for:
    - Decision: Multiple choice decision points
    - Input: Free-form text input collection
    - Approval: Yes/no approval for high-risk tool execution
    """

    type: Literal["interrupt"] = "interrupt"
    interrupt_id: str = Field(..., description="Unique ID for matching response")
    interrupt_type: InterruptType = Field(..., description="Type of interrupt")
    title: str = Field(..., description="Title displayed in dialog")
    message: str = Field(..., description="Detailed message/question")
    options: list[InterruptOption] | None = Field(
        default=None, description="Options for DECISION type"
    )
    tool_info: dict[str, Any] | None = Field(
        default=None, description="Tool details for APPROVAL type"
    )
    default_action: str | None = Field(
        default=None, description="Action to take on timeout (e.g., 'deny', 'approve', 'skip')"
    )
    timeout_seconds: int = Field(default=120, description="Timeout in seconds")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


class InterruptResponseEvent(BaseModel):
    """Event containing user response to an interrupt."""

    type: Literal["interrupt_response"] = "interrupt_response"
    interrupt_id: str = Field(..., description="ID of the interrupt being responded to")
    action: str = Field(..., description="User action: approve, deny, skip, select, input")
    value: str | None = Field(default=None, description="Selected value or input text")
    timestamp: int = Field(default_factory=_timestamp, description="Event timestamp in ms")


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


def image(
    data: str,
    mime_type: str = "image/png",
    index: int | None = None,
) -> dict[str, Any]:
    """Create an image event dictionary.

    Args:
        data: Base64-encoded image data
        mime_type: MIME type of the image
        index: Index for inline rendering (matches ![generated-image:INDEX] placeholders)

    Returns:
        Image event dictionary
    """
    return ImageEvent(data=data, mime_type=mime_type, index=index).model_dump()


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


def browser_stream(
    stream_url: str,
    sandbox_id: str,
    auth_key: str | None = None,
) -> dict[str, Any]:
    """Create a browser stream event dictionary.

    This event provides a URL that can be embedded in an iframe
    to show live browser activity in the E2B sandbox.

    Args:
        stream_url: URL to view the browser stream
        sandbox_id: Sandbox identifier
        auth_key: Authentication key if required

    Returns:
        Browser stream event dictionary
    """
    return BrowserStreamEvent(
        stream_url=stream_url,
        sandbox_id=sandbox_id,
        auth_key=auth_key,
    ).model_dump()


def browser_action(
    action: str,
    description: str,
    target: str | None = None,
    status: str = "running",
) -> dict[str, Any]:
    """Create a browser action event dictionary.

    This event indicates a browser action is being performed,
    helping sync the UI progress with what's visible in the browser stream.

    Args:
        action: Action type (navigate, click, type, scroll, screenshot, etc.)
        description: Human-readable description
        target: Target of the action (URL, coordinates, text)
        status: Action status (running, completed)

    Returns:
        Browser action event dictionary
    """
    return BrowserActionEvent(
        action=action,
        description=description,
        target=target,
        status=status,
    ).model_dump()


def skill_output(
    skill_id: str,
    output: dict[str, Any],
) -> dict[str, Any]:
    """Create a skill output event dictionary.

    Args:
        skill_id: Skill identifier
        output: Skill execution output

    Returns:
        Skill output event dictionary
    """
    return SkillOutputEvent(
        skill_id=skill_id,
        output=output,
    ).model_dump()


def interrupt(
    interrupt_id: str,
    interrupt_type: InterruptType | str,
    title: str,
    message: str,
    options: list[dict[str, str]] | None = None,
    tool_info: dict[str, Any] | None = None,
    default_action: str | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Create an interrupt event dictionary.

    Args:
        interrupt_id: Unique ID for matching response
        interrupt_type: Type of interrupt (decision, input, approval)
        title: Title displayed in dialog
        message: Detailed message/question
        options: Options for DECISION type [{"label": "...", "value": "...", "description": "..."}]
        tool_info: Tool details for APPROVAL type
        default_action: Action to take on timeout
        timeout_seconds: Timeout in seconds

    Returns:
        Interrupt event dictionary
    """
    interrupt_type_enum = (
        InterruptType(interrupt_type)
        if isinstance(interrupt_type, str)
        else interrupt_type
    )
    parsed_options = None
    if options:
        parsed_options = [
            InterruptOption(
                label=opt.get("label", ""),
                value=opt.get("value", ""),
                description=opt.get("description"),
            )
            for opt in options
        ]

    return InterruptEvent(
        interrupt_id=interrupt_id,
        interrupt_type=interrupt_type_enum,
        title=title,
        message=message,
        options=parsed_options,
        tool_info=tool_info,
        default_action=default_action,
        timeout_seconds=timeout_seconds,
    ).model_dump()


def interrupt_response(
    interrupt_id: str,
    action: str,
    value: str | None = None,
) -> dict[str, Any]:
    """Create an interrupt response event dictionary.

    Args:
        interrupt_id: ID of the interrupt being responded to
        action: User action (approve, deny, skip, select, input)
        value: Selected value or input text

    Returns:
        Interrupt response event dictionary
    """
    return InterruptResponseEvent(
        interrupt_id=interrupt_id,
        action=action,
        value=value,
    ).model_dump()
