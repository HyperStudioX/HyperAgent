"""Shared state definitions for the multi-agent system."""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage

from app.models.schemas import LLMProvider, ModelTier, ResearchDepth, ResearchScenario
from app.services.search import SearchResult


class AgentType(str, Enum):
    """Available agent types."""

    CHAT = "chat"
    RESEARCH = "research"
    CODE = "code"
    WRITING = "writing"
    DATA = "data"


class HandoffInfo(TypedDict, total=False):
    """Information about a handoff request."""

    source_agent: str  # Agent that initiated the handoff
    target_agent: str  # Agent to transfer control to
    task_description: str  # What the target agent should do
    context: str  # Additional context for the handoff


class SharedAgentMemory(TypedDict, total=False):
    """Shared memory accessible across agents during handoffs.

    This allows agents to share findings, intermediate results, and context
    when delegating tasks to other agents.
    """

    # Research findings from research agent
    research_findings: str
    research_sources: list[dict[str, Any]]

    # Code artifacts from code agent
    generated_code: str
    code_language: str
    execution_results: str

    # Writing artifacts from writing agent
    writing_outline: str
    writing_draft: str

    # Data analysis artifacts from data agent
    data_analysis_plan: str
    data_visualizations: list[dict[str, str]]

    # General context that any agent can add
    additional_context: str


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


class ChatState(SupervisorState, total=False):
    """State for the chat subagent."""

    # Chat-specific fields
    system_prompt: str
    lc_messages: list[BaseMessage]  # LangChain messages for tool calling
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
    search_count: int  # Track number of search iterations

    # Handoff tracking
    deferred_handoff: HandoffInfo | None  # Handoff deferred until search tools complete

    # Research outputs
    sources: list[SearchResult]
    analysis: str
    synthesis: str
    report_chunks: list[str]


class CodeState(SupervisorState, total=False):
    """State for the code execution subagent."""

    # Code execution
    code: str
    language: str
    execution_result: str
    stdout: str
    stderr: str
    sandbox_id: str | None


class WritingState(SupervisorState, total=False):
    """State for the writing subagent."""

    # Writing configuration
    writing_type: str  # article, documentation, creative, etc.
    tone: str
    outline: str
    draft: str
    final_content: str


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

    # Visualization output (supports multiple visualizations)
    visualization: str | None  # DEPRECATED: Use visualizations instead
    visualization_type: str | None  # DEPRECATED: Use visualizations instead
    visualizations: list[dict[str, str]] | None  # List of {data: str, type: str, path: str}
