"""Search service using Tavily API."""

from dataclasses import dataclass

from tavily import AsyncTavilyClient

from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario
from app.agents.scenarios import get_scenario_config

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    content: str | None = None
    relevance_score: float | None = None


# Depth configuration: number of results to fetch
DEPTH_CONFIG = {
    ResearchDepth.QUICK: {"max_results": 3, "search_depth": "basic"},
    ResearchDepth.STANDARD: {"max_results": 5, "search_depth": "basic"},
    ResearchDepth.DEEP: {"max_results": 10, "search_depth": "advanced"},
}


class SearchService:
    """Service for performing web searches using Tavily."""

    def __init__(self):
        self._client: AsyncTavilyClient | None = None

    def _get_client(self) -> AsyncTavilyClient:
        """Get or create Tavily client."""
        if not settings.tavily_api_key:
            raise ValueError("Tavily API key not configured")
        if not self._client:
            self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        return self._client

    async def search(
        self,
        query: str,
        depth: ResearchDepth = ResearchDepth.STANDARD,
        scenario: ResearchScenario = ResearchScenario.ACADEMIC,
    ) -> list[SearchResult]:
        """Perform a search using Tavily API.

        Args:
            query: Search query
            depth: Research depth affecting number of results
            scenario: Research scenario affecting search focus

        Returns:
            List of search results
        """
        client = self._get_client()
        config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG[ResearchDepth.STANDARD])
        scenario_config = get_scenario_config(scenario)

        # Enhance query with scenario-specific focus
        search_focus = scenario_config.get("search_focus", [])
        enhanced_query = query
        if search_focus:
            # Add the primary focus term to help target results
            enhanced_query = f"{query} {search_focus[0]}"

        logger.info(
            "search_started",
            query=query,
            enhanced_query=enhanced_query,
            depth=depth.value,
            scenario=scenario.value,
            max_results=config["max_results"],
        )

        try:
            response = await client.search(
                query=enhanced_query,
                max_results=config["max_results"],
                search_depth=config["search_depth"],
                include_raw_content=depth == ResearchDepth.DEEP,
            )

            results = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:500] if item.get("content") else "",
                        content=item.get("raw_content") if depth == ResearchDepth.DEEP else None,
                        relevance_score=item.get("score"),
                    )
                )

            logger.info(
                "search_completed",
                query=query,
                results_count=len(results),
            )
            return results

        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            raise


# Global instance
search_service = SearchService()
