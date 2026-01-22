"""Search service using Tavily API."""

import hashlib
import time
from dataclasses import dataclass

from tavily import AsyncTavilyClient

from app.agents.scenarios import get_scenario_config
from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import ResearchDepth, ResearchScenario
from app.middleware.circuit_breaker import CircuitBreakerOpen, get_tavily_breaker

logger = get_logger(__name__)

# Cache configuration
CACHE_TTL_SECONDS = 300  # 5 minutes
CACHE_MAX_SIZE = 1000  # Maximum number of cached queries


@dataclass
class CacheEntry:
    """Cache entry with expiration timestamp."""

    results: list
    expires_at: float


class SearchCache:
    """Simple in-memory TTL cache for search results."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS, max_size: int = CACHE_MAX_SIZE):
        self._cache: dict[str, CacheEntry] = {}
        self._ttl = ttl
        self._max_size = max_size

    def _make_key(self, query: str, max_results: int, search_depth: str, include_raw_content: bool) -> str:
        """Generate cache key from search parameters."""
        key_string = f"{query}|{max_results}|{search_depth}|{include_raw_content}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, query: str, max_results: int, search_depth: str, include_raw_content: bool) -> list | None:
        """Get cached results if not expired."""
        key = self._make_key(query, max_results, search_depth, include_raw_content)
        entry = self._cache.get(key)

        if entry is None:
            return None

        if time.time() > entry.expires_at:
            # Entry expired, remove it
            del self._cache[key]
            return None

        logger.debug("search_cache_hit", query=query[:50])
        return entry.results

    def set(self, query: str, max_results: int, search_depth: str, include_raw_content: bool, results: list) -> None:
        """Cache search results with TTL."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self._max_size:
            self._evict_expired()
            # If still full, remove oldest entries
            if len(self._cache) >= self._max_size:
                oldest_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k].expires_at)[:100]
                for key in oldest_keys:
                    del self._cache[key]

        key = self._make_key(query, max_results, search_depth, include_raw_content)
        self._cache[key] = CacheEntry(
            results=results,
            expires_at=time.time() + self._ttl,
        )
        logger.debug("search_cache_set", query=query[:50], cache_size=len(self._cache))

    def _evict_expired(self) -> None:
        """Remove all expired entries."""
        current_time = time.time()
        expired_keys = [k for k, v in self._cache.items() if current_time > v.expires_at]
        for key in expired_keys:
            del self._cache[key]

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


# Global cache instance
_search_cache = SearchCache()


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
    ResearchDepth.FAST: {"max_results": 3, "search_depth": "basic"},
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

    async def search_raw(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_raw_content: bool = False,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        """Perform a raw search using Tavily API with caching.

        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: "basic" or "advanced"
            include_raw_content: Whether to include full page content
            use_cache: Whether to use cached results (default True)

        Returns:
            List of search results
        """
        # Check cache first
        if use_cache:
            cached = _search_cache.get(query, max_results, search_depth, include_raw_content)
            if cached is not None:
                logger.info(
                    "search_raw_cache_hit",
                    query=query[:50],
                    results_count=len(cached),
                )
                return cached

        client = self._get_client()
        breaker = get_tavily_breaker()

        logger.info(
            "search_raw_started",
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        try:
            async with breaker.call():
                response = await client.search(
                    query=query,
                    max_results=max_results,
                    search_depth=search_depth,
                    include_raw_content=include_raw_content,
                )

            results = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", "Untitled"),
                        url=item.get("url", ""),
                        snippet=item.get("content", "")[:500] if item.get("content") else "",
                        content=item.get("raw_content") if include_raw_content else None,
                        relevance_score=item.get("score"),
                    )
                )

            # Cache the results
            if use_cache:
                _search_cache.set(query, max_results, search_depth, include_raw_content, results)

            logger.info(
                "search_raw_completed",
                query=query,
                results_count=len(results),
            )
            return results

        except CircuitBreakerOpen as e:
            logger.warning(
                "search_raw_circuit_open",
                query=query,
                service="tavily",
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error("search_raw_failed", query=query, error=str(e))
            raise

    async def search(
        self,
        query: str,
        depth: ResearchDepth = ResearchDepth.FAST,
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
        config = DEPTH_CONFIG.get(depth, DEPTH_CONFIG[ResearchDepth.FAST])
        scenario_config = get_scenario_config(scenario)

        # Enhance query with scenario-specific focus
        search_focus = scenario_config.get("search_focus", [])
        enhanced_query = query
        if search_focus:
            # Add the primary focus term to help target results
            enhanced_query = f"{query} {search_focus[0]}"

        breaker = get_tavily_breaker()

        logger.info(
            "search_started",
            query=query,
            enhanced_query=enhanced_query,
            depth=depth.value,
            scenario=scenario.value,
            max_results=config["max_results"],
        )

        try:
            async with breaker.call():
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

        except CircuitBreakerOpen as e:
            logger.warning(
                "search_circuit_open",
                query=query,
                service="tavily",
                retry_after=e.retry_after,
            )
            raise
        except Exception as e:
            logger.error("search_failed", query=query, error=str(e))
            raise


# Global instance
search_service = SearchService()
