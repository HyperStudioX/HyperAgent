"""Handoff tools for agent-to-agent delegation.

This module implements the Manus/LangGraph swarm pattern for multi-agent collaboration.
Agents can delegate tasks to other specialized agents using handoff tools.
"""

from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from app.agents.state import AgentType
from app.core.logging import get_logger

logger = get_logger(__name__)


class HandoffInput(BaseModel):
    """Input schema for handoff tools."""

    task_description: str = Field(
        ...,
        description="A clear description of what the target agent should accomplish.",
    )
    context: str = Field(
        default="",
        description="Additional context or information to help the target agent.",
    )


# Define which agents can delegate to which other agents
HANDOFF_MATRIX: dict[str, list[str]] = {
    AgentType.CHAT.value: [
        AgentType.RESEARCH.value,
        AgentType.CODE.value,
        AgentType.WRITING.value,
        AgentType.DATA.value,
    ],
    AgentType.RESEARCH.value: [
        AgentType.CODE.value,
        AgentType.DATA.value,
    ],
    AgentType.WRITING.value: [
        AgentType.RESEARCH.value,
    ],
    AgentType.CODE.value: [
        AgentType.DATA.value,
    ],
    AgentType.DATA.value: [
        AgentType.CODE.value,
    ],
}

# Agent descriptions for handoff tool docstrings
AGENT_DESCRIPTIONS: dict[str, str] = {
    AgentType.CHAT.value: "General conversation and simple Q&A",
    AgentType.RESEARCH.value: "In-depth web research, analysis, and comprehensive reports",
    AgentType.CODE.value: "Code generation, debugging, and programming tasks",
    AgentType.WRITING.value: "Long-form content creation, articles, documentation",
    AgentType.DATA.value: "Data analysis, CSV/JSON processing, statistics, visualization",
}


def create_handoff_tool(
    source_agent: str,
    target_agent: str,
    description: str | None = None,
) -> BaseTool:
    """Create a handoff tool for transferring control to another agent.

    This creates a tool that, when called by the source agent, signals
    that control should be transferred to the target agent with the
    specified task and context.

    Args:
        source_agent: The agent that will use this tool
        target_agent: The agent to transfer control to
        description: Optional custom description for the tool

    Returns:
        A LangChain BaseTool configured for handoff
    """
    if description is None:
        description = f"Transfer this task to the {target_agent} agent for {AGENT_DESCRIPTIONS.get(target_agent, 'specialized processing')}."

    tool_name = f"handoff_to_{target_agent}"

    @tool(args_schema=HandoffInput)
    def handoff_tool(task_description: str, context: str = "") -> dict[str, Any]:
        """Handoff to another agent."""
        logger.info(
            "handoff_requested",
            source=source_agent,
            target=target_agent,
            task=task_description[:100],
        )
        return {
            "handoff": True,
            "target_agent": target_agent,
            "task_description": task_description,
            "context": context,
            "source_agent": source_agent,
        }

    # Update the function metadata
    handoff_tool.name = tool_name
    handoff_tool.description = description

    return handoff_tool


def get_handoff_tools_for_agent(agent_type: str) -> list[BaseTool]:
    """Get all handoff tools available for a specific agent.

    Args:
        agent_type: The agent type (e.g., "chat", "research")

    Returns:
        List of handoff tools the agent can use
    """
    allowed_targets = HANDOFF_MATRIX.get(agent_type, [])
    tools = [
        create_handoff_tool(source_agent=agent_type, target_agent=target)
        for target in allowed_targets
    ]

    logger.debug(
        "handoff_tools_created",
        agent=agent_type,
        targets=allowed_targets,
    )

    return tools


def is_handoff_response(tool_result: Any) -> bool:
    """Check if a tool result indicates a handoff request.

    Args:
        tool_result: The result from a tool call

    Returns:
        True if this is a handoff request
    """
    if isinstance(tool_result, dict):
        return tool_result.get("handoff", False)
    return False


def parse_handoff_response(tool_result: dict) -> tuple[str, str, str]:
    """Parse a handoff response to extract target and task info.

    Args:
        tool_result: The handoff tool result dict

    Returns:
        Tuple of (target_agent, task_description, context)
    """
    return (
        tool_result.get("target_agent", ""),
        tool_result.get("task_description", ""),
        tool_result.get("context", ""),
    )


class HandoffManager:
    """Manages handoff state and prevents infinite loops.

    Tracks visited agents and enforces maximum handoff depth to prevent
    agents from bouncing tasks back and forth infinitely.
    """

    def __init__(self, max_handoffs: int = 3):
        """Initialize the handoff manager.

        Args:
            max_handoffs: Maximum number of handoffs allowed per request
        """
        self.max_handoffs = max_handoffs
        self.handoff_count = 0
        self.visited_agents: list[str] = []
        self.handoff_history: list[dict[str, Any]] = []

    def can_handoff(self, source_agent: str, target_agent: str) -> bool:
        """Check if a handoff from source to target is allowed.

        Args:
            source_agent: Current agent
            target_agent: Target agent for handoff

        Returns:
            True if handoff is allowed
        """
        # Check max handoffs
        if self.handoff_count >= self.max_handoffs:
            logger.warning(
                "max_handoffs_reached",
                count=self.handoff_count,
                max=self.max_handoffs,
            )
            return False

        # Check if target is in allowed list
        allowed_targets = HANDOFF_MATRIX.get(source_agent, [])
        if target_agent not in allowed_targets:
            logger.warning(
                "handoff_not_allowed",
                source=source_agent,
                target=target_agent,
                allowed=allowed_targets,
            )
            return False

        # Prevent immediate back-and-forth (A -> B -> A)
        if len(self.visited_agents) >= 2:
            if self.visited_agents[-2] == target_agent:
                logger.warning(
                    "handoff_loop_detected",
                    history=self.visited_agents,
                    target=target_agent,
                )
                return False

        return True

    def record_handoff(
        self,
        source_agent: str,
        target_agent: str,
        task_description: str,
        context: str = "",
    ) -> None:
        """Record a handoff for tracking.

        Args:
            source_agent: Agent handing off
            target_agent: Agent receiving the task
            task_description: Description of delegated task
            context: Additional context
        """
        self.handoff_count += 1
        self.visited_agents.append(target_agent)
        self.handoff_history.append({
            "from": source_agent,
            "to": target_agent,
            "task": task_description,
            "context": context,
        })
        logger.info(
            "handoff_recorded",
            count=self.handoff_count,
            history=[h["to"] for h in self.handoff_history],
        )

    def get_handoff_summary(self) -> str:
        """Get a summary of all handoffs that occurred.

        Returns:
            Human-readable summary of handoff chain
        """
        if not self.handoff_history:
            return "No handoffs occurred."

        parts = []
        for i, h in enumerate(self.handoff_history, 1):
            parts.append(f"{i}. {h['from']} → {h['to']}: {h['task'][:50]}...")
        return "\n".join(parts)

    def reset(self) -> None:
        """Reset the handoff state for a new request."""
        self.handoff_count = 0
        self.visited_agents = []
        self.handoff_history = []
