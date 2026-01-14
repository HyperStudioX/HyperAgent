"""Shared state definitions for the multi-agent system."""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage

from app.models.schemas import ResearchDepth, ResearchScenario
from app.services.search import SearchResult


class AgentType(str, Enum):
    """Available agent types."""

    CHAT = "chat"
    RESEARCH = "research"
    CODE = "code"
    WRITING = "writing"
    DATA = "data"


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

    # Output
    response: str  # Final text response
    events: Annotated[list[dict[str, Any]], operator.add]  # Streaming events

    # Metadata
    task_id: str | None
    user_id: str | None


class ChatState(SupervisorState, total=False):
    """State for the chat subagent."""

    # Chat-specific fields
    system_prompt: str
    lc_messages: list[BaseMessage]  # LangChain messages for tool calling


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

    # Visualization output
    visualization: str | None  # Base64 encoded image or HTML content
    visualization_type: str | None  # mime type (image/png, text/html)
