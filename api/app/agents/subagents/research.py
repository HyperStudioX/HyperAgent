"""Research subagent for multi-step deep research tasks with tool calling and handoff support."""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.prompts import (
    get_analysis_prompt,
    get_report_prompt,
    get_search_system_prompt,
    get_synthesis_prompt,
)
from app.agents.scenarios import get_scenario_config
from app.agents.state import ResearchState
from app.agents.tools import (
    parse_search_results,
    get_tools_for_agent,
)
from app.agents.utils import (
    extract_and_add_image_events,
    create_stage_event,
    create_error_event,
    create_tool_call_event,
    create_tool_result_event,
)
from app.agents import events
from app.core.logging import get_logger
from app.models.schemas import LLMProvider, ResearchDepth, ResearchScenario
from app.ai.llm import llm_service, extract_text_from_content
from app.services.search import SearchResult

logger = get_logger(__name__)

# Depth-based configuration
DEPTH_CONFIG = {
    ResearchDepth.FAST: {
        "analysis_detail": "brief",
        "skip_synthesis": True,
        "report_length": "concise",
        "max_searches": 1,
        "search_depth": "basic",
    },
    ResearchDepth.DEEP: {
        "analysis_detail": "in-depth with follow-up questions",
        "skip_synthesis": False,
        "report_length": "detailed and extensive",
        "max_searches": 5,
        "search_depth": "advanced",
    },
}


async def init_config_node(state: ResearchState) -> dict:
    """Initialize research configuration from scenario and depth.

    Args:
        state: Current research state

    Returns:
        Dict with configuration fields
    """
    depth = state.get("depth", ResearchDepth.FAST)
    scenario = state.get("scenario", ResearchScenario.ACADEMIC)

    config = get_scenario_config(scenario)
    depth_config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG[ResearchDepth.FAST])

    # Build search system prompt
    search_prompt = get_search_system_prompt(
        scenario=config["name"],
        search_focus=", ".join(config.get("search_focus", [])),
        depth=depth.value if isinstance(depth, ResearchDepth) else depth,
        max_searches=depth_config["max_searches"],
        report_length=depth_config["report_length"],
    )

    logger.info(
        "research_config_initialized",
        depth=depth.value if isinstance(depth, ResearchDepth) else depth,
        scenario=scenario.value if isinstance(scenario, ResearchScenario) else scenario,
    )

    return {
        "system_prompt": config["system_prompt"],
        "report_structure": config["report_structure"],
        "depth_config": depth_config,
        "lc_messages": [
            SystemMessage(content=search_prompt),
            HumanMessage(content=f"Research topic: {state.get('query') or ''}"),
        ],
        "sources": [],
        "search_complete": False,
        "tool_iterations": 0,
        "events": [
            events.config(
                depth=depth.value if isinstance(depth, ResearchDepth) else depth,
                scenario=scenario.value if isinstance(scenario, ResearchScenario) else scenario,
            ),
            create_stage_event("search", "Searching for sources...", "running"),
        ],
    }


async def search_agent_node(state: ResearchState) -> dict:
    """ReAct agent node that decides whether to search or finish.

    Args:
        state: Current research state

    Returns:
        Dict with updated messages, events, and potential handoff
    """
    lc_messages = state.get("lc_messages") or []
    depth_config = state.get("depth_config") or {}
    tool_iterations = state.get("tool_iterations") or 0
    max_searches = depth_config.get("max_searches", 5)

    # Check for deferred handoff from previous iteration
    # This occurs when LLM returned both search tools and handoff - we execute
    # search tools first, then return the handoff on the next iteration
    deferred_handoff = state.get("deferred_handoff")
    if deferred_handoff:
        logger.info(
            "processing_deferred_handoff",
            target=deferred_handoff.get("target_agent"),
        )
        return {
            "lc_messages": lc_messages,
            "search_complete": True,
            "events": [events.handoff(
                source="research",
                target=deferred_handoff.get("target_agent", ""),
                task=deferred_handoff.get("task_description", ""),
            )],
            "pending_handoff": deferred_handoff,
            "deferred_handoff": None,  # Clear the deferred handoff
        }

    logger.info(
        "search_agent_processing",
        message_count=len(lc_messages),
        tool_iterations=tool_iterations,
        max_searches=max_searches,
    )

    # Enforce iteration limit to prevent infinite loops
    if tool_iterations >= max_searches:
        logger.warning(
            "max_searches_reached",
            count=tool_iterations,
            max=max_searches,
        )
        return {
            "lc_messages": lc_messages,
            "search_complete": True,
            "events": [
                create_stage_event(
                    "search",
                    f"Reached maximum searches ({max_searches}). Proceeding with available sources.",
                    "completed",
                )
            ],
        }

    event_list = []

    # Get all tools for research agent (includes browser, search, image, handoffs)
    all_tools = get_tools_for_agent("research", include_handoffs=True)

    # Get LLM with tools bound
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task("research", provider=provider, tier_override=tier, model_override=model)
    llm_with_tools = llm.bind_tools(all_tools)

    try:
        response = await llm_with_tools.ainvoke(lc_messages)
        lc_messages = lc_messages + [response]

        # Check if search is complete
        if response.content and "SEARCH_COMPLETE" in response.content:
            logger.info("search_phase_complete", tool_iterations=tool_iterations)
            return {
                "lc_messages": lc_messages,
                "search_complete": True,
                "events": event_list,
            }

        # Track and log tool calls
        if response.tool_calls:
            # First pass: separate handoff and non-handoff tool calls
            handoff_call = None
            other_tool_calls = []

            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name") or ""
                if tool_name.startswith("handoff_to_"):
                    handoff_call = tool_call
                else:
                    other_tool_calls.append(tool_call)

            # If we have a handoff but also other tools, defer the handoff
            # to let the search tools execute first
            if handoff_call and other_tool_calls:
                target_agent = handoff_call.get("name", "").replace("handoff_to_", "")
                task_description = handoff_call.get("args", {}).get("task_description", "")
                context = handoff_call.get("args", {}).get("context", "")

                deferred_handoff_info = {
                    "source_agent": "research",
                    "target_agent": target_agent,
                    "task_description": task_description,
                    "context": context,
                }

                logger.info(
                    "handoff_deferred_for_tools",
                    target=target_agent,
                    pending_tools=[tc.get("name") for tc in other_tool_calls],
                )

                # Increment search count for non-handoff tool calls only
                tool_iterations += len(other_tool_calls)
                for tool_call in other_tool_calls:
                    valid_tool_names = [tool.name for tool in all_tools]
                    if tool_call["name"] not in valid_tool_names:
                        logger.warning(
                            "invalid_tool_call",
                            tool=tool_call["name"],
                            allowed=valid_tool_names,
                        )
                        continue
                    event_list.append(create_tool_call_event(
                        tool_call["name"],
                        tool_call["args"],
                        tool_call.get("id"),
                    ))

                logger.info(
                    "search_tool_calls",
                    tools=[tc["name"] for tc in other_tool_calls],
                    tool_iterations=tool_iterations,
                )

                return {
                    "lc_messages": lc_messages,
                    "tool_iterations": tool_iterations,
                    "events": event_list,
                    "deferred_handoff": deferred_handoff_info,
                }

            # If only handoff (no other tools), process it immediately
            if handoff_call and not other_tool_calls:
                target_agent = handoff_call.get("name", "").replace("handoff_to_", "")
                task_description = handoff_call.get("args", {}).get("task_description", "")
                context = handoff_call.get("args", {}).get("context", "")

                pending_handoff = {
                    "source_agent": "research",
                    "target_agent": target_agent,
                    "task_description": task_description,
                    "context": context,
                }

                event_list.append(events.handoff(
                    source="research",
                    target=target_agent,
                    task=task_description,
                ))

                logger.info("research_handoff_detected", target=target_agent)

                return {
                    "lc_messages": lc_messages,
                    "search_complete": True,
                    "events": event_list,
                    "pending_handoff": pending_handoff,
                }

            # No handoff - process all tool calls normally
            tool_iterations += len(response.tool_calls)
            for tool_call in response.tool_calls:
                # Validate tool name
                valid_tool_names = [tool.name for tool in all_tools]
                if tool_call["name"] not in valid_tool_names:
                    logger.warning(
                        "invalid_tool_call",
                        tool=tool_call["name"],
                        allowed=valid_tool_names,
                    )
                    continue

                event_list.append(create_tool_call_event(
                    tool_call["name"],
                    tool_call["args"],
                    tool_call.get("id"),
                ))
            logger.info(
                "search_tool_calls",
                tools=[tc["name"] for tc in response.tool_calls],
                tool_iterations=tool_iterations,
            )

        if not response.tool_calls:
            logger.info("search_phase_complete_no_tool_calls", tool_iterations=tool_iterations)
            return {
                "lc_messages": lc_messages,
                "search_complete": True,
                "events": event_list,
            }

        return {
            "lc_messages": lc_messages,
            "tool_iterations": tool_iterations,
            "events": event_list,
        }

    except Exception as e:
        logger.error("search_agent_failed", error=str(e), tool_iterations=tool_iterations)
        return {
            "lc_messages": lc_messages,
            "search_complete": True,
            "events": [create_error_event("search", str(e), f"Search error: {str(e)}")],
        }


async def search_tools_node(state: ResearchState) -> dict:
    """Execute search tool calls and collect results.

    Args:
        state: Current research state with pending tool calls

    Returns:
        Dict with tool results and collected sources
    """
    lc_messages = state.get("lc_messages", [])
    sources = list(state.get("sources", []))
    user_id = state.get("user_id")
    task_id = state.get("task_id")

    event_list = []

    # Get the last AI message with tool calls
    last_message = lc_messages[-1] if lc_messages else None
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"lc_messages": lc_messages, "events": event_list}

    context_tool_names = {
        "browser_navigate",
        "browser_click",
        "browser_type",
        "browser_scroll",
        "browser_press_key",
        "browser_screenshot",
        "browser_get_stream_url",
        "execute_code",
        "sandbox_file",
    }
    effective_message = last_message
    if user_id or task_id:
        updated_tool_calls = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name") or ""
            tool_args = tool_call.get("args") or {}
            if tool_name in context_tool_names:
                tool_args = dict(tool_args)
                if user_id is not None:
                    tool_args["user_id"] = user_id
                if task_id is not None:
                    tool_args["task_id"] = task_id
                tool_call = {**tool_call, "args": tool_args}
            updated_tool_calls.append(tool_call)
        effective_message = AIMessage(
            content=last_message.content,
            tool_calls=updated_tool_calls,
        )

    # Pre-execution: Check for browser tools and emit stream event BEFORE execution
    browser_tools = {"browser_navigate", "browser_click", "browser_type", "browser_screenshot"}
    has_browser_tool = any(
        tc.get("name") in browser_tools for tc in effective_message.tool_calls
    )

    if has_browser_tool:
        try:
            from app.sandbox import get_desktop_sandbox_manager

            manager = get_desktop_sandbox_manager()
            session = await manager.get_or_create_sandbox(
                user_id=user_id,
                task_id=task_id,
                launch_browser=True,
            )

            # Get stream URL and emit event immediately
            try:
                stream_url, auth_key = await session.executor.get_stream_url(require_auth=True)
                event_list.append(events.browser_stream(
                    stream_url=stream_url,
                    sandbox_id=session.sandbox_id,
                    auth_key=auth_key,
                ))
                logger.info("research_browser_stream_emitted", sandbox_id=session.sandbox_id)
            except Exception as stream_err:
                if "already running" in str(stream_err).lower():
                    import asyncio
                    if session.executor.sandbox and session.executor.sandbox.stream:
                        auth_key = await asyncio.to_thread(session.executor.sandbox.stream.get_auth_key)
                        stream_url = await asyncio.to_thread(
                            session.executor.sandbox.stream.get_url,
                            auth_key=auth_key,
                        )
                        event_list.append(events.browser_stream(
                            stream_url=stream_url,
                            sandbox_id=session.sandbox_id,
                            auth_key=auth_key,
                        ))
                        logger.info("research_browser_stream_emitted_reused", sandbox_id=session.sandbox_id)
                else:
                    logger.warning("research_browser_stream_failed", error=str(stream_err))
        except Exception as e:
            logger.warning("research_browser_pre_execution_failed", error=str(e))

    # Get all tools for research agent (includes browser, search, image, handoffs)
    all_tools = get_tools_for_agent("research", include_handoffs=True)

    # Execute tools
    tool_executor = ToolNode(all_tools)
    tool_results = await tool_executor.ainvoke({"messages": [effective_message]})

    # Process results
    for msg in tool_results.get("messages", []):
        lc_messages = lc_messages + [msg]
        if isinstance(msg, ToolMessage):
            # Emit tool result event
            event_list.append(create_tool_result_event(msg.name, msg.content, msg.tool_call_id))

            # Note: generate_image visualization is handled in react_tool.py

            # Parse structured results from tool output (web_search results)
            new_sources = parse_search_results(msg.content)
            sources.extend(new_sources)

            # Emit source events
            for source in new_sources:
                event_list.append(events.source(
                    title=source.title,
                    url=source.url,
                    snippet=source.snippet,
                    relevance_score=source.relevance_score,
                ))

    logger.info("search_tools_executed", new_sources=len(sources))

    return {
        "lc_messages": lc_messages,
        "sources": sources,
        "events": event_list,
    }


def should_continue_search(state: ResearchState) -> Literal["tools", "collect"]:
    """Determine whether to execute tools or finish search phase.

    Args:
        state: Current research state

    Returns:
        Next node: "tools" if tool calls pending, "collect" if done
    """
    # Check for pending handoff
    if state.get("pending_handoff"):
        return "collect"

    # Check if search is marked complete
    if state.get("search_complete", False):
        return "collect"

    lc_messages = state.get("lc_messages", [])
    if not lc_messages:
        return "collect"

    last_message = lc_messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "collect"


async def collect_sources_node(state: ResearchState) -> dict:
    """Finalize source collection and prepare for analysis.

    Args:
        state: Current research state

    Returns:
        Dict with finalized sources and events
    """
    sources = state.get("sources", [])

    event_list = [create_stage_event(
        "search",
        f"Found {len(sources)} sources",
        "completed",
    )]

    logger.info("sources_collected", count=len(sources))

    result = {"events": event_list}

    # Propagate handoff if present
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        result["pending_handoff"] = pending_handoff

    return result


async def analyze_node(state: ResearchState) -> dict:
    """Analyze the search results.

    Args:
        state: Current research state with sources

    Returns:
        Dict with analysis and events
    """
    pending_handoff = state.get("pending_handoff")
    sources = state.get("sources") or []

    # Only skip if there's a pending handoff AND no sources to analyze
    # When handoff is pending but we have sources, run analysis first
    # to populate research_findings for the target agent
    if pending_handoff and not sources:
        logger.info("analyze_skipped_no_sources", has_handoff=True)
        return {"analysis": "", "events": [], "pending_handoff": pending_handoff}

    query = state.get("query") or ""
    system_prompt = state.get("system_prompt") or ""
    depth_config = state.get("depth_config") or {}

    event_list = [create_stage_event(
        "analyze",
        f"Analyzing sources ({depth_config.get('analysis_detail', 'thorough')})...",
        "running",
    )]

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task("research", provider=provider, tier_override=tier, model_override=model)
    sources_text = _format_sources(sources)

    analysis_prompt = get_analysis_prompt(
        query=query,
        sources_text=sources_text,
        analysis_detail=depth_config.get("analysis_detail", "thorough"),
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=analysis_prompt),
        ])
        analysis_text = response.content
        logger.info("analysis_completed", query=query[:50])
    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        analysis_text = f"Analysis of '{query}' based on {len(sources)} sources."

    event_list.append(create_stage_event("analyze", "Source analysis complete", "completed"))

    result = {
        "analysis": analysis_text,
        "events": event_list,
    }

    # Preserve pending handoff if present
    if pending_handoff:
        result["pending_handoff"] = pending_handoff
        logger.info("analyze_completed_with_handoff", target=pending_handoff.get("target_agent"))

    return result


async def synthesize_node(state: ResearchState) -> dict:
    """Synthesize the analysis findings.

    Args:
        state: Current research state with analysis

    Returns:
        Dict with synthesis and events
    """
    # Skip if there's a pending handoff
    if state.get("pending_handoff"):
        return {"synthesis": "", "events": [], "pending_handoff": state.get("pending_handoff")}

    query = state.get("query") or ""
    analysis_text = state.get("analysis") or ""
    system_prompt = state.get("system_prompt") or ""

    event_list = [create_stage_event("synthesize", "Synthesizing findings...", "running")]

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task("research", provider=provider, tier_override=tier, model_override=model)
    synthesis_prompt = get_synthesis_prompt(
        query=query,
        analysis_text=analysis_text,
    )

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=synthesis_prompt),
        ])
        synthesis_text = response.content
        logger.info("synthesis_completed", query=query[:50])
    except Exception as e:
        logger.error("synthesis_failed", error=str(e))
        synthesis_text = analysis_text

    event_list.append(create_stage_event("synthesize", "Synthesis complete", "completed"))

    return {
        "synthesis": synthesis_text,
        "events": event_list,
    }


async def write_node(state: ResearchState) -> dict:
    """Write the research report.

    Args:
        state: Current research state with analysis/synthesis

    Returns:
        Dict with report chunks, events, and potential handoff
    """
    # Check for pending handoff
    pending_handoff = state.get("pending_handoff")
    if pending_handoff:
        return {
            "report_chunks": [],
            "response": "",
            "events": [],
            "pending_handoff": pending_handoff,
        }

    query = state.get("query") or ""
    analysis = state.get("analysis") or ""
    synthesis = state.get("synthesis") or ""
    sources = state.get("sources") or []
    system_prompt = state.get("system_prompt") or ""
    report_structure = state.get("report_structure") or []
    depth_config = state.get("depth_config") or {}

    event_list = [create_stage_event("write", "Writing research report...", "running")]

    # Use synthesis if available, otherwise analysis
    combined_findings = synthesis if synthesis else analysis
    sources_text = _format_sources(sources)

    locale = state.get("locale") or "en"
    report_prompt = get_report_prompt(
        query=query,
        combined_findings=combined_findings,
        sources_text=sources_text,
        report_structure=report_structure,
        report_length=depth_config.get("report_length", "comprehensive"),
        locale=locale,
    )

    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.choose_llm_for_task("research", provider=provider, tier_override=tier, model_override=model)
    report_chunks = []

    try:
        async for chunk in llm.astream([
            SystemMessage(content=system_prompt),
            HumanMessage(content=report_prompt),
        ]):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    report_chunks.append(content)
                    event_list.append(events.token(content))

        logger.info("report_completed", query=query[:50])
    except Exception as e:
        logger.error("report_generation_failed", error=str(e))
        event_list.append(events.token(f"\n\nError generating report: {str(e)}"))

    event_list.append(create_stage_event("write", "Report complete", "completed"))

    return {
        "report_chunks": report_chunks,
        "response": "".join(report_chunks),
        "events": event_list,
    }


def should_synthesize(state: ResearchState) -> str:
    """Determine whether to run synthesis step.

    Args:
        state: Current research state

    Returns:
        Next node name: "synthesize" or "write"
    """
    # Skip synthesis if there's a pending handoff
    if state.get("pending_handoff"):
        return "write"

    depth_config = state.get("depth_config", {})
    if depth_config.get("skip_synthesis", False):
        return "write"
    return "synthesize"


def _format_sources(results: list[SearchResult]) -> str:
    """Format search results for LLM prompts."""
    if not results:
        return "No sources available."

    formatted = []
    for i, result in enumerate(results, 1):
        score_str = f" (relevance: {result.relevance_score:.2f})" if result.relevance_score else ""
        formatted.append(f"{i}. [{result.title}]({result.url}){score_str}\n   {result.snippet}")
    return "\n\n".join(formatted)


def create_research_graph() -> StateGraph:
    """Create the research subagent graph with ReAct search pattern.

    Returns:
        Compiled research graph
    """
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("init_config", init_config_node)
    graph.add_node("search_agent", search_agent_node)
    graph.add_node("search_tools", search_tools_node)
    graph.add_node("collect_sources", collect_sources_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("write", write_node)

    # Set entry point
    graph.set_entry_point("init_config")

    # Build graph
    graph.add_edge("init_config", "search_agent")

    # ReAct loop for search
    graph.add_conditional_edges(
        "search_agent",
        should_continue_search,
        {
            "tools": "search_tools",
            "collect": "collect_sources",
        },
    )
    graph.add_edge("search_tools", "search_agent")

    # Analysis pipeline
    graph.add_edge("collect_sources", "analyze")

    # Conditional synthesis
    graph.add_conditional_edges(
        "analyze",
        should_synthesize,
        {
            "synthesize": "synthesize",
            "write": "write",
        },
    )

    graph.add_edge("synthesize", "write")
    graph.add_edge("write", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
research_subgraph = create_research_graph()
