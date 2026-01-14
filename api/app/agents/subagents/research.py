"""Research subagent for multi-step deep research tasks."""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.prompts import get_analysis_prompt, get_report_prompt, get_synthesis_prompt
from app.agents.scenarios import get_scenario_config
from app.agents.state import ResearchState
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario
from app.services.llm import llm_service
from app.services.search import SearchResult, search_service

logger = get_logger(__name__)

# Depth-based configuration
DEPTH_CONFIG = {
    ResearchDepth.QUICK: {
        "analysis_detail": "brief",
        "skip_synthesis": True,
        "report_length": "concise",
    },
    ResearchDepth.STANDARD: {
        "analysis_detail": "thorough",
        "skip_synthesis": False,
        "report_length": "comprehensive",
    },
    ResearchDepth.DEEP: {
        "analysis_detail": "in-depth with follow-up questions",
        "skip_synthesis": False,
        "report_length": "detailed and extensive",
    },
}


async def init_config_node(state: ResearchState) -> dict:
    """Initialize research configuration from scenario and depth.

    Args:
        state: Current research state

    Returns:
        Dict with configuration fields
    """
    depth = state.get("depth", ResearchDepth.STANDARD)
    scenario = state.get("scenario", ResearchScenario.ACADEMIC)

    config = get_scenario_config(scenario)
    depth_config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG[ResearchDepth.STANDARD])

    logger.info(
        "research_config_initialized",
        depth=depth.value if isinstance(depth, ResearchDepth) else depth,
        scenario=scenario.value if isinstance(scenario, ResearchScenario) else scenario,
    )

    return {
        "system_prompt": config["system_prompt"],
        "report_structure": config["report_structure"],
        "depth_config": depth_config,
        "events": [
            {
                "type": "config",
                "depth": depth.value if isinstance(depth, ResearchDepth) else depth,
                "scenario": scenario.value if isinstance(scenario, ResearchScenario) else scenario,
            }
        ],
    }


async def search_node(state: ResearchState) -> dict:
    """Search for sources relevant to the research query.

    Args:
        state: Current research state with query

    Returns:
        Dict with sources and events
    """
    query = state.get("query", "")
    depth = state.get("depth", ResearchDepth.STANDARD)
    scenario = state.get("scenario", ResearchScenario.ACADEMIC)
    config = get_scenario_config(scenario)

    events = [
        {
            "type": "step",
            "step_type": "search",
            "description": f"Searching for {config['name'].lower()} sources...",
            "status": "running",
        }
    ]

    try:
        search_results = await search_service.search(
            query=query,
            depth=depth,
            scenario=scenario,
        )
    except ValueError as e:
        # API key not configured - fall back to mock results
        logger.warning("search_fallback_to_mock", error=str(e))
        search_results = _get_mock_results(query, config)
    except Exception as e:
        logger.error("search_failed", error=str(e))
        search_results = _get_mock_results(query, config)

    # Emit source events
    for result in search_results:
        events.append(
            {
                "type": "source",
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "relevance_score": result.relevance_score,
            }
        )

    events.append(
        {
            "type": "step",
            "step_type": "search",
            "description": f"Found {len(search_results)} sources",
            "status": "completed",
        }
    )

    logger.info("search_completed", query=query[:50], count=len(search_results))

    return {
        "sources": search_results,
        "events": events,
    }


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
                report_chunks.append(chunk.content)
                events.append({"type": "token", "content": chunk.content})

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
    formatted = []
    for i, result in enumerate(results, 1):
        score_str = f" (relevance: {result.relevance_score:.2f})" if result.relevance_score else ""
        formatted.append(f"{i}. [{result.title}]({result.url}){score_str}\n   {result.snippet}")
    return "\n\n".join(formatted)


def _get_mock_results(query: str, config: dict) -> list[SearchResult]:
    """Generate mock results when search API is unavailable."""
    search_focus = config.get("search_focus", ["information"])
    return [
        SearchResult(
            title=f"{config['name']} - {query}",
            url="https://example.com/article1",
            snippet=f"Comprehensive {search_focus[0]} on {query}. This source provides detailed information and analysis.",
        ),
        SearchResult(
            title=f"Understanding {query}",
            url="https://example.com/article2",
            snippet=f"Key {search_focus[1] if len(search_focus) > 1 else 'insights'} about {query}. An overview of important concepts.",
        ),
        SearchResult(
            title=f"{query}: A Comprehensive Guide",
            url="https://example.com/article3",
            snippet=f"In-depth guide covering all aspects of {query}. Includes examples and best practices.",
        ),
    ]


def create_research_graph() -> StateGraph:
    """Create the research subagent graph.

    Graph structure:
    [init_config] → [search] → [analyze] → [synthesize?] → [write] → [END]
                                              ↓ (skip if QUICK)
                                            [write]

    Returns:
        Compiled research graph
    """
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("init_config", init_config_node)
    graph.add_node("search", search_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("write", write_node)

    # Set entry point
    graph.set_entry_point("init_config")

    # Add edges
    graph.add_edge("init_config", "search")
    graph.add_edge("search", "analyze")

    # Conditional edge: skip synthesis for QUICK depth
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
