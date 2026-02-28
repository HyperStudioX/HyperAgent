"""Multi-agent system with LangGraph-based orchestration.

This module provides a supervisor-based multi-agent architecture where
different specialized agents handle different types of tasks.

Available agents:
- Task: General-purpose handler with skills (images, writing, code, data, etc.)
- Research: Deep research with web search and analysis

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
# Routing
from app.agents.routing import RoutingResult, route_query
from app.agents.state import (
    AgentType,
    ResearchState,
    SupervisorState,
    TaskState,
)

# Subagents
from app.agents.subagents import (
    research_subgraph,
    task_subgraph,
)

# Supervisor
from app.agents.supervisor import (
    AgentSupervisor,
    agent_supervisor,
    create_supervisor_graph,
)

__all__ = [
    # State types
    "AgentType",
    "SupervisorState",
    "TaskState",
    "ResearchState",
    # Routing
    "route_query",
    "RoutingResult",
    # Supervisor
    "AgentSupervisor",
    "agent_supervisor",
    "create_supervisor_graph",
    # Subagents
    "task_subgraph",
    "research_subgraph",
]
