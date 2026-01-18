"""Supervisor/orchestrator for the multi-agent system with handoff support."""

from typing import Any, AsyncGenerator, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.routing import route_query
from app.agents.state import AgentType, SupervisorState
from app.agents.subagents.chat import chat_subgraph
from app.agents.subagents.code import code_subgraph
from app.agents.subagents.analytics import data_subgraph
from app.agents.subagents.research import research_subgraph
from app.agents.subagents.writing import writing_subgraph
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

# Streaming configuration - declarative mapping of which nodes should stream tokens
# Note: "generate" is disabled because it produces code that shouldn't be shown to users
# The code is still executed, and results are shown via "summarize" stage
STREAMING_CONFIG = {
    "write": True,
    "finalize": True,
    "summarize": True,
    "agent": True,
    "generate": False,  # Code generation - internal step, don't stream to chat
    "outline": False,   # Outline generation - internal step for writing agent
    "synthesize": True,
    "analyze": False,   # Analysis step - internal, only show final summary
    "router": False,
    "tools": False,
    "search_agent": False,
    "search_tools": False,
    # Research subgraph nodes
    "research_prep": False,
    "research_post": False,
    "init_config": False,
    "collect_sources": False,
}


async def router_node(state: SupervisorState) -> dict:
    """Route the query to the appropriate agent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with selected_agent and routing_reason
    """
    # Check if there's a pending handoff - use that instead of routing
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        target_agent = pending_handoff.get("target_agent", "chat")
        logger.info(
            "routing_from_handoff",
            target=target_agent,
            task=pending_handoff.get("task_description", "")[:50],
        )
        return {
            "selected_agent": target_agent,
            "routing_reason": f"Handoff from {pending_handoff.get('source_agent', 'unknown')}",
            "active_agent": target_agent,
            "delegated_task": pending_handoff.get("task_description"),
            "handoff_context": pending_handoff.get("context"),
            "pending_handoff": None,  # Clear the pending handoff
            "events": [
                {
                    "type": "handoff",
                    "source": pending_handoff.get("source_agent"),
                    "target": target_agent,
                    "task": pending_handoff.get("task_description"),
                }
            ],
        }

    result = await route_query(state)

    # Set active_agent from routing
    selected_agent = result.get("selected_agent", "chat")
    result["active_agent"] = selected_agent

    return result


async def chat_node(state: SupervisorState) -> dict:
    """Execute the chat subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with chat response, events, and potential handoff
    """
    # Build input state with handoff context if present
    input_state = {
        "query": _build_query_with_context(state),
        "messages": state.get("messages") or [],
        "user_id": state.get("user_id"),
        "attachment_ids": state.get("attachment_ids") or [],
        "image_attachments": state.get("image_attachments") or [],
        "system_prompt": state.get("system_prompt"),
        "provider": state.get("provider"),
        "model": state.get("model"),
        "shared_memory": state.get("shared_memory") or {},
    }

    # Invoke chat subgraph
    result = await chat_subgraph.ainvoke(input_state)

    output = {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff and _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        _update_handoff_history(output, state, handoff)

    return output


async def research_prep_node(state: SupervisorState) -> dict:
    """Prepare state for research subgraph execution.

    Transforms the query with handoff context and ensures all required
    fields are set before the research subgraph runs.

    Args:
        state: Current supervisor state

    Returns:
        Dict with transformed query and research configuration
    """
    depth = state.get("depth", ResearchDepth.FAST)
    scenario = state.get("scenario", ResearchScenario.ACADEMIC)

    # Transform query with handoff context
    transformed_query = _build_query_with_context(state)

    logger.info(
        "research_prep_started",
        depth=depth.value if isinstance(depth, ResearchDepth) else depth,
        scenario=scenario.value if isinstance(scenario, ResearchScenario) else scenario,
    )

    return {
        "query": transformed_query,
        "depth": depth,
        "scenario": scenario,
    }


async def research_post_node(state: SupervisorState) -> dict:
    """Post-process research subgraph results.

    Updates shared memory with research findings and validates handoffs.

    Args:
        state: Current supervisor state with research results

    Returns:
        Dict with shared memory updates and validated handoff
    """
    output = {}

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

    # Validate and propagate handoff
    handoff = state.get("pending_handoff")
    if handoff and _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        _update_handoff_history(output, state, handoff)

    logger.info(
        "research_post_completed",
        has_findings=bool(shared_memory.get("research_findings")),
        has_handoff=bool(handoff),
    )

    return output


async def code_node(state: SupervisorState) -> dict:
    """Execute the code subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with code results, events, and potential handoff
    """
    input_state = {
        "query": _build_query_with_context(state),
        "messages": state.get("messages") or [],
        "user_id": state.get("user_id"),
        "attachment_ids": state.get("attachment_ids") or [],
        "provider": state.get("provider"),
        "model": state.get("model"),
        "shared_memory": state.get("shared_memory") or {},
    }

    result = await code_subgraph.ainvoke(input_state)

    output = {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }

    # Update shared memory with code artifacts
    shared_memory = state.get("shared_memory") or {}
    if result.get("code"):
        shared_memory["generated_code"] = result.get("code", "")
        shared_memory["code_language"] = result.get("language", "python")
    if result.get("execution_result"):
        shared_memory["execution_results"] = result.get("execution_result", "")
    output["shared_memory"] = shared_memory

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff and _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        _update_handoff_history(output, state, handoff)

    return output


async def writing_node(state: SupervisorState) -> dict:
    """Execute the writing subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with writing results, events, and potential handoff
    """
    input_state = {
        "query": _build_query_with_context(state),
        "messages": state.get("messages") or [],
        "user_id": state.get("user_id"),
        "attachment_ids": state.get("attachment_ids") or [],
        "image_attachments": state.get("image_attachments") or [],
        "provider": state.get("provider"),
        "model": state.get("model"),
        "shared_memory": state.get("shared_memory") or {},
    }

    result = await writing_subgraph.ainvoke(input_state)

    output = {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }

    # Update shared memory with writing artifacts
    shared_memory = state.get("shared_memory") or {}
    if result.get("outline"):
        shared_memory["writing_outline"] = result.get("outline", "")
    if result.get("draft"):
        shared_memory["writing_draft"] = result.get("draft", "")
    output["shared_memory"] = shared_memory

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff and _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        _update_handoff_history(output, state, handoff)

    return output


async def data_node(state: SupervisorState) -> dict:
    """Execute the data analysis subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with data analysis results, events, and potential handoff
    """
    logger.info("data_analysis_started", query=state.get("query", "")[:50])

    input_state = {
        "query": _build_query_with_context(state),
        "messages": state.get("messages") or [],
        "data_source": state.get("data_source", ""),
        "attachment_ids": state.get("attachment_ids") or [],
        "user_id": state.get("user_id"),
        "provider": state.get("provider"),
        "model": state.get("model"),
        "shared_memory": state.get("shared_memory") or {},
    }

    result = await data_subgraph.ainvoke(input_state)

    output = {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }

    # Update shared memory with data analysis artifacts
    shared_memory = state.get("shared_memory") or {}
    if result.get("analysis_plan"):
        shared_memory["data_analysis_plan"] = result.get("analysis_plan", "")
    if result.get("visualizations"):
        shared_memory["data_visualizations"] = result.get("visualizations", [])
    output["shared_memory"] = shared_memory

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff and _can_handoff(state, handoff.get("target_agent", "")):
        output["pending_handoff"] = handoff
        output["handoff_count"] = state.get("handoff_count", 0) + 1
        _update_handoff_history(output, state, handoff)

    return output


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
    graph.add_node("code", code_node)
    graph.add_node("writing", writing_node)
    graph.add_node("data", data_node)

    # Research agent uses prep -> subgraph -> post pattern for real-time streaming
    # Adding the subgraph directly (not wrapped) allows internal events to propagate
    graph.add_node("research_prep", research_prep_node)
    graph.add_node("research", research_subgraph)  # Subgraph directly as node
    graph.add_node("research_post", research_post_node)

    # Set entry point
    graph.set_entry_point("router")

    # Conditional edges from router to appropriate agent
    graph.add_conditional_edges(
        "router",
        select_agent,
        {
            AgentType.CHAT.value: "chat",
            AgentType.RESEARCH.value: "research_prep",  # Route to prep node
            AgentType.CODE.value: "code",
            AgentType.WRITING.value: "writing",
            AgentType.DATA.value: "data",
        },
    )

    # Research flow: prep -> subgraph -> post
    graph.add_edge("research_prep", "research")
    graph.add_edge("research", "research_post")

    # After each agent (or research_post), check for handoff or end
    for agent in ["chat", "research_post", "code", "writing", "data"]:
        graph.add_conditional_edges(
            agent,
            check_for_handoff,
            {
                "router": "router",
                END: END,
            },
        )

    return graph.compile(checkpointer=checkpointer)


# Create default graph with memory checkpointer
_checkpointer = MemorySaver()
supervisor_graph = create_supervisor_graph(checkpointer=_checkpointer)


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
            mode: Optional explicit agent mode (chat, research, code, writing, data)
            task_id: Optional task ID for tracking
            user_id: Optional user ID
            messages: Optional chat history
            **kwargs: Additional parameters passed to subagents

        Yields:
            Event dictionaries for streaming to clients
        """
        import uuid

        # Build initial state
        initial_state: SupervisorState = {
            "query": query,
            "mode": mode,
            "task_id": task_id,
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

        # Create config with thread_id for checkpointing
        thread_id = task_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        logger.info(
            "supervisor_run_started",
            query=query[:50],
            mode=mode,
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

        # Track node path for nested subgraphs
        node_path = []
        current_content_node = None

        emitted_tool_call_ids = set()
        emitted_stage_keys = set()
        streamed_tokens = False
        # Track tool calls by ID for matching with results
        pending_tool_calls: dict[str, dict] = {}

        try:
            # Stream events from the graph
            async for event in self.graph.astream_events(
                initial_state,
                config=config,
                version="v2",
            ):
                # Ensure event is a dictionary before processing
                if not isinstance(event, dict):
                    continue

                event_type = event.get("event")
                node_name = event.get("name", "")

                # Track node path for nested subgraphs
                if event_type == "on_chain_start":
                    node_path.append(node_name)

                    # Track content-generating nodes at any level
                    content_nodes = list(STREAMING_CONFIG.keys())
                    if any(node in node_name for node in content_nodes if STREAMING_CONFIG.get(node)):
                        current_content_node = node_name

                    # Provide immediate feedback for agent steps
                    # Helper to emit running stage only once
                    def emit_stage_running(name: str, description: str):
                        stage_key = f"{name}:running"
                        if stage_key not in emitted_stage_keys:
                            emitted_stage_keys.add(stage_key)
                            return {"type": "stage", "name": name, "description": description, "status": "running"}
                        return None

                    # Data analysis stages
                    if node_name == "plan":
                        stage_event = emit_stage_running("plan", "Planning analysis...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "generate":
                        stage_event = emit_stage_running("generate", "Generating code...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "execute":
                        stage_event = emit_stage_running("execute", "Executing code...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "summarize":
                        stage_event = emit_stage_running("summarize", "Summarizing results...")
                        if stage_event:
                            yield stage_event
                    # Writing agent stages
                    elif node_name == "analyze":
                        stage_event = emit_stage_running("analyze", "Analyzing task...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "outline":
                        stage_event = emit_stage_running("outline", "Creating outline...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "write":
                        stage_event = emit_stage_running("write", "Writing content...")
                        if stage_event:
                            yield stage_event
                    elif node_name == "finalize":
                        stage_event = emit_stage_running("finalize", "Finalizing response...")
                        if stage_event:
                            yield stage_event
                    # Research agent stages (check with endswith for namespaced subgraph nodes)
                    # When subgraph is added as a node, internal nodes are named like "research:init_config"
                    elif node_name.endswith("init_config"):
                        stage_event = emit_stage_running("config", "Initializing research...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("search_agent"):
                        stage_event = emit_stage_running("search", "Searching for sources...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("search_tools"):
                        stage_event = emit_stage_running("search_tools", "Executing search...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("collect_sources"):
                        stage_event = emit_stage_running("collect", "Collecting sources...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("synthesize"):
                        stage_event = emit_stage_running("synthesize", "Synthesizing findings...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("analyze") and any("research" in p for p in node_path):
                        # Research analyze stage (distinguish from writing analyze)
                        stage_event = emit_stage_running("analyze", "Analyzing sources...")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("write") and any("research" in p for p in node_path):
                        # Research write stage
                        stage_event = emit_stage_running("report", "Writing research report...")
                        if stage_event:
                            yield stage_event

                elif event_type == "on_chain_end":
                    # Update node path
                    if node_path and node_path[-1] == node_name:
                        node_path.pop()
                    if node_name == current_content_node:
                        current_content_node = None

                    # Mark thinking stage as completed when we start getting results
                    if node_name == "router" and "thinking" not in emitted_stage_keys:
                        emitted_stage_keys.add("thinking")
                        yield {
                            "type": "stage",
                            "name": "thinking",
                            "description": "Request processed",
                            "status": "completed",
                        }

                    # Emit completion events for agent stages
                    # Helper to emit stage completion if not already emitted
                    def emit_stage_completion(name: str, description: str):
                        stage_key = f"{name}:completed"
                        if stage_key not in emitted_stage_keys:
                            emitted_stage_keys.add(stage_key)
                            return {"type": "stage", "name": name, "description": description, "status": "completed"}
                        return None

                    # Data analysis stages
                    if node_name == "plan":
                        stage_event = emit_stage_completion("plan", "Analysis planned")
                        if stage_event:
                            yield stage_event
                    elif node_name == "generate":
                        stage_event = emit_stage_completion("generate", "Code generated")
                        if stage_event:
                            yield stage_event
                    elif node_name == "execute":
                        stage_event = emit_stage_completion("execute", "Code executed")
                        if stage_event:
                            yield stage_event
                    elif node_name == "summarize":
                        stage_event = emit_stage_completion("summarize", "Results summarized")
                        if stage_event:
                            yield stage_event
                    # Writing agent stages
                    elif node_name == "analyze":
                        stage_event = emit_stage_completion("analyze", "Task analyzed")
                        if stage_event:
                            yield stage_event
                    elif node_name == "outline":
                        stage_event = emit_stage_completion("outline", "Outline created")
                        if stage_event:
                            yield stage_event
                    elif node_name == "write":
                        stage_event = emit_stage_completion("write", "Content written")
                        if stage_event:
                            yield stage_event
                    elif node_name == "finalize":
                        stage_event = emit_stage_completion("finalize", "Response finalized")
                        if stage_event:
                            yield stage_event
                    # Research agent stages (check with endswith for namespaced subgraph nodes)
                    elif node_name.endswith("init_config"):
                        stage_event = emit_stage_completion("config", "Research configured")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("search_agent"):
                        # Don't mark search as complete here - it loops
                        pass
                    elif node_name.endswith("search_tools"):
                        stage_event = emit_stage_completion("search_tools", "Search executed")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("collect_sources"):
                        stage_event = emit_stage_completion("search", "Sources collected")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("synthesize"):
                        stage_event = emit_stage_completion("synthesize", "Findings synthesized")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("analyze") and any("research" in p for p in node_path):
                        stage_event = emit_stage_completion("analyze", "Sources analyzed")
                        if stage_event:
                            yield stage_event
                    elif node_name.endswith("write") and any("research" in p for p in node_path):
                        stage_event = emit_stage_completion("report", "Research report complete")
                        if stage_event:
                            yield stage_event

                    # Extract events from output (including routing and handoff events)
                    event_data = event.get("data") or {}
                    output = event_data.get("output") or {}
                    if isinstance(output, dict):
                        events_list = output.get("events", [])
                        if isinstance(events_list, list):
                            for e in events_list:
                                if isinstance(e, dict):
                                    # Skip token events if we already streamed them in real-time
                                    if e.get("type") == "token" and streamed_tokens:
                                        continue
                                    # Deduplicate stage events
                                    if e.get("type") == "stage":
                                        stage_key = f"{e.get('name')}:{e.get('status')}"
                                        if stage_key in emitted_stage_keys:
                                            continue
                                        emitted_stage_keys.add(stage_key)
                                    # Log visualization events for debugging
                                    if e.get("type") == "visualization":
                                        logger.info(
                                            "yielding_visualization_event",
                                            node_name=node_name,
                                            has_data=bool(e.get("data")),
                                            data_length=len(e.get("data", "")) if e.get("data") else 0,
                                        )
                                    yield e

                # Handle streaming tokens from LLM in real-time
                elif event_type == "on_chat_model_stream":
                    # Build node path string for checking
                    node_path_str = "/".join(node_path)

                    # Emit tool calls immediately if present in the chunk
                    chunk = (event.get("data") or {}).get("chunk")
                    if chunk and getattr(chunk, "tool_calls", None):
                        for tool_call in chunk.tool_calls:
                            # Skip None or non-dict tool calls
                            if not tool_call or not isinstance(tool_call, dict):
                                continue
                            tool_id = tool_call.get("id") or tool_call.get("tool_call_id")
                            # Generate a unique ID if not provided
                            if not tool_id:
                                tool_id = str(uuid.uuid4())
                            if tool_id in emitted_tool_call_ids:
                                continue
                            emitted_tool_call_ids.add(tool_id)
                            tool_name = tool_call.get("name") or tool_call.get("tool")
                            tool_args = tool_call.get("args") or {}
                            # Track pending tool call for matching with result
                            pending_tool_calls[tool_id] = {
                                "tool": tool_name,
                                "args": tool_args,
                            }
                            yield {
                                "type": "tool_call",
                                "tool": tool_name,
                                "args": tool_args,
                                "id": tool_id,
                            }

                    # Use declarative config to determine streaming
                    should_stream = any(
                        node in node_path_str
                        for node, enabled in STREAMING_CONFIG.items()
                        if enabled
                    )

                    if should_stream:
                        chunk = (event.get("data") or {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            from app.services.llm import extract_text_from_content
                            content = extract_text_from_content(chunk.content)
                            if content:
                                streamed_tokens = True
                                yield {"type": "token", "content": content}

                # Handle tool execution start
                elif event_type == "on_tool_start":
                    # Tool is starting execution - we already emitted tool_call
                    # Get tool call ID for tracking
                    run_id = event.get("run_id", "")
                    tool_name = event.get("name", "")
                    tool_input = (event.get("data") or {}).get("input") or {}

                    # Generate ID if we don't have one
                    tool_call_id = None
                    if isinstance(tool_input, dict):
                        tool_call_id = tool_input.get("tool_call_id")

                    # Track the run_id to tool_call_id mapping for result matching
                    if run_id and not tool_call_id:
                        # Use run_id as fallback ID
                        tool_call_id = str(run_id)

                    if tool_name and tool_call_id and tool_call_id not in emitted_tool_call_ids:
                        emitted_tool_call_ids.add(tool_call_id)
                        pending_tool_calls[tool_call_id] = {
                            "tool": tool_name,
                            "run_id": run_id,
                        }
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_input if isinstance(tool_input, dict) else {},
                            "id": tool_call_id,
                        }

                # Handle tool execution end - emit tool_result event
                elif event_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    tool_name = event.get("name", "")
                    output = (event.get("data") or {}).get("output", "")

                    # Find matching tool call by run_id
                    tool_call_id = None
                    for tid, info in pending_tool_calls.items():
                        if info.get("run_id") == run_id or info.get("tool") == tool_name:
                            tool_call_id = tid
                            break

                    # If no match found, use run_id as the ID
                    if not tool_call_id:
                        tool_call_id = str(run_id) if run_id else str(uuid.uuid4())

                    # Emit tool_result event
                    content = str(output)[:500] if output else ""
                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "content": content,
                        "id": tool_call_id,
                    }

                    # Remove from pending
                    pending_tool_calls.pop(tool_call_id, None)

                # Handle errors from subagents
                elif event_type == "on_chain_error":
                    error = (event.get("data") or {}).get("error")
                    if error:
                        yield {
                            "type": "error",
                            "error": str(error),
                            "node": node_name,
                        }
                        logger.error(
                            "subagent_error",
                            node=node_name,
                            error=str(error),
                            thread_id=thread_id,
                        )

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

        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        result = await self.graph.ainvoke(initial_state, config=config)
        return result


# Global instance for convenience
agent_supervisor = AgentSupervisor()
