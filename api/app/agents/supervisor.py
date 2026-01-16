"""Supervisor/orchestrator for the multi-agent system."""

from typing import Any, AsyncGenerator

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.routing import route_query
from app.agents.state import AgentType, SupervisorState
from app.agents.subagents.chat import chat_subgraph
from app.agents.subagents.code import code_subgraph
from app.agents.subagents.analytics import data_subgraph
from app.agents.subagents.research import research_subgraph
from app.agents.subagents.writing import writing_subgraph
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario

logger = get_logger(__name__)


async def router_node(state: SupervisorState) -> dict:
    """Route the query to the appropriate agent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with selected_agent and routing_reason
    """
    result = await route_query(state)
    
    # Emit routing stage event
    selected_agent = result.get("selected_agent", "chat")
    events = result.get("events", [])
    result["events"] = events
    
    return result


async def chat_node(state: SupervisorState) -> dict:
    """Execute the chat subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with chat response and events
    """
    # Invoke chat subgraph
    result = await chat_subgraph.ainvoke(
        {
            "query": state.get("query") or "",
            "messages": state.get("messages") or [],
            "user_id": state.get("user_id"),
            "attachment_ids": state.get("attachment_ids") or [],
            "system_prompt": state.get("system_prompt"),
            "provider": state.get("provider"),
            "model": state.get("model"),
        }
    )
    return {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }


async def research_node(state: SupervisorState) -> dict:
    """Execute the research subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with research results and events
    """
    # Get research-specific parameters
    depth = state.get("depth", ResearchDepth.FAST)
    scenario = state.get("scenario", ResearchScenario.ACADEMIC)

    # Invoke research subgraph
    result = await research_subgraph.ainvoke(
        {
            "query": state.get("query") or "",
            "depth": depth,
            "scenario": scenario,
            "task_id": state.get("task_id"),
            "user_id": state.get("user_id"),
            "attachment_ids": state.get("attachment_ids") or [],
            "provider": state.get("provider"),
            "model": state.get("model"),
        }
    )
    return {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }


async def code_node(state: SupervisorState) -> dict:
    """Execute the code subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with code results and events
    """
    # Invoke code subgraph
    result = await code_subgraph.ainvoke(
        {
            "query": state.get("query") or "",
            "messages": state.get("messages") or [],
            "user_id": state.get("user_id"),
            "attachment_ids": state.get("attachment_ids") or [],
            "provider": state.get("provider"),
            "model": state.get("model"),
        }
    )
    return {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }


async def writing_node(state: SupervisorState) -> dict:
    """Execute the writing subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with writing results and events
    """
    # Invoke writing subgraph
    result = await writing_subgraph.ainvoke(
        {
            "query": state.get("query") or "",
            "messages": state.get("messages") or [],
            "user_id": state.get("user_id"),
            "attachment_ids": state.get("attachment_ids") or [],
            "provider": state.get("provider"),
            "model": state.get("model"),
        }
    )
    return {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }


async def data_node(state: SupervisorState) -> dict:
    """Execute the data analysis subagent.

    Args:
        state: Current supervisor state

    Returns:
        Dict with data analysis results and events
    """
    logger.info("data_analysis_started", query=state.get("query", "")[:50])

    # Invoke data analysis subgraph
    result = await data_subgraph.ainvoke(
        {
            "query": state.get("query") or "",
            "messages": state.get("messages") or [],
            "data_source": state.get("data_source", ""),
            "attachment_ids": state.get("attachment_ids") or [],
            "user_id": state.get("user_id"),
            "provider": state.get("provider"),
            "model": state.get("model"),
        }
    )
    return {
        "response": result.get("response", ""),
        "events": result.get("events", []),
    }


def select_agent(state: SupervisorState) -> str:
    """Select which agent to route to based on state.

    Args:
        state: Current supervisor state with selected_agent

    Returns:
        Node name to route to
    """
    selected = state.get("selected_agent", AgentType.CHAT.value)
    return selected


def create_supervisor_graph(checkpointer=None):
    """Create the supervisor graph that orchestrates subagents.

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled supervisor graph
    """
    graph = StateGraph(SupervisorState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("chat", chat_node)
    graph.add_node("research", research_node)
    graph.add_node("code", code_node)
    graph.add_node("writing", writing_node)
    graph.add_node("data", data_node)

    # Set entry point
    graph.set_entry_point("router")

    # Conditional edges from router to appropriate agent
    graph.add_conditional_edges(
        "router",
        select_agent,
        {
            AgentType.CHAT.value: "chat",
            AgentType.RESEARCH.value: "research",
            AgentType.CODE.value: "code",
            AgentType.WRITING.value: "writing",
            AgentType.DATA.value: "data",
        },
    )

    # All agents end the graph
    for agent in ["chat", "research", "code", "writing", "data"]:
        graph.add_edge(agent, END)

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
        emitted_stage_keys = set()  # Track emitted stages to avoid duplicates
        streamed_tokens = False

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
                    content_nodes = ["write", "finalize", "summarize", "generate", "outline"]
                    if any(node in node_name for node in content_nodes):
                        current_content_node = node_name

                    # Provide immediate feedback for data analysis steps
                    if node_name == "plan":
                        yield {"type": "stage", "name": "plan", "description": "Planning analysis...", "status": "running"}
                    elif node_name == "generate":
                        yield {"type": "stage", "name": "generate", "description": "Generating analysis code...", "status": "running"}
                    elif node_name == "execute":
                        yield {"type": "stage", "name": "execute", "description": "Executing analysis code...", "status": "running"}
                    elif node_name == "summarize":
                        yield {"type": "stage", "name": "summarize", "description": "Summarizing results...", "status": "running"}
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

                    # Extract events from output (including routing events)
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        events = output.get("events", [])
                        if isinstance(events, list):
                            for e in events:
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
                                    yield e

                # Handle streaming tokens from LLM in real-time
                elif event_type == "on_chat_model_stream":
                    # Build node path string for checking
                    node_path_str = "/".join(node_path)

                    # Emit tool calls immediately if present in the chunk
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and getattr(chunk, "tool_calls", None):
                        for tool_call in chunk.tool_calls:
                            tool_id = tool_call.get("id") or tool_call.get("tool_call_id")
                            if tool_id and tool_id in emitted_tool_call_ids:
                                continue
                            if tool_id:
                                emitted_tool_call_ids.add(tool_id)
                            yield {
                                "type": "tool_call",
                                "tool": tool_call.get("name") or tool_call.get("tool"),
                                "args": tool_call.get("args") or {},
                            }

                    # Determine if we should stream tokens based on mode and node path
                    if mode == "research":
                        # Stream from synthesis and writing for smoother feedback
                        should_stream = any(node in node_path_str for node in ["synthesize", "write"])
                    elif mode == "data":
                        # Stream from planning, generation, and summarization
                        should_stream = any(node in node_path_str for node in ["plan", "generate", "summarize"])
                    elif mode == "writing":
                        # Stream from outline and write nodes
                        should_stream = any(node in node_path_str for node in ["outline", "write"])
                    elif mode == "code":
                        # Stream from generate and finalize nodes
                        should_stream = any(node in node_path_str for node in ["generate", "finalize"])
                    elif mode == "chat":
                        # For chat mode, stream from agent node (where LLM response is generated)
                        should_stream = "agent" in node_path_str
                    else:
                        # For other modes, stream from common content stages
                        should_stream = any(
                            node in node_path_str
                            for node in [
                                "write",
                                "finalize",
                                "summarize",
                                "generate",
                                "outline",
                                "synthesize",
                                "analyze",
                                "agent",
                            ]
                        )
                    
                    if should_stream:
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            from app.services.llm import extract_text_from_content
                            content = extract_text_from_content(chunk.content)
                            if content:  # Only yield non-empty content
                                streamed_tokens = True
                                yield {"type": "token", "content": content}

                # Handle errors from subagents
                elif event_type == "on_chain_error":
                    error = event.get("data", {}).get("error")
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
            **kwargs,
        }

        config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        result = await self.graph.ainvoke(initial_state, config=config)
        return result


# Global instance for convenience
agent_supervisor = AgentSupervisor()
