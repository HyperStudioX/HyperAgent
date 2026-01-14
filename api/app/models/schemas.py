from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


class QueryMode(str, Enum):
    CHAT = "chat"
    RESEARCH = "research"
    CODE = "code"
    WRITING = "writing"
    DATA = "data"


class ResearchScenario(str, Enum):
    ACADEMIC = "academic"
    MARKET_ANALYSIS = "market"
    TECHNICAL = "technical"
    NEWS = "news"


# Chat Schemas
class ChatMessage(BaseModel):
    """A single chat message."""

    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str
    conversation_id: str | None = None
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    id: str
    content: str
    model: str
    provider: LLMProvider
    tokens: int | None = None


class StreamEvent(BaseModel):
    """Server-sent event for streaming."""

    type: Literal["token", "step", "source", "complete", "error"]
    data: str


# Research Schemas
class ResearchDepth(str, Enum):
    FAST = "fast"
    DEEP = "deep"


class ResearchRequest(BaseModel):
    """Request to start a research task."""

    query: str
    depth: ResearchDepth = ResearchDepth.FAST
    scenario: ResearchScenario = ResearchScenario.ACADEMIC
    conversation_id: str | None = None


class ResearchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchStepType(str, Enum):
    SEARCH = "search"
    ANALYZE = "analyze"
    SYNTHESIZE = "synthesize"
    WRITE = "write"


class ResearchStep(BaseModel):
    """A step in the research process."""

    id: str
    type: ResearchStepType
    description: str
    status: ResearchStatus
    output: str | None = None


class Source(BaseModel):
    """A source found during research."""

    id: str
    title: str
    url: str
    snippet: str | None = None


class ResearchTaskResponse(BaseModel):
    """Response when starting a research task."""

    task_id: str
    status: ResearchStatus


class ResearchResult(BaseModel):
    """Result of a completed research task."""

    task_id: str
    query: str
    status: ResearchStatus
    steps: list[ResearchStep]
    sources: list[Source]
    summary: str | None = None
    report: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


# Unified Query Schemas
class UnifiedQueryRequest(BaseModel):
    """Unified request for both chat and research modes."""

    message: str
    mode: QueryMode = QueryMode.CHAT
    scenario: ResearchScenario | None = None
    depth: ResearchDepth = ResearchDepth.FAST
    conversation_id: str | None = None
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class UnifiedQueryResponse(BaseModel):
    """Unified response for both chat and research modes."""

    id: str
    mode: QueryMode
    task_id: str | None = None
    content: str | None = None
    model: str
    provider: LLMProvider


# Conversation Schemas
class ConversationType(str, Enum):
    CHAT = "chat"
    RESEARCH = "research"
    CODE = "code"
    WRITING = "writing"
    DATA = "data"


class ConversationMessageResponse(BaseModel):
    """Response model for a conversation message."""

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str


class ConversationResponse(BaseModel):
    """Response model for a conversation."""

    id: str
    title: str
    type: ConversationType
    user_id: str
    created_at: str
    updated_at: str
    messages: list[ConversationMessageResponse] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """Response model for conversation list (without messages)."""

    id: str
    title: str
    type: ConversationType
    user_id: str
    created_at: str
    updated_at: str


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    title: str
    type: ConversationType = ConversationType.CHAT


class UpdateConversationRequest(BaseModel):
    """Request to update a conversation."""

    title: str | None = None


class CreateMessageRequest(BaseModel):
    """Request to add a message to a conversation."""

    role: MessageRole
    content: str
    metadata: dict[str, Any] | None = None


class UpdateMessageRequest(BaseModel):
    """Request to update a message."""

    content: str
