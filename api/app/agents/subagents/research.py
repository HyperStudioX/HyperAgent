"""Research subagent for multi-step deep research tasks with tool calling."""

from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.prompts import get_analysis_prompt, get_report_prompt, get_synthesis_prompt
from app.agents.scenarios import get_scenario_config
from app.agents.state import ResearchState
from app.agents.tools import parse_search_results, web_search
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario
from app.services.llm import llm_service
from app.services.search import SearchResult

logger = get_logger(__name__)

# Tools available for research
RESEARCH_TOOLS = [web_search]

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

SEARCH_SYSTEM_PROMPT = """You are a research assistant that gathers information from the web.

Your task is to search for relevant information on the given topic. You have access to a web_search tool.

Guidelines:
1. Start with a broad search to understand the topic
2. Follow up with specific searches to fill in gaps
3. For {scenario} research, focus on: {search_focus}
4. Search depth: {depth} - adjust your search strategy accordingly
5. Maximum searches allowed: {max_searches}

When you have gathered enough information to write a comprehensive {report_length} report,
respond with "SEARCH_COMPLETE" to proceed to analysis.

Do NOT write the report yet - just gather sources."""


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
    search_prompt = SEARCH_SYSTEM_PROMPT.format(
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
            HumanMessage(content=f"Research topic: {state.get('query', '')}"),
        ],
        "sources": [],
        "search_complete": False,
        "events": [
            {
                "type": "config",
                "depth": depth.value if isinstance(depth, ResearchDepth) else depth,
                "scenario": scenario.value if isinstance(scenario, ResearchScenario) else scenario,
            },
            {
                "type": "step",
                "step_type": "search",
                "description": "Searching for sources...",
                "status": "running",
            },
        ],
    }


async def search_agent_node(state: ResearchState) -> dict:
    """ReAct agent node that decides whether to search or finish.

    Args:
        state: Current research state

    Returns:
        Dict with updated messages and events
    """
    lc_messages = state.get("lc_messages", [])
    depth_config = state.get("depth_config", {})

    logger.info("search_agent_processing", message_count=len(lc_messages))

    events = []

    # Get LLM with tools bound
    llm = llm_service.get_llm()
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)

    try:
        response = await llm_with_tools.ainvoke(lc_messages)
        lc_messages = lc_messages + [response]

        # Check if search is complete
        if response.content and "SEARCH_COMPLETE" in response.content:
            logger.info("search_phase_complete")
            return {
                "lc_messages": lc_messages,
                "search_complete": True,
                "events": events,
            }

        # Log tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                events.append(
                    {
                        "type": "tool_call",
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                    }
                )
            logger.info(
                "search_tool_calls",
                tools=[tc["name"] for tc in response.tool_calls],
            )

        return {
            "lc_messages": lc_messages,
            "events": events,
        }

    except Exception as e:
        logger.error("search_agent_failed", error=str(e))
        # On error, mark search complete to proceed
        return {
            "lc_messages": lc_messages,
            "search_complete": True,
            "events": [
                {
                    "type": "step",
                    "step_type": "search",
                    "description": f"Search error: {str(e)}",
                    "status": "completed",
                }
            ],
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

    events = []

    # Get the last AI message with tool calls
    last_message = lc_messages[-1] if lc_messages else None
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"lc_messages": lc_messages, "events": events}

    # Execute tools
    tool_executor = ToolNode(RESEARCH_TOOLS)
    tool_results = await tool_executor.ainvoke({"messages": [last_message]})

    # Process results
    for msg in tool_results.get("messages", []):
        lc_messages = lc_messages + [msg]
        if isinstance(msg, ToolMessage):
            # Parse structured results from tool output
            new_sources = parse_search_results(msg.content)
            sources.extend(new_sources)

            # Emit source events
            for source in new_sources:
                events.append(
                    {
                        "type": "source",
                        "title": source.title,
                        "url": source.url,
                        "snippet": source.snippet,
                        "relevance_score": source.relevance_score,
                    }
                )

    logger.info("search_tools_executed", new_sources=len(sources))

    return {
        "lc_messages": lc_messages,
        "sources": sources,
        "events": events,
    }


def should_continue_search(state: ResearchState) -> Literal["tools", "collect"]:
    """Determine whether to execute tools or finish search phase.

    Args:
        state: Current research state

    Returns:
        Next node: "tools" if tool calls pending, "collect" if done
    """
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

    events = [
        {
            "type": "step",
            "step_type": "search",
            "description": f"Found {len(sources)} sources",
            "status": "completed",
        }
    ]

    logger.info("sources_collected", count=len(sources))

    return {"events": events}


async def analyze_node(state: ResearchState) -> dict:
    """Analyze the search results.

    Args:
        state: Current research state with sources

    Returns:
        Dict with analysis and events
    """
    query = state.get("query", "")
    sources = state.get("sources", [])
    system_prompt = state.get("system_prompt", "")
    depth_config = state.get("depth_config", {})

    events = [
        {
            "type": "step",
            "step_type": "analyze",
            "description": f"Analyzing sources ({depth_config.get('analysis_detail', 'thorough')})...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()
    sources_text = _format_sources(sources)

    analysis_prompt = get_analysis_prompt(
        query=query,
        sources_text=sources_text,
        analysis_detail=depth_config.get("analysis_detail", "thorough"),
    )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=analysis_prompt),
            ]
        )
        analysis_text = response.content
        logger.info("analysis_completed", query=query[:50])
    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        analysis_text = f"Analysis of '{query}' based on {len(sources)} sources."

    events.append(
        {
            "type": "step",
            "step_type": "analyze",
            "description": "Source analysis complete",
            "status": "completed",
        }
    )

    return {
        "analysis": analysis_text,
        "events": events,
    }


async def synthesize_node(state: ResearchState) -> dict:
    """Synthesize the analysis findings.

    Args:
        state: Current research state with analysis

    Returns:
        Dict with synthesis and events
    """
    query = state.get("query", "")
    analysis_text = state.get("analysis", "")
    system_prompt = state.get("system_prompt", "")

    events = [
        {
            "type": "step",
            "step_type": "synthesize",
            "description": "Synthesizing findings...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()
    synthesis_prompt = get_synthesis_prompt(
        query=query,
        analysis_text=analysis_text,
    )

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=synthesis_prompt),
            ]
        )
        synthesis_text = response.content
        logger.info("synthesis_completed", query=query[:50])
    except Exception as e:
        logger.error("synthesis_failed", error=str(e))
        synthesis_text = analysis_text

    events.append(
        {
            "type": "step",
            "step_type": "synthesize",
            "description": "Synthesis complete",
            "status": "completed",
        }
    )

    return {
        "synthesis": synthesis_text,
        "events": events,
    }


async def write_node(state: ResearchState) -> dict:
    """Write the research report.

    Args:
        state: Current research state with analysis/synthesis

    Returns:
        Dict with report chunks and events
    """
    query = state.get("query", "")
    analysis = state.get("analysis", "")
    synthesis = state.get("synthesis", "")
    sources = state.get("sources", [])
    system_prompt = state.get("system_prompt", "")
    report_structure = state.get("report_structure", [])
    depth_config = state.get("depth_config", {})

    events = [
        {
            "type": "step",
            "step_type": "write",
            "description": "Writing research report...",
            "status": "running",
        }
    ]

    # Use synthesis if available, otherwise analysis
    combined_findings = synthesis if synthesis else analysis
    sources_text = _format_sources(sources)

    report_prompt = get_report_prompt(
        query=query,
        combined_findings=combined_findings,
        sources_text=sources_text,
        report_structure=report_structure,
        report_length=depth_config.get("report_length", "comprehensive"),
    )

    llm = llm_service.get_llm()
    report_chunks = []

    try:
        async for chunk in llm.astream(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=report_prompt),
            ]
        ):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    report_chunks.append(content)
                    events.append({"type": "token", "content": content})

        logger.info("report_completed", query=query[:50])
    except Exception as e:
        logger.error("report_generation_failed", error=str(e))
        events.append({"type": "token", "content": f"\n\nError generating report: {str(e)}"})

    events.append(
        {
            "type": "step",
            "step_type": "write",
            "description": "Report complete",
            "status": "completed",
        }
    )

    return {
        "report_chunks": report_chunks,
        "response": "".join(report_chunks),
        "events": events,
    }


def should_synthesize(state: ResearchState) -> str:
    """Determine whether to run synthesis step.

    Args:
        state: Current research state

    Returns:
        Next node name: "synthesize" or "write"
    """
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

    Graph structure:
    [init_config] → [search_agent] ⟲ [search_tools] (ReAct loop)
                            ↓
                    [collect_sources]
                            ↓
                      [analyze]
                            ↓
                    [synthesize?] → [write] → [END]

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
