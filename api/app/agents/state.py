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
    IMAGE = "image"


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

    # Image output (supports multiple images/charts)
    visualization: str | None  # DEPRECATED: Use images instead
    visualization_type: str | None  # DEPRECATED: Use images instead
    images: list[dict[str, str]] | None  # List of {data: str, type: str, path: str}


class ImageState(SupervisorState, total=False):
    """State for the image generation subagent."""

    # Request analysis
    original_prompt: str  # User's original request
    refined_prompt: str  # LLM-enhanced prompt for better results
    should_refine: bool  # Whether prompt refinement is needed

    # Image parameters
    style: str  # e.g., "photorealistic", "artistic", "cartoon"
    aspect_ratio: str  # e.g., "1:1", "16:9", "9:16"
    size: str  # e.g., "1024x1024", "1792x1024"
    quality: str  # "standard" or "hd" (for OpenAI)

    # Provider configuration
    image_provider: str  # "gemini" or "openai"
    image_model: str  # Specific model name

    # Generation results
    generated_images: list[dict[str, Any]]  # List of {base64_data, url, revised_prompt}
    generation_status: str  # "pending", "generating", "completed", "failed"
    generation_error: str | None  # Error message if failed
