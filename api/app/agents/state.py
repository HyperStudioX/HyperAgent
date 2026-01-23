"""Shared state definitions for the multi-agent system."""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage

from app.models.schemas import LLMProvider, ModelTier, ResearchDepth, ResearchScenario
from app.services.search import SearchResult


class AgentType(str, Enum):
    """Available agent types.

    Simplified architecture:
    - CHAT: Main agent with skills for general tasks, image generation, writing, and coding
    - RESEARCH: Deep research workflows with comprehensive analysis
    - DATA: Data analytics and visualization

    Note: Deprecated agent types (IMAGE, WRITING, CODE) have been removed.
    They are mapped to CHAT at the routing layer via AGENT_NAME_MAP.
    """

    CHAT = "chat"
    RESEARCH = "research"
    DATA = "data"


# Re-export HandoffInfo and SharedAgentMemory from handoff module for backward compatibility
# These types are now consolidated in the handoff module
from app.agents.tools.handoff import HandoffInfo, SharedAgentMemory


class SupervisorState(TypedDict, total=False):
    """Base state for the supervisor graph.

    All subagent states extend this base state to ensure compatibility
    with the supervisor routing system.
    """

    # Input
    query: str
    mode: str | None  # Explicit mode override (AgentType value)
    messages: list[dict[str, Any]]  # Chat history for context

    # Routing
    selected_agent: str  # The agent type selected by router
    routing_reason: str  # Explanation for routing decision
    routing_confidence: float  # Confidence score from router (0.0 to 1.0)

    # Handoff support (multi-agent collaboration)
    active_agent: str | None  # Currently active agent (for handoff tracking)
    delegated_task: str | None  # Task description if this was a handoff
    handoff_context: str | None  # Additional context from handoff
    handoff_count: int  # Number of handoffs in current request
    handoff_history: list[HandoffInfo]  # History of handoffs
    pending_handoff: HandoffInfo | None  # Pending handoff to process
    shared_memory: SharedAgentMemory  # Shared state across agents

    # Tool execution tracking (shared across all agents)
    tool_iterations: int  # Count of tool-call loops for current agent

    # Output
    response: str  # Final text response
    events: Annotated[list[dict[str, Any]], operator.add]  # Streaming events

    # Metadata
    task_id: str | None
    user_id: str | None
    attachment_ids: list[str]  # IDs of attached files for tool access
    image_attachments: list[dict]  # Base64-encoded image data for vision tools [{id, filename, base64_data, mime_type}]
    provider: LLMProvider
    model: str | None
    tier: ModelTier | None  # User-specified tier override
    locale: str  # User's preferred language (e.g., 'en', 'zh-CN')


class ChatState(SupervisorState, total=False):
    """State for the chat subagent."""

    # Chat-specific fields
    system_prompt: str
    lc_messages: list[BaseMessage]  # LangChain messages for tool calling
    has_error: bool  # Flag to signal error and stop the loop
    # Note: tool_iterations is inherited from SupervisorState


class ResearchState(SupervisorState, total=False):
    """State for the research subagent."""

    # Research configuration
    depth: ResearchDepth
    scenario: ResearchScenario
    system_prompt: str
    report_structure: list[str]
    depth_config: dict[str, Any]

    # Tool calling support
    lc_messages: list[BaseMessage]  # LangChain messages for ReAct loop
    search_complete: bool  # Flag to exit search loop
    # Note: tool_iterations (inherited from SupervisorState) tracks search iterations

    # Handoff tracking
    deferred_handoff: HandoffInfo | None  # Handoff deferred until search tools complete

    # Research outputs
    sources: list[SearchResult]
    analysis: str
    synthesis: str
    report_chunks: list[str]


class DataAnalysisState(SupervisorState, total=False):
    """State for the data analysis subagent."""

    # Data analysis planning
    data_source: str  # URL, file path, or inline data
    data_type: str  # csv, json, etc.
    analysis_type: str  # visualization, statistics, processing, ml, general
    analysis_plan: str  # Planning output

    # Code generation
    code: str  # Generated Python code
    language: str  # Programming language (always python for data)

    # Execution results
    execution_result: str
    stdout: str
    stderr: str
    sandbox_id: str | None

    # Image output (supports multiple images/charts)
    visualization: str | None  # DEPRECATED: Use images instead
    visualization_type: str | None  # DEPRECATED: Use images instead
    images: list[dict[str, str]] | None  # List of {data: str, type: str, path: str}


# =============================================================================
# Node Output Types (for type-safe node returns)
# =============================================================================


class RouterOutput(TypedDict, total=False):
    """Return type for router_node."""

    selected_agent: str
    routing_reason: str
    routing_confidence: float
    active_agent: str
    delegated_task: str | None
    handoff_context: str | None
    pending_handoff: HandoffInfo | None
    events: list[dict[str, Any]]


class ChatOutput(TypedDict, total=False):
    """Return type for chat_node."""

    response: str
    events: list[dict[str, Any]]
    pending_handoff: HandoffInfo | None
    handoff_count: int
    handoff_history: list[HandoffInfo]


class ResearchPrepOutput(TypedDict, total=False):
    """Return type for research_prep_node."""

    query: str
    depth: Any  # ResearchDepth
    scenario: Any  # ResearchScenario


class ResearchPostOutput(TypedDict, total=False):
    """Return type for research_post_node."""

    shared_memory: SharedAgentMemory
    pending_handoff: HandoffInfo | None
    handoff_count: int
    handoff_history: list[HandoffInfo]
    response: str


class DataOutput(TypedDict, total=False):
    """Return type for data_node."""

    response: str
    events: list[dict[str, Any]]
    shared_memory: SharedAgentMemory
    pending_handoff: HandoffInfo | None
    handoff_count: int
    handoff_history: list[HandoffInfo]


class ErrorOutput(TypedDict, total=False):
    """Return type for error cases in nodes."""

    response: str
    events: list[dict[str, Any]]
    has_error: bool


