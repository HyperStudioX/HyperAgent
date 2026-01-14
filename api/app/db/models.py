"""Database ORM models for research tasks."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    research_tasks: Mapped[list["ResearchTask"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "image": self.image,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResearchTask(Base):
    """Research task model."""

    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[str] = mapped_column(String(20), default="standard")
    scenario: Mapped[str] = mapped_column(String(20), default="academic")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Worker tracking fields
    worker_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    worker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[int] = mapped_column(default=0)
    retry_count: Mapped[int] = mapped_column(default=0)
    priority: Mapped[int] = mapped_column(default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="research_tasks")
    steps: Mapped[list["ResearchStep"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="ResearchStep.created_at"
    )
    sources: Mapped[list["ResearchSource"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "query": self.query,
            "depth": self.depth,
            "scenario": self.scenario,
            "status": self.status,
            "report": self.report,
            "error": self.error,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "progress": self.progress,
            "worker_job_id": self.worker_job_id,
            "steps": [step.to_dict() for step in self.steps],
            "sources": [source.to_dict() for source in self.sources],
        }


class ResearchStep(Base):
    """Research step model."""

    __tablename__ = "research_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    task: Mapped["ResearchTask"] = relationship(back_populates="steps")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "status": self.status,
            "output": self.output,
        }


class ResearchSource(Base):
    """Research source model."""

    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("research_tasks.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    task: Mapped["ResearchTask"] = relationship(back_populates="sources")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "relevance_score": self.relevance_score,
        }


class BackgroundTask(Base):
    """Generic background task model for non-research async work."""

    __tablename__ = "background_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[int] = mapped_column(default=0)

    # Input/Output
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON input
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON result
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Tracking
    worker_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    worker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    progress: Mapped[int] = mapped_column(default=0)
    retry_count: Mapped[int] = mapped_column(default=0)
    max_retries: Mapped[int] = mapped_column(default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # User association
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "task_type": self.task_type,
            "status": self.status,
            "priority": self.priority,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "progress": self.progress,
            "worker_job_id": self.worker_job_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Conversation(Base):
    """Conversation model for chat sessions."""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="chat")
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )

    def to_dict(self, include_messages: bool = True) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_messages:
            result["messages"] = [msg.to_dict() for msg in self.messages]
        return result


class ConversationMessage(Base):
    """Message model for conversation messages."""

    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.message_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
