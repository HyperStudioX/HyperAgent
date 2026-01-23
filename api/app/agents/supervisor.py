"""Supervisor/orchestrator for the multi-agent system with handoff support."""

from typing import Any, AsyncGenerator, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.routing import route_query
from app.agents.state import AgentType, SupervisorState
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

# Streaming configuration - declarative mapping of which nodes should stream tokens
# Note: "generate" is disabled because it produces code that shouldn't be shown to users
# The code is still executed, and results are shown via "summarize" stage
STREAMING_CONFIG = {
    "summarize": True,
    "agent": True,
    "generate": False,  # Code generation - internal step, don't stream to chat
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


def _node_matches_streaming(node_name: str, node_key: str) -> bool:
    """Check if a node name matches a streaming config key."""
    return node_name == node_key or node_name.endswith(f":{node_key}")


def _path_has_streamable_node(node_path_str: str) -> bool:
    """Check if any node in the current path should stream."""
    if not node_path_str:
        return False
    for segment in node_path_str.split("/"):
        for node, enabled in STREAMING_CONFIG.items():
            if enabled and _node_matches_streaming(segment, node):
                return True
    return False


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

    # Invoke chat subgraph
    result = await chat_subgraph.ainvoke(input_state)

    output = {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff:
        if _can_handoff(state, handoff.get("target_agent", "")):
            output["pending_handoff"] = handoff
            output["handoff_count"] = state.get("handoff_count", 0) + 1
            _update_handoff_history(output, state, handoff)
        else:
            logger.warning(
                "chat_handoff_blocked",
                target=handoff.get("target_agent", ""),
            )
            if not output.get("response"):
                output["response"] = (
                    "I couldn't hand off that request, so I'm continuing here. "
                    "Please share more details or rephrase."
                )

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
    if handoff:
        if _can_handoff(state, handoff.get("target_agent", "")):
            output["pending_handoff"] = handoff
            output["handoff_count"] = state.get("handoff_count", 0) + 1
            _update_handoff_history(output, state, handoff)
        else:
            logger.warning(
                "research_handoff_blocked",
                target=handoff.get("target_agent", ""),
            )
            if not state.get("response"):
                output["response"] = (
                    "I couldn't hand off that request, so I'm continuing here. "
                    "Please share more details or rephrase."
                )

    logger.info(
        "research_post_completed",
        has_findings=bool(shared_memory.get("research_findings")),
        has_handoff=bool(handoff),
    )

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
        "task_id": state.get("task_id"),
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
    if result.get("images"):
        shared_memory["data_images"] = result.get("images", [])
    output["shared_memory"] = shared_memory

    # Check for handoff in result
    handoff = result.get("pending_handoff")
    if handoff:
        if _can_handoff(state, handoff.get("target_agent", "")):
            output["pending_handoff"] = handoff
            output["handoff_count"] = state.get("handoff_count", 0) + 1
            _update_handoff_history(output, state, handoff)
        else:
            logger.warning(
                "data_handoff_blocked",
                target=handoff.get("target_agent", ""),
            )
            if not output.get("response"):
                output["response"] = (
                    "I couldn't hand off that request, so I'm continuing here. "
                    "Please share more details or rephrase."
                )

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
    graph.add_node("data", data_node)

    # Research agent uses prep -> subgraph -> post pattern for real-time streaming
    # Adding the subgraph directly (not wrapped) allows internal events to propagate
    graph.add_node("research_prep", research_prep_node)
    graph.add_node("research", research_subgraph)  # Subgraph directly as node
    graph.add_node("research_post", research_post_node)

    # Set entry point
    graph.set_entry_point("router")

    # Conditional edges from router to appropriate agent
    # Note: Deprecated agent types (code, writing, image) are automatically
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

        effective_task_id = task_id or str(uuid.uuid4())
        normalized_mode = mode
        if isinstance(mode, str):
            mode_lower = mode.lower()
            if mode_lower in {"code", "writing", "image"}:
                normalized_mode = "chat"
            else:
                normalized_mode = mode_lower

        # Build initial state
        initial_state: SupervisorState = {
            "query": query,
            "mode": normalized_mode,
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

        # Create config with thread_id for checkpointing and recursion limit
        from app.config import settings

        thread_id = effective_task_id
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.langgraph_recursion_limit,
        }

        logger.info(
            "supervisor_run_started",
            query=query[:50],
            mode=normalized_mode,
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
        emitted_image_indices = set()  # Track yielded image events by index
        streamed_tokens = False
        # Track tool calls by ID for matching with results
        pending_tool_calls: dict[str, dict] = {}
        pending_tool_calls_by_tool: dict[str, list[str]] = {}

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
                    if any(
                        enabled and _node_matches_streaming(node_name, node)
                        for node, enabled in STREAMING_CONFIG.items()
                    ):
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
                                    # BUT: Don't skip token events from these nodes:
                                    # - "present" nodes (like image agent's present_results_node)
                                    # - "image" node (supervisor wrapper for image agent)
                                    # - "summarize" nodes (data analysis results)
                                    # These contain programmatic responses that weren't streamed via LLM
                                    is_programmatic_node = any(
                                        keyword in node_name.lower()
                                        for keyword in ["present", "image", "summarize"]
                                    )
                                    if e.get("type") == "token" and streamed_tokens and not is_programmatic_node:
                                        continue
                                    # Deduplicate stage events
                                    if e.get("type") == "stage":
                                        stage_key = f"{e.get('name')}:{e.get('status')}"
                                        if stage_key in emitted_stage_keys:
                                            continue
                                        emitted_stage_keys.add(stage_key)
                                    # Deduplicate tool_call events
                                    if e.get("type") == "tool_call":
                                        tool_id = e.get("id")
                                        if tool_id and tool_id in emitted_tool_call_ids:
                                            continue
                                        if tool_id:
                                            emitted_tool_call_ids.add(tool_id)
                                    # Deduplicate tool_result events
                                    if e.get("type") == "tool_result":
                                        tool_id = e.get("id")
                                        # Check if we've already emitted a result for this tool
                                        # Use a separate key to track emitted results
                                        result_key = f"result:{tool_id}"
                                        if tool_id and result_key in emitted_tool_call_ids:
                                            continue
                                        if tool_id:
                                            emitted_tool_call_ids.add(result_key)
                                    # Deduplicate image events by index
                                    if e.get("type") == "image":
                                        image_index = e.get("index", 0)
                                        if image_index in emitted_image_indices:
                                            logger.debug(
                                                "skipping_duplicate_image_event",
                                                node_name=node_name,
                                                index=image_index,
                                            )
                                            continue
                                        emitted_image_indices.add(image_index)
                                        logger.info(
                                            "yielding_image_event",
                                            node_name=node_name,
                                            has_data=bool(e.get("data")),
                                            data_length=len(e.get("data", "")) if e.get("data") else 0,
                                            has_url=bool(e.get("url")),
                                            url=e.get("url", "")[:100] if e.get("url") else None,
                                            mime_type=e.get("mime_type"),
                                            index=image_index,
                                        )
                                    # Browser stream events are emitted by react_tool.py when browser tools are invoked
                                    # No need to deduplicate here as they're emitted once per tool invocation
                                    # Log token events from image node for debugging
                                    if e.get("type") == "token" and "image" in node_name.lower():
                                        logger.info(
                                            "yielding_image_token_event",
                                            node_name=node_name,
                                            content_length=len(e.get("content", "")),
                                            content_preview=e.get("content", "")[:100],
                                        )
                                    yield e

                # Handle streaming tokens from LLM in real-time
                elif event_type == "on_chat_model_stream":
                    # Build node path string for checking
                    node_path_str = "/".join(node_path)

                    # Emit tool calls immediately if present in the chunk
                    # Note: During streaming, early chunks may have empty names.
                    # Only emit when we have a valid tool name to avoid generic "Tool" display.
                    chunk = (event.get("data") or {}).get("chunk")
                    if chunk and getattr(chunk, "tool_calls", None):
                        for tool_call in chunk.tool_calls:
                            # Skip None or non-dict tool calls
                            if not tool_call or not isinstance(tool_call, dict):
                                continue
                            func = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else None
                            tool_name = tool_call.get("name") or tool_call.get("tool") or (func.get("name") if func else None)
                            # Skip if no tool name yet (streaming chunks may arrive without name)
                            # The subagent's on_tool_call callback will emit the proper event
                            if not tool_name:
                                continue
                            tool_id = tool_call.get("id") or tool_call.get("tool_call_id")
                            # Generate a unique ID if not provided
                            if not tool_id:
                                tool_id = str(uuid.uuid4())
                            if tool_id in emitted_tool_call_ids:
                                continue
                            emitted_tool_call_ids.add(tool_id)
                            tool_args = tool_call.get("args") or {}
                            # Track pending tool call for matching with result
                            pending_tool_calls[tool_id] = {
                                "tool": tool_name,
                                "args": tool_args,
                            }
                            pending_tool_calls_by_tool.setdefault(tool_name, []).append(tool_id)
                            yield {
                                "type": "tool_call",
                                "tool": tool_name,
                                "args": tool_args,
                                "id": tool_id,
                            }

                    # Use declarative config to determine streaming
                    should_stream = _path_has_streamable_node(node_path_str)

                    if should_stream:
                        chunk = (event.get("data") or {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            from app.ai.llm import extract_text_from_content
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

                    browser_tools = {
                        "browser_navigate",
                        "browser_click",
                        "browser_type",
                        "browser_screenshot",
                        "browser_scroll",
                        "browser_press_key",
                    }

                    # Emit browser_stream when E2B desktop available so frontend shows live viewer
                    if tool_name in browser_tools:
                        from app.agents import events as agent_events
                        from app.sandbox import (
                            get_desktop_sandbox_manager,
                            is_desktop_sandbox_available,
                        )

                        if is_desktop_sandbox_available():
                            uid = (
                                tool_input.get("user_id")
                                if isinstance(tool_input, dict)
                                else None
                            )
                            tid = (
                                tool_input.get("task_id")
                                if isinstance(tool_input, dict)
                                else None
                            )
                            uid = uid if uid is not None else user_id
                            tid = tid if tid is not None else effective_task_id
                            try:
                                manager = get_desktop_sandbox_manager()
                                session = await manager.get_or_create_sandbox(
                                    user_id=uid,
                                    task_id=tid,
                                    launch_browser=True,
                                )
                                stream_url, auth_key = await manager.ensure_stream_ready(
                                    session
                                )
                                yield agent_events.browser_stream(
                                    stream_url=stream_url,
                                    sandbox_id=session.sandbox_id,
                                    auth_key=auth_key,
                                )
                            except Exception as e:
                                logger.warning(
                                    "browser_stream_emit_failed",
                                    tool=tool_name,
                                    error=str(e),
                                )

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
                        pending_tool_calls_by_tool.setdefault(tool_name, []).append(
                            tool_call_id
                        )
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_input if isinstance(tool_input, dict) else {},
                            "id": tool_call_id,
                        }

                    # Emit browser_action events for browser tools
                    if tool_name in browser_tools:
                        from app.agents import events as agent_events

                        # Emit browser_action event with description of the action about to happen
                        action_descriptions = {
                            "browser_navigate": ("navigate", "Navigating to URL", tool_input.get("url", "") if isinstance(tool_input, dict) else ""),
                            "browser_click": ("click", "Clicking on element", f"({tool_input.get('x', '?')}, {tool_input.get('y', '?')})" if isinstance(tool_input, dict) else ""),
                            "browser_type": ("type", "Typing text", tool_input.get("text", "")[:50] if isinstance(tool_input, dict) else ""),
                            "browser_screenshot": ("screenshot", "Taking screenshot", None),
                            "browser_scroll": ("scroll", "Scrolling page", tool_input.get("direction", "down") if isinstance(tool_input, dict) else "down"),
                            "browser_press_key": ("key", "Pressing key", tool_input.get("key", "") if isinstance(tool_input, dict) else ""),
                        }
                        if tool_name in action_descriptions:
                            action, desc, target = action_descriptions[tool_name]
                            yield agent_events.browser_action(
                                action=action,
                                description=desc,
                                target=target,
                                status="running",
                            )

                # Handle tool execution end - emit tool_result event
                elif event_type == "on_tool_end":
                    run_id = event.get("run_id", "")
                    tool_name = event.get("name", "")
                    output = (event.get("data") or {}).get("output", "")

                    # Find matching tool call by run_id, then by tool order
                    tool_call_id = None
                    matched_info = None
                    if run_id:
                        for tid, info in pending_tool_calls.items():
                            if info.get("run_id") == run_id:
                                tool_call_id = tid
                                matched_info = info
                                break
                    if not tool_call_id and tool_name:
                        tool_queue = pending_tool_calls_by_tool.get(tool_name) or []
                        if tool_queue:
                            tool_call_id = tool_queue.pop(0)
                            matched_info = pending_tool_calls.get(tool_call_id)

                    # Try to get tool name from matched pending call if not in event
                    if not tool_name and matched_info:
                        tool_name = matched_info.get("tool", "")

                    # Skip if we still don't have a tool name
                    if not tool_name:
                        continue

                    # If no match found, use run_id as the ID
                    if not tool_call_id:
                        tool_call_id = str(run_id) if run_id else str(uuid.uuid4())

                    # Emit browser_action "completed" event for browser tools
                    browser_tools = {"browser_navigate", "browser_click", "browser_type", "browser_screenshot", "browser_scroll", "browser_press_key"}
                    if tool_name in browser_tools:
                        from app.agents import events as agent_events
                        action_names = {
                            "browser_navigate": "navigate",
                            "browser_click": "click",
                            "browser_type": "type",
                            "browser_screenshot": "screenshot",
                            "browser_scroll": "scroll",
                            "browser_press_key": "key",
                        }
                        yield agent_events.browser_action(
                            action=action_names.get(tool_name, tool_name),
                            description=f"{tool_name.replace('browser_', '').replace('_', ' ').title()} completed",
                            status="completed",
                        )

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
                    if tool_name in pending_tool_calls_by_tool:
                        try:
                            pending_tool_calls_by_tool[tool_name].remove(tool_call_id)
                        except ValueError:
                            pass
                        if not pending_tool_calls_by_tool[tool_name]:
                            pending_tool_calls_by_tool.pop(tool_name, None)

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

        from app.config import settings

        config = {
            "configurable": {"thread_id": str(uuid.uuid4())},
            "recursion_limit": settings.langgraph_recursion_limit,
        }

        result = await self.graph.ainvoke(initial_state, config=config)
        return result


# Global instance for convenience
agent_supervisor = AgentSupervisor()
