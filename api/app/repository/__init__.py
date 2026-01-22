"""Repository package for data persistence.

This package contains repositories for different domain entities.
"""

from app.repository.deep_research_repository import (
    DeepResearchRepository,
    deep_research_repository,
)

__all__ = [
    "DeepResearchRepository",
    "deep_research_repository",
]
