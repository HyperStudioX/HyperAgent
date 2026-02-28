"""Tool Search - meta-tool for discovering available tools.

Enables lazy tool loading: instead of binding all ~35 tools upfront,
the agent starts with core tools + search_tools. When the agent needs
a specialized tool, it calls search_tools to discover it by description.
This reduces context window usage by ~85% for tool descriptions.
"""

import json
from difflib import SequenceMatcher

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolMetadata:
    """Lightweight metadata about a tool (no full schema)."""

    def __init__(self, name: str, description: str, category: str):
        self.name = name
        self.description = description  # First 200 chars of tool description
        self.category = category


class ToolMetadataRegistry:
    """Registry of tool metadata for search."""

    def __init__(self):
        self._tools: dict[str, ToolMetadata] = {}

    def register(self, name: str, description: str, category: str):
        """Register a tool's metadata."""
        self._tools[name] = ToolMetadata(
            name=name,
            description=description[:200],
            category=category,
        )

    def search(self, query: str, limit: int = 5) -> list[ToolMetadata]:
        """Search tools by keyword matching against name and description.

        Uses simple keyword matching + sequence similarity for ranking.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for tool_meta in self._tools.values():
            # Score based on name match, keyword overlap, and sequence similarity
            name_lower = tool_meta.name.lower()
            desc_lower = tool_meta.description.lower()
            cat_lower = tool_meta.category.lower()

            score = 0.0

            # Exact name match
            if query_lower == name_lower:
                score += 10.0
            # Partial name match
            elif query_lower in name_lower or name_lower in query_lower:
                score += 5.0

            # Category match
            if query_lower in cat_lower or cat_lower in query_lower:
                score += 3.0

            # Keyword overlap with description
            desc_words = set(desc_lower.split())
            overlap = query_words & desc_words
            score += len(overlap) * 2.0

            # Sequence similarity
            score += SequenceMatcher(None, query_lower, name_lower).ratio() * 2.0
            score += SequenceMatcher(None, query_lower, desc_lower[:50]).ratio()

            if score > 0.5:
                scored.append((score, tool_meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [meta for _, meta in scored[:limit]]

    def get_all(self) -> list[ToolMetadata]:
        """Get all registered tool metadata."""
        return list(self._tools.values())


# Module-level singleton
_metadata_registry = ToolMetadataRegistry()


def get_tool_metadata_registry() -> ToolMetadataRegistry:
    """Get the global tool metadata registry."""
    return _metadata_registry


def populate_registry_from_catalog():
    """Populate the metadata registry from the tool catalog.

    Called once at startup to index all tools.
    """
    from app.agents.tools.registry import TOOL_CATALOG

    for category, tools in TOOL_CATALOG.items():
        for t in tools:
            _metadata_registry.register(
                name=t.name,
                description=t.description or "",
                category=category.value,
            )
    logger.info("tool_metadata_populated", count=len(_metadata_registry._tools))


class SearchToolsInput(BaseModel):
    """Input for search_tools."""

    query: str = Field(
        ...,
        description=(
            "Keyword or description of the tool you need "
            "(e.g., 'file editing', 'browser automation', 'deploy')"
        ),
    )

    class Config:
        json_schema_extra = {"examples": [{"query": "file read write"}]}


@tool(args_schema=SearchToolsInput)
def search_tools(query: str) -> str:
    """Search for available tools by keyword or description.

    Use this when you need a specialized tool that isn't in your current toolset.
    Returns matching tool names and descriptions so you can request them.

    Examples:
    - "file" -> finds file_read, file_write, file_str_replace, etc.
    - "browser" -> finds browser_navigate, browser_click, etc.
    - "deploy" -> finds deploy_expose_port, deploy_get_url
    - "shell" -> finds shell_exec, shell_view, etc.
    """
    results = _metadata_registry.search(query, limit=8)

    if not results:
        return json.dumps({
            "matches": [],
            "message": "No tools found matching your query. Try different keywords.",
        })

    matches = [
        {
            "name": r.name,
            "description": r.description,
            "category": r.category,
        }
        for r in results
    ]

    return json.dumps({
        "matches": matches,
        "message": f"Found {len(matches)} matching tools. These tools are available for use.",
    })
