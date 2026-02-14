"""Research streaming via Redis pub/sub from background workers.

Extracted from query.py to keep the main endpoint file focused.
"""

import json
import uuid
from typing import AsyncGenerator

from app.core.logging import get_logger
from app.core.redis import close_redis_pool, get_redis
from app.models.schemas import (
    ResearchStatus,
    ResearchStep,
    ResearchStepType,
    Source,
)

logger = get_logger(__name__)


# Re-export for backward compatibility with main.py import
close_shared_redis = close_redis_pool


async def research_stream_from_worker(task_id: str) -> AsyncGenerator[dict, None]:
    """Stream research progress from worker via Redis pub/sub."""
    # Send initial event with task_id for backward compatibility
    yield {
        "event": "message",
        "data": json.dumps({"type": "task_started", "task_id": task_id}),
    }

    # Subscribe to worker progress channel using shared Redis connection
    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"hyperagent:progress:{task_id}"

    try:
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                event_data = json.loads(message["data"])
                event_type = event_data.get("type")
                data = event_data.get("data", {})

                # Transform worker events to match frontend expected format
                if event_type == "step":
                    # Map step events to stage format for frontend compatibility
                    step_type = data.get("step_type", "")
                    try:
                        step_type_enum = ResearchStepType(step_type)
                    except ValueError:
                        # Unknown step type - pass through as-is
                        logger.warning("unknown_step_type", step_type=step_type)
                        stage_data = {
                            "type": "stage",
                            "name": step_type,
                            "description": data.get("description", step_type),
                            "status": data.get("status", "running"),
                            "id": data.get("step_id", str(uuid.uuid4())),
                        }
                        yield {
                            "event": "message",
                            "data": json.dumps(stage_data),
                        }
                        continue

                    step = ResearchStep(
                        id=data.get("step_id", str(uuid.uuid4())),
                        type=step_type_enum,
                        description=data["description"],
                        status=ResearchStatus(data["status"]),
                    )
                    stage_data = step.model_dump()
                    stage_data["name"] = stage_data.pop("type")
                    stage_data["type"] = "stage"
                    yield {
                        "event": "message",
                        "data": json.dumps(stage_data),
                    }

                elif event_type == "source":
                    source = Source(
                        id=data.get("source_id", str(uuid.uuid4())),
                        title=data["title"],
                        url=data["url"],
                        snippet=data.get("snippet"),
                    )
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "source", "data": source.model_dump()}),
                    }

                elif event_type == "token":
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "token", "data": data.get("content", "")}),
                    }

                elif event_type == "token_batch":
                    # Token batch is just multiple tokens at once
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "token", "data": data.get("content", "")}),
                    }

                elif event_type == "tool_call":
                    # Forward tool call events
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "tool_call",
                            "tool": data.get("tool", ""),
                            "args": data.get("args", {}),
                            "id": data.get("id"),
                        }),
                    }

                elif event_type == "tool_result":
                    # Forward tool result events
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "tool_result",
                            "tool": data.get("tool", ""),
                            "output": data.get("output", ""),
                            "id": data.get("id"),
                        }),
                    }

                elif event_type == "progress":
                    # Forward progress percentage events
                    yield {
                        "event": "message",
                        "data": json.dumps({
                            "type": "progress",
                            "percentage": data.get("percentage", 0),
                            "message": data.get("message", ""),
                        }),
                    }

                elif event_type == "complete":
                    logger.info("research_stream_completed", task_id=task_id)
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "complete", "data": ""}),
                    }
                    break

                elif event_type == "error":
                    logger.error(
                        "research_stream_error",
                        task_id=task_id,
                        error=data.get("error", "Unknown error"),
                    )
                    yield {
                        "event": "message",
                        "data": json.dumps({"type": "error", "data": data.get("error", "Unknown error")}),
                    }
                    break

    except Exception as e:
        logger.error("research_stream_subscription_error", task_id=task_id, error=str(e))
        yield {
            "event": "message",
            "data": json.dumps({"type": "error", "data": str(e)}),
        }
    finally:
        await pubsub.unsubscribe(channel)
        # Note: redis client is shared (module-level pool), do not close it here
