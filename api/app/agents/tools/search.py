"""Web search tool for LangGraph agents."""

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.services.search import search_service, SearchResult

logger = get_logger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""

    query: str = Field(description="The search query to execute")
    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to return (1-20)",
    )
    search_depth: Literal["basic", "advanced"] = Field(
        default="basic",
        description="Search depth: 'basic' for quick results, 'advanced' for comprehensive search",
    )


@tool(args_schema=WebSearchInput)
async def web_search(
    query: str,
    max_results: int = 5,
    search_depth: Literal["basic", "advanced"] = "basic",
) -> str:
    """Search the web for current information on any topic.

    Use this tool when you need to find up-to-date information, verify facts,
    or gather data from the internet. Returns relevant web pages with titles,
    URLs, and content snippets.

    Args:
        query: The search query to execute
        max_results: Maximum number of results (1-20)
        search_depth: 'basic' for quick results, 'advanced' for comprehensive search

    Returns:
        JSON string with formatted results and structured data
    """
    logger.info(
        "web_search_tool_invoked",
        query=query,
        max_results=max_results,
        search_depth=search_depth,
    )

    try:
        results = await search_service.search_raw(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        if not results:
            return json.dumps({
                "formatted": f"No results found for: {query}",
                "results": [],
                "query": query,
            })

        return json.dumps({
            "formatted": _format_results(results),
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "content": r.content,
                    "relevance_score": r.relevance_score,
                }
                for r in results
            ],
            "query": query,
        })

    except ValueError as e:
        logger.warning("web_search_api_not_configured", error=str(e))
        return json.dumps({
            "formatted": f"Search service unavailable: {e}",
            "results": [],
            "query": query,
            "error": str(e),
        })
    except Exception as e:
        logger.error("web_search_failed", query=query, error=str(e))
        return json.dumps({
            "formatted": f"Search failed: {e}",
            "results": [],
            "query": query,
            "error": str(e),
        })


def _format_results(results: list[SearchResult]) -> str:
    """Format search results for LLM consumption."""
    formatted = []
    for i, result in enumerate(results, 1):
        parts = [f"[{i}] {result.title}"]
        parts.append(f"    URL: {result.url}")
        if result.snippet:
            parts.append(f"    {result.snippet}")
        if result.relevance_score:
            parts.append(f"    Relevance: {result.relevance_score:.2f}")
        formatted.append("\n".join(parts))

    return "\n\n".join(formatted)


def parse_search_results(tool_output: str) -> list[SearchResult]:
    """Parse tool output JSON back into SearchResult objects.

    Args:
        tool_output: JSON string from web_search tool

    Returns:
        List of SearchResult objects
    """
    try:
        data = json.loads(tool_output)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
                content=r.get("content"),
                relevance_score=r.get("relevance_score"),
            )
            for r in data.get("results", [])
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("parse_search_results_failed", error=str(e))
        return []
