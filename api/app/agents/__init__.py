"""Multi-agent system with LangGraph-based orchestration.

This module provides a supervisor-based multi-agent architecture where
different specialized agents handle different types of tasks.

Available agents:
- Chat: General conversation and Q&A
- Research: Deep research with web search and analysis
- Code: Code generation and execution
- Writing: Long-form content creation
- Data: Data analysis (placeholder)

Usage:
    from app.agents import agent_supervisor

    # Streaming execution
    async for event in agent_supervisor.run(query="Hello"):
        print(event)

    # Non-streaming execution
    result = await agent_supervisor.invoke(query="Hello")

    # With explicit mode
    async for event in agent_supervisor.run(
        query="Research AI trends",
        mode="research",
        depth=ResearchDepth.FAST,
    ):
        print(event)
"""

# State definitions
from app.agents.state import (
    AgentType,
    ChatState,
    CodeState,
    DataAnalysisState,
    ResearchState,
    SupervisorState,
    WritingState,
)

# Routing
from app.agents.routing import route_query, RoutingResult

# Supervisor
from app.agents.supervisor import (
    AgentSupervisor,
    agent_supervisor,
    create_supervisor_graph,
    supervisor_graph,
)

# Subagents
from app.agents.subagents import (
    chat_subgraph,
    code_subgraph,
    research_subgraph,
    writing_subgraph,
)

__all__ = [
    # State types
    "AgentType",
    "SupervisorState",
    "ChatState",
    "ResearchState",
    "CodeState",
    "WritingState",
    "DataAnalysisState",
    # Routing
    "route_query",
    "RoutingResult",
    # Supervisor
    "AgentSupervisor",
    "agent_supervisor",
    "create_supervisor_graph",
    "supervisor_graph",
    # Subagents
    "chat_subgraph",
    "research_subgraph",
    "code_subgraph",
    "writing_subgraph",
]
