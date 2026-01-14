"""Research agent for multi-step deep research tasks."""

from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import LLMProvider, ResearchDepth, ResearchScenario
from app.services.llm import llm_service
from app.services.search import SearchResult, search_service
from app.agents.scenarios import get_scenario_config

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


class ResearchAgent:
    """Research agent for multi-step deep research tasks."""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Get LLM instance."""
        if not self._llm:
            self._llm = llm_service.get_llm(provider=LLMProvider.ANTHROPIC)
        return self._llm

    async def run(
        self,
        query: str,
        depth: ResearchDepth = ResearchDepth.STANDARD,
        scenario: ResearchScenario = ResearchScenario.ACADEMIC,
    ) -> AsyncGenerator[dict, None]:
        """Run the research process and yield events.

        Args:
            query: Research query
            depth: Research depth (quick, standard, deep)
            scenario: Research scenario type

        Yields:
            Event dictionaries with type, step_type, description, status, etc.
        """
        config = get_scenario_config(scenario)
        depth_config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG[ResearchDepth.STANDARD])
        system_prompt = config["system_prompt"]
        report_structure = config["report_structure"]

        logger.info(
            "research_started",
            query=query,
            depth=depth.value,
            scenario=scenario.value,
        )

        # Step 1: Search
        yield {
            "type": "step",
            "step_type": "search",
            "description": f"Searching for {config['name'].lower()} sources...",
            "status": "running",
        }

        try:
            search_results = await search_service.search(
                query=query,
                depth=depth,
                scenario=scenario,
            )
        except ValueError as e:
            # API key not configured - fall back to mock results for development
            logger.warning("search_fallback_to_mock", error=str(e))
            search_results = self._get_mock_results(query, config)
        except Exception as e:
            logger.error("search_failed", error=str(e))
            search_results = self._get_mock_results(query, config)

        # Yield sources
        for result in search_results:
            yield {
                "type": "source",
                "title": result.title,
                "url": result.url,
                "snippet": result.snippet,
                "relevance_score": result.relevance_score,
            }

        yield {
            "type": "step",
            "step_type": "search",
            "description": f"Found {len(search_results)} sources",
            "status": "completed",
        }

        # Step 2: Analyze
        yield {
            "type": "step",
            "step_type": "analyze",
            "description": f"Analyzing sources ({depth_config['analysis_detail']})...",
            "status": "running",
        }

        llm = self._get_llm()
        sources_text = self._format_sources(search_results)

        analysis_prompt = f"""Analyze the following sources about: {query}

Sources:
{sources_text}

Provide a {depth_config['analysis_detail']} analysis covering:
1. Main themes and key findings
2. Areas of agreement and disagreement between sources
3. Gaps in the available information
4. Quality and reliability of sources"""

        try:
            analysis_response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=analysis_prompt),
            ])
            analysis_text = analysis_response.content
            logger.info("analysis_completed", query=query)
        except Exception as e:
            logger.error("analysis_failed", error=str(e))
            analysis_text = f"Analysis of '{query}' based on {len(search_results)} sources."

        yield {
            "type": "step",
            "step_type": "analyze",
            "description": "Source analysis complete",
            "status": "completed",
        }

        # Step 3: Synthesize (skip for QUICK depth)
        synthesis_text = ""
        if not depth_config["skip_synthesis"]:
            yield {
                "type": "step",
                "step_type": "synthesize",
                "description": "Synthesizing findings...",
                "status": "running",
            }

            synthesis_prompt = f"""Based on your analysis of sources about: {query}

Analysis:
{analysis_text}

Synthesize the key findings into a coherent narrative that:
1. Identifies the most important insights
2. Resolves contradictions where possible
3. Highlights actionable conclusions
4. Notes areas requiring further research"""

            try:
                synthesis_response = await llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=synthesis_prompt),
                ])
                synthesis_text = synthesis_response.content
                logger.info("synthesis_completed", query=query)
            except Exception as e:
                logger.error("synthesis_failed", error=str(e))
                synthesis_text = analysis_text

            yield {
                "type": "step",
                "step_type": "synthesize",
                "description": "Synthesis complete",
                "status": "completed",
            }

        # Step 4: Write report
        yield {
            "type": "step",
            "step_type": "write",
            "description": "Writing research report...",
            "status": "running",
        }

        structure_str = "\n".join(
            [f"{i + 1}. {section}" for i, section in enumerate(report_structure)]
        )

        combined_findings = synthesis_text if synthesis_text else analysis_text

        report_prompt = f"""Write a {depth_config['report_length']} research report on: {query}

Based on analysis and synthesis:
{combined_findings}

Sources used:
{sources_text}

Structure the report with these sections:
{structure_str}

Ensure the report:
- Is well-organized and easy to read
- Cites specific sources where appropriate
- Provides actionable insights
- Acknowledges limitations of the research"""

        try:
            async for chunk in llm.astream([
                SystemMessage(content=system_prompt),
                HumanMessage(content=report_prompt),
            ]):
                if chunk.content:
                    yield {"type": "token", "content": chunk.content}
        except Exception as e:
            logger.error("report_generation_failed", error=str(e))
            yield {"type": "token", "content": f"\n\nError generating report: {str(e)}"}

        yield {
            "type": "step",
            "step_type": "write",
            "description": "Report complete",
            "status": "completed",
        }

        logger.info("research_completed", query=query)

    def _format_sources(self, results: list[SearchResult]) -> str:
        """Format search results for LLM prompts."""
        formatted = []
        for i, result in enumerate(results, 1):
            score_str = f" (relevance: {result.relevance_score:.2f})" if result.relevance_score else ""
            formatted.append(f"{i}. [{result.title}]({result.url}){score_str}\n   {result.snippet}")
        return "\n\n".join(formatted)

    def _get_mock_results(self, query: str, config: dict) -> list[SearchResult]:
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


# Global instance
research_agent = ResearchAgent()
