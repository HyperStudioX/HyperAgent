"""Subagent graphs for the multi-agent system."""

from app.agents.subagents.chat import chat_subgraph
from app.agents.subagents.code import code_subgraph
from app.agents.subagents.data import data_subgraph
from app.agents.subagents.research import research_subgraph
from app.agents.subagents.writing import writing_subgraph

__all__ = [
    "chat_subgraph",
    "code_subgraph",
    "data_subgraph",
    "research_subgraph",
    "writing_subgraph",
]
