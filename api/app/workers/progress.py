"""Progress reporter for real-time task updates via Redis Pub/Sub."""

import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.logging import get_logger

logger = get_logger(__name__)


class ProgressReporter:
    """
    Publishes task progress events to Redis pub/sub channels.

    This enables real-time progress updates to connected SSE/WebSocket clients
    without coupling the worker to the HTTP request lifecycle.
    """

    CHANNEL_PREFIX = "hyperagent:progress:"

    def __init__(self, redis: Redis, task_id: str):
        """
        Initialize the progress reporter.

        Args:
            redis: Redis connection
            task_id: Task ID to publish progress for
        """
        self.redis = redis
        self.task_id = task_id
        self.channel = f"{self.CHANNEL_PREFIX}{task_id}"

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        """
        Publish a progress event to the task's channel.

        Args:
            event_type: Type of event (step, source, token, token_batch, complete, error)
            data: Event payload
        """
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        try:
            await self.redis.publish(self.channel, message)
        except Exception as e:
            logger.error("progress_emit_failed", task_id=self.task_id, error=str(e))

    async def emit_step(
        self,
        step_type: str,
        description: str,
        status: str,
        step_id: str | None = None,
    ) -> None:
        """
        Emit a step progress event.

        Args:
            step_type: Type of step (search, analyze, synthesize, write)
            description: Human-readable step description
            status: Step status (running, completed, failed)
            step_id: Optional step ID for updates
        """
        await self.emit("step", {
            "step_id": step_id,
            "step_type": step_type,
            "description": description,
            "status": status,
        })

    async def emit_source(
        self,
        source_id: str,
        title: str,
        url: str,
        snippet: str | None = None,
    ) -> None:
        """
        Emit a source discovery event.

        Args:
            source_id: Unique source ID
            title: Source title
            url: Source URL
            snippet: Optional source snippet
        """
        await self.emit("source", {
            "source_id": source_id,
            "title": title,
            "url": url,
            "snippet": snippet,
        })

    async def emit_token(self, content: str) -> None:
        """
        Emit a token/content event.

        Args:
            content: Token content
        """
        await self.emit("token", {"content": content})

    async def emit_token_batch(self, content: str) -> None:
        """
        Emit a batch of tokens.

        Args:
            content: Batched content
        """
        await self.emit("token_batch", {"content": content})

    async def emit_progress(self, percentage: int, message: str = "") -> None:
        """
        Emit a progress percentage update.

        Args:
            percentage: Progress 0-100
            message: Optional status message
        """
        await self.emit("progress", {
            "percentage": percentage,
            "message": message,
        })

    async def emit_complete(self) -> None:
        """Emit task completion event."""
        await self.emit("complete", {"task_id": self.task_id})

    async def emit_error(self, error: str) -> None:
        """
        Emit task error event.

        Args:
            error: Error message
        """
        await self.emit("error", {"task_id": self.task_id, "error": error})
