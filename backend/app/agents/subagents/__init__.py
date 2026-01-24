"""Subagent graphs for the multi-agent system."""

from app.agents.subagents.chat import chat_subgraph
from app.agents.subagents.data import data_subgraph
from app.agents.subagents.research import research_subgraph

__all__ = [
    "chat_subgraph",
    "data_subgraph",
    "research_subgraph",
]
