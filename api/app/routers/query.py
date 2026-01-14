"""Unified query router for both chat and research modes."""

import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.logging import get_logger
from app.db.base import get_db
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
from app.agents.research_agent import research_agent

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

Be concise, accurate, and helpful. When providing code, use proper formatting with markdown code blocks and specify the language.

If you're unsure about something, say so rather than making things up."""


@router.post("/", response_model=UnifiedQueryResponse)
async def query(request: UnifiedQueryRequest, db: AsyncSession = Depends(get_db)):
    """Unified entry point for chat and research modes."""
    if request.mode == QueryMode.CHAT:
        # Handle chat mode
        try:
            response = await llm_service.chat(
                message=request.message,
                history=request.history,
                provider=request.provider,
                model=request.model,
                system_prompt=CHAT_SYSTEM_PROMPT,
            )

            return UnifiedQueryResponse(
                id=str(uuid.uuid4()),
                mode=QueryMode.CHAT,
                content=response,
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
async def stream_query(request: UnifiedQueryRequest, db: AsyncSession = Depends(get_db)):
    """Stream response for both chat and research modes."""
    if request.mode == QueryMode.CHAT:
        # Stream chat response
        async def chat_generator() -> AsyncGenerator[str, None]:
            try:
                async for token in llm_service.stream_chat(
                    message=request.message,
                    history=request.history,
                    provider=request.provider,
                    model=request.model,
                    system_prompt=CHAT_SYSTEM_PROMPT,
                ):
                    data = json.dumps({"type": "token", "data": token})
                    yield f"data: {data}\n\n"

                yield f"data: {json.dumps({'type': 'complete', 'data': ''})}\n\n"
            except Exception as e:
                logger.error("chat_stream_error", error=str(e))
                yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"

        return StreamingResponse(
            chat_generator(),
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
        )
        await db.commit()

        logger.info("research_stream_started", task_id=task_id, query=request.message[:50])

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
                async for event in research_agent.run(
                    query=request.message,
                    depth=request.depth,
                    scenario=request.scenario,
                ):
                    if event["type"] == "step":
                        step_id = str(uuid.uuid4())
                        step_type = event["step_type"]

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
                        yield {
                            "event": "message",
                            "data": json.dumps({"type": "step", "data": step.model_dump()}),
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
                        report_content.append(event["content"])
                        yield {
                            "event": "message",
                            "data": json.dumps({"type": "token", "data": event["content"]}),
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
async def get_query_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """Get the status of a research task."""
    task_data = await storage_service.get_task_dict(db, task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")

    return task_data
