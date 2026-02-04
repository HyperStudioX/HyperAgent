"""Skill executor service for executing skills with state management and event streaming."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import events
from app.core.logging import get_logger
from app.db.models import SkillExecution
from app.services.skill_registry import skill_registry

logger = get_logger(__name__)


class SkillExecutor:
    """Executes skills with state management and event streaming."""

    async def execute_skill(
        self,
        skill_id: str,
        params: dict[str, Any],
        user_id: str,
        agent_type: str,
        task_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Execute a skill and stream events.

        Args:
            skill_id: Skill identifier
            params: Input parameters
            user_id: User ID for tracking
            agent_type: Agent type invoking the skill
            task_id: Optional task ID for context
            db: Optional database session for execution tracking

        Yields:
            Event dictionaries
        """
        # Get skill from registry
        skill = skill_registry.get_skill(skill_id)
        if not skill:
            yield events.error(f"Skill not found: {skill_id}")
            return

        # Validate input
        is_valid, error_msg = skill.validate_input(params)
        if not is_valid:
            yield events.error(f"Invalid input for skill {skill_id}: {error_msg}")
            return

        # Create execution record
        execution_id = str(uuid.uuid4())
        execution = None
        start_time = datetime.utcnow()

        if db:
            execution = SkillExecution(
                id=execution_id,
                skill_id=skill_id,
                user_id=user_id,
                agent_type=agent_type,
                task_id=task_id,
                status="running",
                input_params=json.dumps(params),
                started_at=start_time,
            )
            db.add(execution)
            await db.commit()

        # Emit start event
        yield events.stage(
            name=f"skill_{skill_id}",
            description=f"Executing {skill.metadata.name}",
            status="running",
        )

        logger.info(
            "skill_execution_started",
            skill_id=skill_id,
            execution_id=execution_id,
            user_id=user_id,
            task_id=task_id,
            params_keys=list(params.keys()) if params else [],
        )

        try:
            # Build initial state with execution context
            from app.agents.skills.skill_base import SkillState

            initial_state: SkillState = {
                "skill_id": skill_id,
                "input_params": params,
                "output": {},
                "error": None,
                "events": [],
                "iterations": 0,
                # Execution context - allows skills to share sandbox sessions with agents
                "user_id": user_id,
                "task_id": task_id,
            }

            # Add pending_events for skills that emit stage events during execution
            # This is not part of the base SkillState but used by specific skills like app_builder
            initial_state["pending_events"] = []  # type: ignore[typeddict-unknown-key]

            # Get compiled graph
            graph = skill.create_graph()

            # Execute with timeout using astream to capture intermediate events
            final_state = None
            emitted_event_count = 0  # Track how many events we've emitted
            try:
                async with asyncio.timeout(skill.metadata.max_execution_time_seconds):
                    # Use astream to get intermediate states and emit pending events
                    async for state_update in graph.astream(initial_state):
                        # state_update is a dict with node name as key
                        for node_name, node_state in state_update.items():
                            if not isinstance(node_state, dict):
                                continue

                            # Emit any pending events from this state
                            pending_events = node_state.get("pending_events", [])
                            new_events = pending_events[emitted_event_count:]
                            if new_events:
                                event_types = [e.get("type") for e in new_events if isinstance(e, dict)]
                                logger.info(
                                    "skill_executor_yielding_events",
                                    skill_id=skill_id,
                                    node_name=node_name,
                                    event_count=len(new_events),
                                    event_types=event_types,
                                )
                            for event in new_events:
                                yield event
                            emitted_event_count = len(pending_events)

                            # Update final state
                            if final_state is None:
                                final_state = dict(initial_state)
                            final_state.update(node_state)

            except TimeoutError:
                raise Exception(
                    f"Skill execution timed out after {skill.metadata.max_execution_time_seconds}s"
                )

            # Extract output
            output = final_state.get("output", {}) if final_state else {}

            # Update execution record
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            if execution and db:
                execution.status = "completed"
                execution.output_data = json.dumps(output)
                execution.completed_at = end_time
                execution.execution_time_ms = execution_time_ms
                await db.commit()

            logger.info(
                "skill_execution_completed",
                skill_id=skill_id,
                execution_id=execution_id,
                execution_time_ms=execution_time_ms,
            )

            # Emit completion stage
            yield events.stage(
                name=f"skill_{skill_id}",
                description=f"Completed {skill.metadata.name}",
                status="completed",
            )

            # Emit skill output event
            yield events.skill_output(skill_id=skill_id, output=output)

        except Exception as e:
            error_msg = str(e)
            logger.error(
                "skill_execution_failed",
                skill_id=skill_id,
                execution_id=execution_id,
                error=error_msg,
            )

            # Update execution record
            if execution and db:
                execution.status = "failed"
                execution.error = error_msg
                execution.completed_at = datetime.utcnow()
                await db.commit()

            # Emit error events
            yield events.stage(
                name=f"skill_{skill_id}",
                description=f"Failed {skill.metadata.name}",
                status="failed",
            )
            yield events.error(error_msg, name=skill.metadata.name)


# Global singleton
skill_executor = SkillExecutor()
