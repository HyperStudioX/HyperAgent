"""Subagent graphs for the multi-agent system."""

from app.agents.subagents.research import research_subgraph
from app.agents.subagents.task import task_subgraph

__all__ = [
    "task_subgraph",
    "research_subgraph",
]
