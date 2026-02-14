"""Supervisor/orchestrator for the multi-agent system with handoff support."""

import asyncio
from typing import Any, AsyncGenerator, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.routing import route_query
from app.agents.state import (
    AgentType,
    ChatOutput,
    DataOutput,
    ErrorOutput,
    ResearchPostOutput,
    ResearchPrepOutput,
    RouterOutput,
    SupervisorState,
)
from app.agents.subagents.chat import chat_subgraph
from app.agents.subagents.data import data_subgraph
from app.agents.subagents.research import research_subgraph
from app.agents.tools.handoff import (
    HANDOFF_MATRIX,
    MAX_HANDOFFS,
    HandoffInfo,
    build_query_with_context,
    can_handoff,
    update_handoff_history,
)
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario

logger = get_logger(__name__)

# Default timeout for subgraph invocations (in seconds)
DEFAULT_SUBGRAPH_TIMEOUT = 300  # 5 minutes

# Streaming configuration - declarative mapping of which nodes should stream tokens
# Note: "generate" is disabled because it produces code that shouldn't be shown to users
# The code is still executed, and results are shown via "summarize" stage



async def router_node(state: SupervisorState) -> RouterOutput:
    """Route the query to the appropriate agent.

    Includes input validation and error handling.

    Args:
        state: Current supervisor state

    Returns:
        RouterOutput with selected_agent and routing_reason
    """
    try:
        # Input validation
        query = (state.get("query") or "").strip()
        if not query:
            logger.warning("router_empty_query")
            return RouterOutput(
                selected_agent=AgentType.CHAT.value,
                routing_reason="Empty query - defaulting to chat",
                routing_confidence=1.0,
                active_agent=AgentType.CHAT.value,
                events=[
                    {
                        "type": "validation",
                        "warning": "Empty query received",
                    }
                ],
            )

        # Check if there's a pending handoff - use that instead of routing
        pending_handoff = state.get("pending_handoff")
        if pending_handoff:
            target_agent = pending_handoff.get("target_agent", "chat")
            logger.info(
                "routing_from_handoff",
                target=target_agent,
                task=pending_handoff.get("task_description", "")[:50],
            )
            return RouterOutput(
                selected_agent=target_agent,
                routing_reason=f"Handoff from {pending_handoff.get('source_agent', 'unknown')}",
                active_agent=target_agent,
                delegated_task=pending_handoff.get("task_description"),
                handoff_context=pending_handoff.get("context"),
                pending_handoff=None,  # Clear the pending handoff
                events=[
                    {
                        "type": "handoff",
                        "source": pending_handoff.get("source_agent"),
                        "target": target_agent,
                        "task": pending_handoff.get("task_description"),
                    }
                ],
            )

        result = await route_query(state)

        # Set active_agent from routing
        selected_agent = result.get("selected_agent", "chat")
        result["active_agent"] = selected_agent

        return RouterOutput(**result)

    except Exception as e:
        logger.error("router_node_failed", error=str(e))
        # Default to chat on routing failure
        return RouterOutput(
            selected_agent=AgentType.CHAT.value,
            routing_reason=f"Routing error: {str(e)}",
            routing_confidence=0.0,
            active_agent=AgentType.CHAT.value,
            events=[
                {
                    "type": "error",
                    "node": "router",
                    "error": str(e),
                }
            ],
        )


async def chat_node(state: SupervisorState) -> ChatOutput | ErrorOutput:
    """Execute the chat subagent.

    Args:
        state: Current supervisor state

    Returns:
        ChatOutput with response, events, and potential handoff
    """
    try:
        # Build input state with handoff context if present
        # Include task_id so browser tools use the same sandbox session as the stream viewer
        input_state = {
            "query": _build_query_with_context(state),
            "mode": state.get("mode"),
            "messages": state.get("messages") or [],
            "user_id": state.get("user_id"),
            "task_id": state.get("task_id"),
            "attachment_ids": state.get("attachment_ids") or [],
            "image_attachments": state.get("image_attachments") or [],
            "system_prompt": state.get("system_prompt"),
            "provider": state.get("provider"),
            "model": state.get("model"),
            "shared_memory": state.get("shared_memory") or {},
        }

        # Invoke chat subgraph with timeout
        from app.config import settings

        timeout = getattr(settings, "subgraph_timeout", DEFAULT_SUBGRAPH_TIMEOUT)
        async with asyncio.timeout(timeout):
            result = await chat_subgraph.ainvoke(input_state)

        output: ChatOutput = {
            "response": result.get("response", ""),
            "events": result.get("events", []),
        }

        _process_handoff(output, state, result.get("pending_handoff"), "chat")

        return output

    except asyncio.TimeoutError:
        logger.error("chat_node_timeout", task_id=state.get("task_id"))
        return ErrorOutput(
            response="I'm sorry, the request took too long to process. Please try again with a simpler query.",
            events=[{"type": "error", "node": "chat", "error": "Timeout"}],
            has_error=True,
        )
    except Exception as e:
        logger.error("chat_node_failed", error=str(e), task_id=state.get("task_id"))
        return ErrorOutput(
            response=f"I encountered an error while processing your request: {str(e)}",
            events=[{"type": "error", "node": "chat", "error": str(e)}],
            has_error=True,
        )


async def research_prep_node(state: SupervisorState) -> ResearchPrepOutput | ErrorOutput:
    """Prepare state for research subgraph execution.

    Transforms the query with handoff context and ensures all required
    fields are set before the research subgraph runs.

    Args:
        state: Current supervisor state

    Returns:
        ResearchPrepOutput with transformed query and research configuration
    """
    try:
        depth = state.get("depth", ResearchDepth.FAST)
        scenario = state.get("scenario", ResearchScenario.ACADEMIC)

        # Transform query with handoff context
        transformed_query = _build_query_with_context(state)

        logger.info(
            "research_prep_started",
            depth=depth.value if isinstance(depth, ResearchDepth) else depth,
            scenario=scenario.value if isinstance(scenario, ResearchScenario) else scenario,
        )

        return ResearchPrepOutput(
            query=transformed_query,
            depth=depth,
            scenario=scenario,
        )

    except Exception as e:
        logger.error("research_prep_failed", error=str(e))
        return ErrorOutput(
            response=f"Failed to prepare research: {str(e)}",
            events=[{"type": "error", "node": "research_prep", "error": str(e)}],
            has_error=True,
        )


async def research_post_node(state: SupervisorState) -> ResearchPostOutput | ErrorOutput:
    """Post-process research subgraph results.

    Updates shared memory with research findings and validates handoffs.

    Args:
        state: Current supervisor state with research results

    Returns:
        ResearchPostOutput with shared memory updates and validated handoff
    """
    try:
        output: ResearchPostOutput = {}

        # Update shared memory with research findings
        shared_memory = dict(state.get("shared_memory") or {})
        if state.get("analysis"):
            shared_memory["research_findings"] = state.get("analysis", "")
        if state.get("sources"):
            sources = state.get("sources", [])
            shared_memory["research_sources"] = [
                {"title": s.title, "url": s.url, "snippet": s.snippet}
                for s in sources
                if hasattr(s, "title")  # Check if it's a SearchResult object
            ]
        output["shared_memory"] = shared_memory

        _process_handoff(output, state, state.get("pending_handoff"), "research")

        logger.info(
            "research_post_completed",
            has_findings=bool(shared_memory.get("research_findings")),
            has_handoff=bool(handoff),
        )

        return output

    except Exception as e:
        logger.error("research_post_failed", error=str(e))
        return ErrorOutput(
            response=f"Failed to process research results: {str(e)}",
            events=[{"type": "error", "node": "research_post", "error": str(e)}],
            has_error=True,
        )


async def data_node(state: SupervisorState) -> DataOutput | ErrorOutput:
    """Execute the data analysis subagent.

    Args:
        state: Current supervisor state

    Returns:
        DataOutput with analysis results, events, and potential handoff
    """
    try:
        logger.info("data_analysis_started", query=state.get("query", "")[:50])

        input_state = {
            "query": _build_query_with_context(state),
            "messages": state.get("messages") or [],
            "data_source": state.get("data_source", ""),
            "attachment_ids": state.get("attachment_ids") or [],
            "user_id": state.get("user_id"),
            "task_id": state.get("task_id"),
            "provider": state.get("provider"),
            "model": state.get("model"),
            "shared_memory": state.get("shared_memory") or {},
        }

        # Invoke data subgraph with timeout
        from app.config import settings

        timeout = getattr(settings, "subgraph_timeout", DEFAULT_SUBGRAPH_TIMEOUT)
        async with asyncio.timeout(timeout):
            result = await data_subgraph.ainvoke(input_state)

        output: DataOutput = {
            "response": result.get("response", ""),
            "events": result.get("events", []),
        }

        # Update shared memory with data analysis artifacts
        shared_memory = dict(state.get("shared_memory") or {})
        if result.get("analysis_plan"):
            shared_memory["data_analysis_plan"] = result.get("analysis_plan", "")
        if result.get("images"):
            shared_memory["data_images"] = result.get("images", [])
        output["shared_memory"] = shared_memory

        _process_handoff(output, state, result.get("pending_handoff"), "data")

        return output

    except asyncio.TimeoutError:
        logger.error("data_node_timeout", task_id=state.get("task_id"))
        return ErrorOutput(
            response="I'm sorry, the data analysis took too long. Please try with a smaller dataset or simpler query.",
            events=[{"type": "error", "node": "data", "error": "Timeout"}],
            has_error=True,
        )
    except Exception as e:
        logger.error("data_node_failed", error=str(e), task_id=state.get("task_id"))
        return ErrorOutput(
            response=f"I encountered an error during data analysis: {str(e)}",
            events=[{"type": "error", "node": "data", "error": str(e)}],
            has_error=True,
        )


def select_agent(state: SupervisorState) -> str:
    """Select which agent to route to based on state.

    Args:
        state: Current supervisor state with selected_agent

    Returns:
        Node name to route to
    """
    selected = state.get("selected_agent", AgentType.CHAT.value)
    return selected


def check_for_handoff(state: SupervisorState) -> Literal["router", "__end__"]:
    """Check if there's a pending handoff that needs processing.

    Args:
        state: Current supervisor state

    Returns:
        "router" if handoff pending, "__end__" otherwise
    """
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        target = pending_handoff.get("target_agent", "")
        handoff_count = state.get("handoff_count", 0)

        # Check handoff limits
        if handoff_count >= MAX_HANDOFFS:
            logger.warning(
                "max_handoffs_reached",
                count=handoff_count,
                max=MAX_HANDOFFS,
            )
            return END

        # Validate handoff target
        current_agent = state.get("active_agent", "chat")
        allowed_targets = HANDOFF_MATRIX.get(current_agent, [])
        if target not in allowed_targets:
            logger.warning(
                "invalid_handoff_target",
                current=current_agent,
                target=target,
                allowed=allowed_targets,
            )
            return END

        logger.info(
            "handoff_detected",
            from_agent=current_agent,
            to_agent=target,
            handoff_count=handoff_count,
        )
        return "router"

    return END


def _build_query_with_context(state: SupervisorState) -> str:
    """Build query string with handoff context if present.

    Thin wrapper that extracts state fields and delegates to handoff module.

    Args:
        state: Current supervisor state

    Returns:
        Query string with optional context
    """
    return build_query_with_context(
        query=state.get("query") or "",
        delegated_task=state.get("delegated_task"),
        handoff_context=state.get("handoff_context"),
        shared_memory=state.get("shared_memory"),
    )


def _can_handoff(state: SupervisorState, target_agent: str) -> bool:
    """Check if a handoff to the target agent is allowed.

    Thin wrapper that extracts state fields and delegates to handoff module.

    Args:
        state: Current supervisor state
        target_agent: Target agent for handoff

    Returns:
        True if handoff is allowed
    """
    return can_handoff(
        current_agent=state.get("active_agent") or "chat",
        target_agent=target_agent,
        handoff_count=state.get("handoff_count", 0),
        handoff_history=state.get("handoff_history"),
    )


def _process_handoff(
    output: dict,
    state: SupervisorState,
    handoff: dict | None,
    agent_name: str,
) -> None:
    """Validate and apply handoff to output dict, or set fallback response.

    Args:
        output: Output dict to update in-place
        state: Current supervisor state
        handoff: Handoff info dict from agent result, or None
        agent_name: Name of the current agent (for logging)
    """
    if not handoff:
        return

    if _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        output["handoff_history"] = update_handoff_history(
            history=list(state.get("handoff_history") or []),
            source_agent=state.get("active_agent") or "chat",
            handoff=handoff,
        )
    else:
        logger.warning(
            f"{agent_name}_handoff_blocked",
            target=handoff.get("target_agent", ""),
        )
        if not output.get("response"):
            output["response"] = (
                "I couldn't hand off that request, so I'm continuing here. "
                "Please share more details or rephrase."
            )


def _update_handoff_history(
    output: dict,
    state: SupervisorState,
    handoff: HandoffInfo,
) -> None:
    """Update handoff history in output.

    Thin wrapper that extracts state fields and delegates to handoff module.

    Args:
        output: Output dict to update
        state: Current supervisor state
        handoff: Handoff info to add
    """
    output["handoff_history"] = update_handoff_history(
        history=list(state.get("handoff_history") or []),
        source_agent=state.get("active_agent") or "chat",
        handoff=handoff,
    )


def create_supervisor_graph(checkpointer=None):
    """Create the supervisor graph that orchestrates subagents with handoff support.

    The research agent uses a special pattern with prep/subgraph/post nodes
    to enable real-time event streaming from the research subgraph's internal
    nodes (init_config, search_agent, search_tools, etc.) to the supervisor's
    astream_events output. This allows the sidebar to show real-time progress.

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled supervisor graph
    """
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("chat", chat_node)
    graph.add_node("data", data_node)

    # Research agent uses prep -> subgraph -> post pattern for real-time streaming
    # Adding the subgraph directly (not wrapped) allows internal events to propagate
    graph.add_node("research_prep", research_prep_node)
    graph.add_node("research", research_subgraph)  # Subgraph directly as node
    graph.add_node("research_post", research_post_node)

    # Set entry point
    graph.set_entry_point("router")

    # Conditional edges from router to appropriate agent
    # Note: Deprecated agent type (image) is automatically
    # mapped to CHAT in routing.py via AGENT_NAME_MAP before reaching here
    graph.add_conditional_edges(
        "router",
        select_agent,
        {
            AgentType.CHAT.value: "chat",
            AgentType.RESEARCH.value: "research_prep",  # Route to prep node
            AgentType.DATA.value: "data",
        },
    )

    # Research flow: prep -> subgraph -> post
    graph.add_edge("research_prep", "research")
    graph.add_edge("research", "research_post")

    # After each agent (or research_post), check for handoff or end
    for agent in ["chat", "research_post", "data"]:
        graph.add_conditional_edges(
            agent,
            check_for_handoff,
            {
                "router": "router",
                END: END,
            },
        )

    return graph.compile(checkpointer=checkpointer)


# =============================================================================
# Factory Functions (for better testability and thread safety)
# =============================================================================


def get_supervisor_graph(checkpointer=None):
    """Factory function to create supervisor graph with optional checkpointer.

    Use this function instead of the global singleton for better testability
    and multi-tenant scenarios.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     If None, creates a new MemorySaver.

    Returns:
        Compiled supervisor graph
    """
    if checkpointer is None:
        checkpointer = MemorySaver()
    return create_supervisor_graph(checkpointer=checkpointer)


# Lazy-initialized global graph (use get_supervisor_graph() for new instances)
# Note: For testing, use get_supervisor_graph() with a mock checkpointer instead
_default_checkpointer = MemorySaver()
supervisor_graph = create_supervisor_graph(checkpointer=_default_checkpointer)


class AgentSupervisor:
    """High-level wrapper for the supervisor graph.

    Provides a clean interface for running the multi-agent system
    with support for both synchronous and streaming execution.
    """

    def __init__(self, checkpointer=None):
        """Initialize the supervisor.

        Args:
            checkpointer: Optional checkpointer for state persistence
        """
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = create_supervisor_graph(checkpointer=self.checkpointer)

    async def run(
        self,
        query: str,
        mode: str | None = None,
        task_id: str | None = None,
        user_id: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        **kwargs,
    ) -> AsyncGenerator[dict, None]:
        """Run the appropriate agent and yield events.

        This method maintains backward compatibility with the existing
        research agent interface while supporting the new multi-agent system.

        Args:
            query: User query to process
            mode: Optional explicit agent mode (chat, research, app, data, image)
            task_id: Optional task ID for tracking
            user_id: Optional user ID
            messages: Optional chat history
            **kwargs: Additional parameters passed to subagents

        Yields:
            Event dictionaries for streaming to clients
        """
        import uuid
        from app.agents.stream_processor import StreamProcessor

        effective_task_id = task_id or str(uuid.uuid4())
        # Preserve original mode for subagents (important for image/app modes)
        # The router will handle normalization for routing decisions
        original_mode = mode.lower() if isinstance(mode, str) else mode

        # Build initial state
        initial_state: SupervisorState = {
            "query": query,
            "mode": original_mode,  # Preserve original mode (e.g., "image", "app")
            "task_id": effective_task_id,
            "user_id": user_id,
            "messages": messages or [],
            "events": [],
            "handoff_count": 0,
            "handoff_history": [],
            "shared_memory": {},
        }

        # Add any extra kwargs (like depth, scenario for research)
        for key, value in kwargs.items():
            initial_state[key] = value

        # Create config with unique run_id for each request
        # Using a unique ID per request prevents checkpoint state (like events) from carrying over
        # Conversation history is passed explicitly via messages, not through checkpointing
        from app.config import settings
        import uuid

        run_id = str(uuid.uuid4())  # Unique per request, not conversation
        thread_id = effective_task_id  # Still log with conversation ID
        config = {
            "configurable": {"thread_id": run_id},  # Use unique run_id for checkpointing
            "recursion_limit": settings.langgraph_recursion_limit,
        }

        logger.info(
            "supervisor_run_started",
            query=query[:50],
            mode=original_mode,
            thread_id=thread_id,
            depth=initial_state.get("depth"),
            scenario=initial_state.get("scenario"),
        )

        # Emit initial thinking stage
        yield {
            "type": "stage",
            "name": "thinking",
            "description": "Processing your request...",
            "status": "running",
        }

        # Initialize stream processor
        processor = StreamProcessor(
            user_id=user_id,
            task_id=effective_task_id,
            thread_id=thread_id,
        )

        try:
            # Stream events from the graph
            async for event in self.graph.astream_events(
                initial_state,
                config=config,
                version="v2",
            ):
                if not isinstance(event, dict):
                    continue

                async for processed_event in processor.process_event(event):
                    yield processed_event

            # Emit completion event
            yield {"type": "complete"}

            logger.info("supervisor_run_completed", thread_id=thread_id)

        except Exception as e:
            logger.error("supervisor_run_failed", error=str(e), thread_id=thread_id)
            yield {"type": "error", "error": str(e)}

    async def invoke(
        self,
        query: str,
        mode: str | None = None,
        **kwargs,
    ) -> dict:
        """Run the agent and return final result (non-streaming).

        Args:
            query: User query to process
            mode: Optional explicit agent mode
            **kwargs: Additional parameters

        Returns:
            Final result dictionary with response
        """
        import uuid

        initial_state: SupervisorState = {
            "query": query,
            "mode": mode,
            "events": [],
            "handoff_count": 0,
            "handoff_history": [],
            "shared_memory": {},
            **kwargs,
        }

        from app.config import settings

        config = {
            "configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": settings.langgraph_recursion_limit,
        }

        result = await self.graph.ainvoke(initial_state, config=config)
        return result


# Global instance for convenience
agent_supervisor = AgentSupervisor()
