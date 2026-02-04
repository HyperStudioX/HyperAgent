"""Unified query router for both chat and research modes."""

import asyncio
import base64
import json
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.agents import agent_supervisor
from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import Conversation, ConversationMessage
from app.db.models import File as FileModel
from app.guardrails.scanners.input_scanner import input_scanner
from app.models.schemas import (
    LLMProvider,
    QueryMode,
    ResearchStatus,
    ResearchStep,
    ResearchStepType,
    Source,
    UnifiedQueryRequest,
    UnifiedQueryResponse,
)
from app.repository import deep_research_repository
from app.services.file_storage import file_storage_service
from app.workers.task_queue import task_queue

logger = get_logger(__name__)

router = APIRouter(prefix="/query")


def get_default_model(provider: LLMProvider) -> str:
    """Get default model for a provider."""
    defaults = {
        LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
        LLMProvider.OPENAI: "gpt-4o",
        LLMProvider.GEMINI: "gemini-2.5-flash",
    }
    return defaults.get(provider, "claude-sonnet-4-20250514")


CHAT_SYSTEM_PROMPT = """You are HyperAgent, a helpful AI assistant. You are designed to help users with various tasks including coding, research, analysis, and general questions.

You have access to a web search tool that you can use to find current information when needed. Use it when:
- The user asks about recent events or news
- You need to verify facts or find up-to-date information
- The question requires knowledge beyond your training data

When you decide to search, refine the query to improve quality:
- Include specific entities, versions, dates, and locations
- Add the most likely authoritative source (e.g. official docs/site:example.com)
- Use short, focused queries rather than a single broad query
- Avoid vague terms; include exact product or feature names

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""

MAX_CHAT_HISTORY_MESSAGES = 20


async def get_conversation_history(
    db: AsyncSession,
    conversation_id: str | None,
    user_id: str,
    limit: int = MAX_CHAT_HISTORY_MESSAGES,
) -> list[dict]:
    """Fetch recent conversation history for short-term memory."""
    if not conversation_id:
        return []

    result = await db.execute(
        select(Conversation.id).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        return []

    message_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(message_result.scalars().all()))
    history = [
        {
            "role": message.role,
            "content": message.content,
            "metadata": message.message_metadata,
        }
        for message in messages
        if message.role in ("user", "assistant")
    ]
    return history


def trim_duplicate_user_message(history: list[dict], query: str) -> list[dict]:
    """Remove duplicate trailing user message when it matches the current query."""
    if not history:
        return history
    last = history[-1]
    if last.get("role") == "user" and last.get("content", "").strip() == query.strip():
        return history[:-1]
    return history


async def get_file_context(
    db: AsyncSession,
    attachment_ids: list[str],
    user_id: str,
) -> str:
    """Get extracted text from attached files for LLM context."""
    if not attachment_ids:
        return ""

    result = await db.execute(
        select(FileModel).where(
            FileModel.id.in_(attachment_ids),
            FileModel.user_id == user_id,
        )
    )
    files = result.scalars().all()

    context_parts = []
    for file in files:
        if file.extracted_text:
            context_parts.append(
                f"[Attached file: {file.original_filename}]\n{file.extracted_text}\n"
            )
        else:
            context_parts.append(
                f"[Attached file: {file.original_filename} - binary content not extracted]\n"
            )

    if context_parts:
        return "\n---\n".join(context_parts)
    return ""


# Image MIME types that can be processed by vision tools
IMAGE_MIME_TYPES: set[str] = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def _sse_data(payload: dict[str, Any]) -> str:
    """Format a payload as an SSE data line.

    Args:
        payload: Dictionary to serialize as JSON

    Returns:
        SSE formatted data string
    """
    return f"data: {json.dumps(payload)}\n\n"


async def get_image_attachments(
    db: AsyncSession,
    attachment_ids: list[str],
    user_id: str,
) -> list[dict]:
    """Get image attachments as base64 for vision tool usage.

    Uses asyncio.gather for parallel downloads to improve performance.

    Returns:
        List of dicts with {id, filename, base64_data, mime_type}
    """
    if not attachment_ids:
        return []

    result = await db.execute(
        select(FileModel).where(
            FileModel.id.in_(attachment_ids),
            FileModel.user_id == user_id,
        )
    )
    files = result.scalars().all()

    # Filter to only image files
    image_files = [f for f in files if f.content_type in IMAGE_MIME_TYPES]

    if not image_files:
        return []

    async def process_image(file: FileModel) -> dict | None:
        """Process a single image file and return attachment dict or None on error."""
        try:
            file_data = await file_storage_service.download_file(file.storage_key)
            base64_data = base64.b64encode(file_data.read()).decode("utf-8")

            logger.info(
                "image_attachment_loaded",
                file_id=file.id,
                filename=file.original_filename,
                mime_type=file.content_type,
            )

            return {
                "id": file.id,
                "filename": file.original_filename,
                "base64_data": base64_data,
                "mime_type": file.content_type,
            }
        except Exception as e:
            logger.error(
                "image_attachment_load_failed",
                file_id=file.id,
                error=str(e),
            )
            return None

    # Download all images in parallel
    results = await asyncio.gather(*[process_image(f) for f in image_files])

    # Filter out None results (failed downloads)
    return [r for r in results if r is not None]


@router.post("/", response_model=UnifiedQueryResponse)
async def query(
    request: UnifiedQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Unified entry point for chat and research modes."""
    try:
        # Get file context if attachments provided
        file_context = await get_file_context(
            db,
            request.attachment_ids,
            current_user.id,
        )

        # Enhance system prompt with file context
        system_prompt = CHAT_SYSTEM_PROMPT
        if file_context:
            system_prompt = f"{CHAT_SYSTEM_PROMPT}\n\nThe user has attached the following files for context:\n\n{file_context}"

        history = [m.model_dump() for m in request.history]
        if not history and request.conversation_id:
            history = await get_conversation_history(
                db,
                request.conversation_id,
                current_user.id,
            )
            history = trim_duplicate_user_message(history, request.message)

        if request.mode == QueryMode.CHAT:
            # Use agent supervisor even for chat to enable tools
            result = await agent_supervisor.invoke(
                query=request.message,
                mode=QueryMode.CHAT.value,
                user_id=current_user.id,
                messages=history,
                system_prompt=system_prompt,
                provider=request.provider,
                model=request.model,
            )

            return UnifiedQueryResponse(
                id=str(uuid.uuid4()),
                mode=QueryMode.CHAT,
                content=result.get("response", ""),
                model=request.model or get_default_model(request.provider),
                provider=request.provider,
            )

        elif request.mode in (QueryMode.APP, QueryMode.DATA, QueryMode.IMAGE):
            # Use agent supervisor for specialized modes
            result = await agent_supervisor.invoke(
                query=request.message,
                mode=request.mode.value,
                user_id=current_user.id,
                messages=history,
                system_prompt=system_prompt,
                provider=request.provider,
                model=request.model,
            )

            return UnifiedQueryResponse(
                id=str(uuid.uuid4()),
                mode=request.mode,
                content=result.get("response", ""),
                model=request.model or get_default_model(request.provider),
                provider=request.provider,
            )
    except ValueError as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("chat_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

    else:
        # Handle research mode
        if request.scenario is None:
            raise HTTPException(
                status_code=400,
                detail="Scenario is required for research mode. Choose from: academic, market, technical, news",
            )

        task_id = str(uuid.uuid4())

        # Create task in database
        await deep_research_repository.create_task(
            db=db,
            task_id=task_id,
            query=request.message,
            depth=request.depth.value,
            scenario=request.scenario.value,
            user_id=current_user.id,
        )

        logger.info("research_task_created", task_id=task_id, query=request.message[:50])

        return UnifiedQueryResponse(
            id=str(uuid.uuid4()),
            mode=QueryMode.RESEARCH,
            task_id=task_id,
            model=request.model or get_default_model(request.provider),
            provider=request.provider,
        )


@router.post("/stream")
async def stream_query(
    request: UnifiedQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Stream response for chat, research, and other agent modes."""
    if request.mode in (QueryMode.CHAT, QueryMode.APP, QueryMode.DATA, QueryMode.IMAGE):
        history = [m.model_dump() for m in request.history]
        if not history and request.conversation_id:
            history = await get_conversation_history(
                db,
                request.conversation_id,
                current_user.id,
            )
            history = trim_duplicate_user_message(history, request.message)

        # Debug logging for conversation context
        logger.info(
            "query_stream_context",
            conversation_id=request.conversation_id,
            history_from_request=len(request.history),
            history_total=len(history),
            has_history=bool(history),
        )

        # Get file context if attachments provided
        file_context = await get_file_context(
            db,
            request.attachment_ids,
            current_user.id,
        )

        # Get image attachments as base64 for vision tool usage
        image_attachments = await get_image_attachments(
            db,
            request.attachment_ids,
            current_user.id,
        )

        # Enhance system prompt with file context
        system_prompt = CHAT_SYSTEM_PROMPT
        if file_context:
            system_prompt = f"{CHAT_SYSTEM_PROMPT}\n\nThe user has attached the following files for context:\n\n{file_context}"

        # Generate task_id for browser session management if not provided
        # Use request.task_id, conversation_id as fallback, or generate a new one
        chat_task_id = request.task_id or request.conversation_id or str(uuid.uuid4())

        # Input guardrails check
        scan_result = await input_scanner.scan(request.message)
        if scan_result.blocked:
            logger.warning(
                "input_guardrail_blocked",
                violations=[v.value for v in scan_result.violations],
                reason=scan_result.reason,
            )

            async def blocked_generator() -> AsyncGenerator[str, None]:
                error_message = (
                    "I'm unable to process this request due to safety concerns. "
                    "Please rephrase your message and try again."
                )
                yield _sse_data({"type": "token", "data": error_message})
                yield _sse_data({"type": "complete", "data": ""})

            return StreamingResponse(
                blocked_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        # Stream agent response using supervisor
        async def agent_generator() -> AsyncGenerator[str, None]:
            try:
                async for event in agent_supervisor.run(
                    query=request.message,
                    mode=request.mode.value,
                    task_id=chat_task_id,
                    user_id=current_user.id,
                    messages=history,
                    system_prompt=system_prompt,
                    provider=request.provider,
                    model=request.model,
                    attachment_ids=request.attachment_ids,
                    image_attachments=image_attachments,
                    locale=request.locale,
                ):
                    event_type = event["type"]

                    if event_type == "token":
                        yield _sse_data({"type": "token", "data": event["content"]})

                    elif event_type == "stage":
                        yield _sse_data(event)

                    elif event_type == "tool_call":
                        yield _sse_data({
                            "type": "tool_call",
                            "tool": event.get("tool", ""),
                            "args": event.get("args", {}),
                            "id": event.get("id"),
                        })

                    elif event_type == "tool_result":
                        yield _sse_data({
                            "type": "tool_result",
                            "tool": event.get("tool", ""),
                            "content": event.get("content", ""),
                            "id": event.get("id"),
                        })

                    elif event_type == "routing":
                        yield _sse_data({
                            "type": "routing",
                            "agent": event.get("agent", ""),
                            "reason": event.get("reason", ""),
                            "confidence": event.get("confidence"),
                            "low_confidence": event.get("low_confidence", False),
                        })

                    elif event_type == "handoff":
                        yield _sse_data({
                            "type": "handoff",
                            "source": event.get("source", ""),
                            "target": event.get("target", ""),
                            "task": event.get("task", ""),
                        })

                    elif event_type == "source":
                        yield _sse_data({
                            "type": "source",
                            "title": event.get("title", ""),
                            "url": event.get("url", ""),
                            "snippet": event.get("snippet", ""),
                        })

                    elif event_type == "code_result":
                        yield _sse_data({
                            "type": "code_result",
                            "output": event.get("output", ""),
                            "exit_code": event.get("exit_code"),
                            "error": event.get("error"),
                        })

                    elif event_type == "browser_stream":
                        logger.info(
                            "streaming_browser_stream_event",
                            sandbox_id=event.get("sandbox_id", "")[:8],
                        )
                        yield _sse_data({
                            "type": "browser_stream",
                            "stream_url": event.get("stream_url", ""),
                            "sandbox_id": event.get("sandbox_id", ""),
                            "auth_key": event.get("auth_key"),
                        })

                    elif event_type == "browser_action":
                        yield _sse_data({
                            "type": "browser_action",
                            "action": event.get("action", ""),
                            "description": event.get("description", ""),
                            "target": event.get("target"),
                            "status": event.get("status", "running"),
                        })

                    elif event_type == "terminal_command":
                        yield _sse_data({
                            "type": "terminal_command",
                            "command": event.get("command", ""),
                            "cwd": event.get("cwd", "/home/user"),
                            "timestamp": event.get("timestamp"),
                        })

                    elif event_type == "terminal_output":
                        yield _sse_data({
                            "type": "terminal_output",
                            "content": event.get("content", ""),
                            "stream": event.get("stream", "stdout"),
                            "timestamp": event.get("timestamp"),
                        })

                    elif event_type == "terminal_error":
                        yield _sse_data({
                            "type": "terminal_error",
                            "content": event.get("content", ""),
                            "exit_code": event.get("exit_code"),
                            "timestamp": event.get("timestamp"),
                        })

                    elif event_type == "terminal_complete":
                        yield _sse_data({
                            "type": "terminal_complete",
                            "exit_code": event.get("exit_code", 0),
                            "timestamp": event.get("timestamp"),
                        })

                    elif event_type == "skill_output":
                        yield _sse_data({
                            "type": "skill_output",
                            "skill_id": event.get("skill_id", ""),
                            "output": event.get("output", {}),
                        })

                    elif event_type == "image":
                        img_data = event.get("data")
                        img_url = event.get("url")
                        if img_data or img_url:
                            payload: dict[str, Any] = {
                                "type": "image",
                                "mime_type": event.get("mime_type", "image/png"),
                                "index": event.get("index"),
                            }
                            if img_data:
                                payload["data"] = img_data
                            if img_url:
                                payload["url"] = img_url
                            if event.get("storage_key"):
                                payload["storage_key"] = event["storage_key"]
                            if event.get("file_id"):
                                payload["file_id"] = event["file_id"]

                            logger.info(
                                "streaming_image_event",
                                mime_type=event.get("mime_type", "image/png"),
                                has_data=bool(img_data),
                                has_url=bool(img_url),
                                index=event.get("index"),
                            )
                            yield _sse_data(payload)
                        else:
                            logger.warning("skipping_empty_image_event", event=event)

                    elif event_type == "interrupt":
                        logger.info(
                            "streaming_interrupt_event",
                            interrupt_id=event.get("interrupt_id", "")[:8],
                            interrupt_type=event.get("interrupt_type"),
                        )
                        yield _sse_data({
                            "type": "interrupt",
                            "interrupt_id": event.get("interrupt_id", ""),
                            "interrupt_type": event.get("interrupt_type", "input"),
                            "title": event.get("title", "Agent Question"),
                            "message": event.get("message", ""),
                            "options": event.get("options"),
                            "tool_info": event.get("tool_info"),
                            "default_action": event.get("default_action"),
                            "timeout_seconds": event.get("timeout_seconds", 120),
                            "timestamp": event.get("timestamp"),
                        })

                    elif event_type == "complete":
                        yield _sse_data({"type": "complete", "data": ""})

                    elif event_type == "error":
                        yield _sse_data({
                            "type": "error",
                            "data": event.get("error", "Unknown error"),
                        })

            except Exception as e:
                logger.error("agent_stream_error", mode=request.mode.value, error=str(e))
                yield _sse_data({"type": "error", "data": str(e)})

        return StreamingResponse(
            agent_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    else:
        # Stream research response via worker queue
        if request.scenario is None:
            raise HTTPException(
                status_code=400,
                detail="Scenario is required for research mode. Choose from: academic, market, technical, news",
            )

        # Use frontend-provided task_id if available, otherwise generate new one
        task_id = request.task_id or str(uuid.uuid4())

        # Create task in database
        await deep_research_repository.create_task(
            db=db,
            task_id=task_id,
            query=request.message,
            depth=request.depth.value,
            scenario=request.scenario.value,
            user_id=current_user.id,
        )

        # Update status to queued before enqueueing
        await deep_research_repository.update_task_status(db, task_id, "queued")
        await db.commit()

        # Enqueue to worker for background processing
        job_id = await task_queue.enqueue_research_task(
            task_id=task_id,
            query=request.message,
            depth=request.depth.value,
            scenario=request.scenario.value,
            user_id=current_user.id,
            locale=request.locale,
        )

        # Update task with worker job ID
        await deep_research_repository.update_task_worker_info(db, task_id, job_id, "api-enqueue")
        await db.commit()

        logger.info(
            "research_stream_enqueued",
            task_id=task_id,
            job_id=job_id,
            query=request.message[:50],
            depth=request.depth.value if request.depth else None,
            scenario=request.scenario.value if request.scenario else None,
        )

        async def research_stream_from_worker() -> AsyncGenerator[dict, None]:
            """Stream research progress from worker via Redis pub/sub."""
            from redis.asyncio import Redis

            from app.config import settings

            # Send initial event with task_id for backward compatibility
            yield {
                "event": "message",
                "data": json.dumps({"type": "task_started", "task_id": task_id}),
            }

            # Subscribe to worker progress channel
            redis = Redis.from_url(settings.redis_url, decode_responses=True)
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
                await redis.aclose()

        return EventSourceResponse(research_stream_from_worker())


async def get_db_session() -> AsyncSession:
    """Get a new database session for use in generators."""
    from app.db.base import async_session_maker

    return async_session_maker()


@router.get("/status/{task_id}")
async def get_query_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get the status of a research task."""
    task_data = await deep_research_repository.get_task_dict(db, task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_data
