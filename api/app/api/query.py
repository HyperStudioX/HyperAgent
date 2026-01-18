"""Unified query router for both chat and research modes."""

import asyncio
import base64
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.db.base import get_db
from app.db.models import Conversation, ConversationMessage, File as FileModel
from app.models.schemas import (
    QueryMode,
    UnifiedQueryRequest,
    UnifiedQueryResponse,
    LLMProvider,
    ResearchStatus,
    ResearchStep,
    ResearchStepType,
    Source,
)
from app.services.llm import llm_service
from app.services.storage import storage_service
from app.services.file_storage import file_storage_service
from app.agents import agent_supervisor

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
IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


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

        elif request.mode in (QueryMode.CODE, QueryMode.WRITING, QueryMode.DATA):
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
        await storage_service.create_task(
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
    if request.mode in (QueryMode.CHAT, QueryMode.CODE, QueryMode.WRITING, QueryMode.DATA):
        history = [m.model_dump() for m in request.history]
        if not history and request.conversation_id:
            history = await get_conversation_history(
                db,
                request.conversation_id,
                current_user.id,
            )
            history = trim_duplicate_user_message(history, request.message)

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

        # Stream agent response using supervisor
        async def agent_generator() -> AsyncGenerator[str, None]:
            try:
                async for event in agent_supervisor.run(
                    query=request.message,
                    mode=request.mode.value,
                    user_id=current_user.id,
                    messages=history,
                    system_prompt=system_prompt,
                    provider=request.provider,
                    model=request.model,
                    attachment_ids=request.attachment_ids,
                    image_attachments=image_attachments,
                ):
                    if event["type"] == "token":
                        data = json.dumps({"type": "token", "data": event["content"]})
                        yield f"data: {data}\n\n"
                    elif event["type"] == "stage":
                        # Stream stage event directly (already has type field)
                        data = json.dumps(event)
                        yield f"data: {data}\n\n"
                    elif event["type"] == "tool_call":
                        # Stream tool calls with flat structure (no data wrapper)
                        data = json.dumps({
                            "type": "tool_call",
                            "tool": event.get("tool", ""),
                            "args": event.get("args", {}),
                            "id": event.get("id"),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "tool_result":
                        # Stream tool results with flat structure
                        data = json.dumps({
                            "type": "tool_result",
                            "tool": event.get("tool", ""),
                            "content": event.get("content", ""),
                            "id": event.get("id"),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "routing":
                        # Stream routing decision events
                        data = json.dumps({
                            "type": "routing",
                            "agent": event.get("agent", ""),
                            "reason": event.get("reason", ""),
                            "confidence": event.get("confidence"),
                            "low_confidence": event.get("low_confidence", False),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "handoff":
                        # Stream agent handoff events
                        data = json.dumps({
                            "type": "handoff",
                            "source": event.get("source", ""),
                            "target": event.get("target", ""),
                            "task": event.get("task", ""),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "source":
                        # Stream source events from search results
                        data = json.dumps({
                            "type": "source",
                            "title": event.get("title", ""),
                            "url": event.get("url", ""),
                            "snippet": event.get("snippet", ""),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "code_result":
                        # Stream code execution results
                        data = json.dumps({
                            "type": "code_result",
                            "output": event.get("output", ""),
                            "exit_code": event.get("exit_code"),
                            "error": event.get("error"),
                        })
                        yield f"data: {data}\n\n"
                    elif event["type"] == "visualization":
                        # Stream visualization events (generated images, charts, etc.)
                        viz_data = event.get("data")
                        if viz_data:  # Only send if data is present
                            data = json.dumps({
                                "type": "visualization",
                                "data": viz_data,
                                "mime_type": event.get("mime_type", "image/png"),
                            })
                            logger.info("streaming_visualization_event", mime_type=event.get("mime_type", "image/png"), data_length=len(viz_data) if viz_data else 0)
                            yield f"data: {data}\n\n"
                        else:
                            logger.warning("skipping_empty_visualization_event")
                    elif event["type"] == "complete":
                        yield f"data: {json.dumps({'type': 'complete', 'data': ''})}\n\n"
                    elif event["type"] == "error":
                        yield f"data: {json.dumps({'type': 'error', 'data': event.get('error', 'Unknown error')})}\n\n"

            except Exception as e:
                logger.error("agent_stream_error", mode=request.mode.value, error=str(e))
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

        return StreamingResponse(
            agent_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    else:
        # Stream research response
        if request.scenario is None:
            raise HTTPException(
                status_code=400,
                detail="Scenario is required for research mode. Choose from: academic, market, technical, news",
            )

        task_id = str(uuid.uuid4())

        # Create task in database
        task = await storage_service.create_task(
            db=db,
            task_id=task_id,
            query=request.message,
            depth=request.depth.value,
            scenario=request.scenario.value,
            user_id=current_user.id,
        )
        await db.commit()

        logger.info(
            "research_stream_started",
            task_id=task_id,
            query=request.message[:50],
            depth=request.depth.value if request.depth else None,
            scenario=request.scenario.value if request.scenario else None,
        )

        async def research_generator() -> AsyncGenerator[dict, None]:
            # Track state for database updates
            report_content = []
            step_ids = {}

            # Batching configuration - reduces DB sessions from ~10 per task to ~3
            BATCH_FLUSH_INTERVAL = 0.5  # seconds
            pending_steps: list[dict] = []
            pending_sources: list[dict] = []
            pending_step_updates: list[dict] = []
            import time
            last_flush_time = time.time()

            async def flush_pending_writes():
                """Flush all pending database writes in a single transaction."""
                nonlocal pending_steps, pending_sources, pending_step_updates, last_flush_time

                if not pending_steps and not pending_sources and not pending_step_updates:
                    return

                async with (await get_db_session()) as session:
                    # Add new steps
                    for step_data in pending_steps:
                        await storage_service.add_step(
                            db=session,
                            task_id=task_id,
                            step_id=step_data["step_id"],
                            step_type=step_data["step_type"],
                            description=step_data["description"],
                            status=step_data["status"],
                        )

                    # Update step statuses
                    for update_data in pending_step_updates:
                        await storage_service.update_step_status(
                            db=session,
                            step_id=update_data["step_id"],
                            status=update_data["status"],
                        )

                    # Add sources
                    for source_data in pending_sources:
                        await storage_service.add_source(
                            db=session,
                            task_id=task_id,
                            source_id=source_data["source_id"],
                            title=source_data["title"],
                            url=source_data["url"],
                            snippet=source_data.get("snippet"),
                            relevance_score=source_data.get("relevance_score"),
                        )

                    await session.commit()

                # Clear buffers
                pending_steps = []
                pending_sources = []
                pending_step_updates = []
                last_flush_time = time.time()

            async def maybe_flush():
                """Flush if enough time has passed since last flush."""
                if time.time() - last_flush_time >= BATCH_FLUSH_INTERVAL:
                    await flush_pending_writes()

            # Update task status to running
            async with (await get_db_session()) as session:
                await storage_service.update_task_status(session, task_id, "running")
                await session.commit()

            # Send initial event with task_id
            yield {
                "event": "message",
                "data": json.dumps({"type": "task_started", "task_id": task_id}),
            }

            try:
                async for event in agent_supervisor.run(
                    query=request.message,
                    mode="research",
                    depth=request.depth,
                    scenario=request.scenario,
                ):
                    if event["type"] == "stage":
                        step_id = str(uuid.uuid4())
                        step_type = event["name"]

                        # Track step IDs for updates
                        if event["status"] == "running":
                            step_ids[step_type] = step_id
                            # Queue step for batched insert
                            pending_steps.append({
                                "step_id": step_id,
                                "step_type": step_type,
                                "description": event["description"],
                                "status": event["status"],
                            })
                        else:
                            # Queue step status update
                            if step_type in step_ids:
                                pending_step_updates.append({
                                    "step_id": step_ids[step_type],
                                    "status": event["status"],
                                })
                                step_id = step_ids[step_type]

                        # Maybe flush pending writes
                        await maybe_flush()

                        step = ResearchStep(
                            id=step_id,
                            type=ResearchStepType(step_type),
                            description=event["description"],
                            status=ResearchStatus(event["status"]),
                        )
                        stage_data = step.model_dump()
                        # Rename 'type' to 'name' to avoid collision with event type
                        stage_data["name"] = stage_data.pop("type")
                        stage_data["type"] = "stage"
                        yield {
                            "event": "message",
                            "data": json.dumps(stage_data),
                        }

                    elif event["type"] == "source":
                        source_id = str(uuid.uuid4())

                        # Queue source for batched insert
                        pending_sources.append({
                            "source_id": source_id,
                            "title": event["title"],
                            "url": event["url"],
                            "snippet": event.get("snippet"),
                            "relevance_score": event.get("relevance_score"),
                        })

                        # Maybe flush pending writes
                        await maybe_flush()

                        source = Source(
                            id=source_id,
                            title=event["title"],
                            url=event["url"],
                            snippet=event.get("snippet"),
                        )
                        yield {
                            "event": "message",
                            "data": json.dumps({"type": "source", "data": source.model_dump()}),
                        }

                    elif event["type"] == "token":
                        from app.services.llm import extract_text_from_content
                        content = extract_text_from_content(event["content"])
                        if content:  # Only append non-empty content
                            report_content.append(content)
                            yield {
                                "event": "message",
                                "data": json.dumps({"type": "token", "data": content}),
                            }

                # Flush any remaining pending writes
                await flush_pending_writes()

                # Update task as completed with report
                async with (await get_db_session()) as session:
                    await storage_service.update_task_report(
                        db=session,
                        task_id=task_id,
                        report="".join(report_content),
                    )
                    await storage_service.update_task_status(session, task_id, "completed")
                    await session.commit()

                logger.info("research_stream_completed", task_id=task_id)
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "complete", "data": ""}),
                }

            except Exception as e:
                logger.error("research_stream_error", task_id=task_id, error=str(e))
                # Flush any pending writes before error handling
                try:
                    await flush_pending_writes()
                except Exception:
                    pass  # Don't mask the original error

                async with (await get_db_session()) as session:
                    await storage_service.update_task_status(
                        session, task_id, "failed", error=str(e)
                    )
                    await session.commit()
                yield {
                    "event": "message",
                    "data": json.dumps({"type": "error", "data": str(e)}),
                }

        return EventSourceResponse(research_generator())


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
    task_data = await storage_service.get_task_dict(db, task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_data
