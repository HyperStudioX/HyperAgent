"""Unified query router for both chat and research modes."""

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
                ):
                    if event["type"] == "token":
                        data = json.dumps({"type": "token", "data": event["content"]})
                        yield f"data: {data}\n\n"
                    elif event["type"] == "stage":
                        # Stream stage event directly (already has type field)
                        data = json.dumps(event)
                        yield f"data: {data}\n\n"
                    elif event["type"] == "tool_call":
                        # Stream tool calls
                        data = json.dumps({"type": "tool_call", "data": event})
                        yield f"data: {data}\n\n"
                    elif event["type"] == "tool_result":
                        data = json.dumps({"type": "tool_result", "data": event})
                        yield f"data: {data}\n\n"
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

                            # Add step to database
                            async with (await get_db_session()) as session:
                                await storage_service.add_step(
                                    db=session,
                                    task_id=task_id,
                                    step_id=step_id,
                                    step_type=step_type,
                                    description=event["description"],
                                    status=event["status"],
                                )
                                await session.commit()
                        else:
                            # Update existing step
                            if step_type in step_ids:
                                async with (await get_db_session()) as session:
                                    await storage_service.update_step_status(
                                        db=session,
                                        step_id=step_ids[step_type],
                                        status=event["status"],
                                    )
                                    await session.commit()
                                step_id = step_ids[step_type]

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

                        # Add source to database
                        async with (await get_db_session()) as session:
                            await storage_service.add_source(
                                db=session,
                                task_id=task_id,
                                source_id=source_id,
                                title=event["title"],
                                url=event["url"],
                                snippet=event.get("snippet"),
                                relevance_score=event.get("relevance_score"),
                            )
                            await session.commit()

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
