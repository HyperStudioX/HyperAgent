"""LLM-based routing logic for the multi-agent system."""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AgentType, SupervisorState
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

ROUTER_PROMPT = """You are a routing assistant that determines which specialized agent should handle a user query.

Available agents:
1. CHAT - For general conversation, simple Q&A, greetings, and casual interactions
2. RESEARCH - For in-depth research tasks requiring web search, analysis, and comprehensive reports
3. CODE - For code execution, writing scripts, debugging, and programming tasks
4. WRITING - For long-form content creation like articles, documentation, essays, and creative writing
5. DATA - For data analysis, CSV/JSON processing, statistics, and data visualization

Analyze the user's query and respond with ONLY the agent name (CHAT, RESEARCH, CODE, WRITING, or DATA) followed by a brief reason.

Format your response exactly as:
AGENT: <agent_name>
REASON: <brief_explanation>

Examples:
- "Hello, how are you?" → AGENT: CHAT | REASON: Simple greeting requiring conversational response
- "Research the latest AI developments in 2024" → AGENT: RESEARCH | REASON: Requires web search and comprehensive analysis
- "Write a Python function to sort a list" → AGENT: CODE | REASON: Programming task requiring code generation
- "Write a blog post about climate change" → AGENT: WRITING | REASON: Long-form content creation
- "Analyze this CSV data and find trends" → AGENT: DATA | REASON: Data analysis task"""


@dataclass
class RoutingResult:
    """Result from the routing decision."""

    agent: AgentType
    reason: str


def parse_router_response(response: str) -> RoutingResult:
    """Parse the LLM router response into a structured result.

    Args:
        response: Raw LLM response string

    Returns:
        RoutingResult with agent type and reason
    """
    lines = response.strip().split("\n")
    agent_str = AgentType.CHAT.value  # Default
    reason = "Default routing"

    for line in lines:
        line = line.strip()
        if line.upper().startswith("AGENT:"):
            agent_part = line.split(":", 1)[1].strip().upper()
            # Handle both "CHAT" and "AGENT: CHAT | REASON: ..." formats
            if "|" in agent_part:
                agent_part = agent_part.split("|")[0].strip()
            # Map to AgentType
            agent_map = {
                "CHAT": AgentType.CHAT,
                "RESEARCH": AgentType.RESEARCH,
                "CODE": AgentType.CODE,
                "WRITING": AgentType.WRITING,
                "DATA": AgentType.DATA,
            }
            agent_str = agent_map.get(agent_part, AgentType.CHAT).value
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    return RoutingResult(agent=AgentType(agent_str), reason=reason)


async def route_query(state: SupervisorState) -> dict:
    """Route a query to the appropriate agent.

    If an explicit mode is provided in the state, use that directly.
    Otherwise, use LLM-based routing to determine the best agent.

    Args:
        state: Current supervisor state with query and optional mode

    Returns:
        Dict with selected_agent and routing_reason
    """
    # Check for explicit mode override
    explicit_mode = state.get("mode")
    if explicit_mode:
        try:
            agent_type = AgentType(explicit_mode)
            logger.info(
                "routing_explicit",
                query=state.get("query", "")[:50],
                agent=agent_type.value,
            )
            return {
                "selected_agent": agent_type.value,
                "routing_reason": "Explicit mode selection",
                "events": [
                    {
                        "type": "routing",
                        "agent": agent_type.value,
                        "reason": "Explicit mode selection",
                    }
                ],
            }
        except ValueError:
            logger.warning("invalid_explicit_mode", mode=explicit_mode)
            # Fall through to LLM routing

    # LLM-based routing
    query = state.get("query", "")
    llm = llm_service.get_llm()

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=ROUTER_PROMPT),
                HumanMessage(content=f"Query: {query}"),
            ]
        )
        result = parse_router_response(response.content)

        logger.info(
            "routing_llm",
            query=query[:50],
            agent=result.agent.value,
            reason=result.reason,
        )

        return {
            "selected_agent": result.agent.value,
            "routing_reason": result.reason,
            "events": [
                {
                    "type": "routing",
                    "agent": result.agent.value,
                    "reason": result.reason,
                }
            ],
        }
    except Exception as e:
        logger.error("routing_failed", error=str(e))
        # Default to chat on routing failure
        return {
            "selected_agent": AgentType.CHAT.value,
            "routing_reason": f"Default (routing error: {str(e)})",
            "events": [
                {
                    "type": "routing",
                    "agent": AgentType.CHAT.value,
                    "reason": "Default due to routing error",
                }
            ],
        }
