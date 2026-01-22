"""LLM-based routing logic for the multi-agent system."""

import json
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AgentType, SupervisorState
from app.core.logging import get_logger
from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier

logger = get_logger(__name__)

# Structured JSON-based router prompt for more reliable parsing
ROUTER_PROMPT = """You are a routing assistant that determines which specialized agent should handle a user query.

Available agents:
1. chat - For general conversation, simple Q&A, greetings, and casual interactions
2. research - For in-depth research tasks requiring web search, analysis, and comprehensive reports
3. code - For code execution, writing scripts, debugging, and programming tasks
4. writing - For long-form content creation like articles, documentation, essays, and creative writing
5. data - For data analysis, CSV/JSON processing, statistics, and data visualization
6. image - For image generation, creating pictures, artwork, illustrations, and visual content
7. computer - For tasks requiring visual desktop interaction, browser automation, form filling, clicking buttons, or interacting with web applications as a human would

Analyze the user's query and respond with a JSON object containing:
- "agent": The agent name (chat, research, code, writing, data, image, or computer)
- "confidence": Your confidence level (0.0 to 1.0)
- "reason": Brief explanation for your choice

Respond with ONLY the JSON object, no other text.

Examples:
Query: "Hello, how are you?"
{"agent": "chat", "confidence": 0.95, "reason": "Simple greeting requiring conversational response"}

Query: "Research the latest AI developments in 2024"
{"agent": "research", "confidence": 0.9, "reason": "Requires web search and comprehensive analysis"}

Query: "Write a Python function to sort a list"
{"agent": "code", "confidence": 0.95, "reason": "Programming task requiring code generation"}

Query: "Write a blog post about climate change"
{"agent": "writing", "confidence": 0.85, "reason": "Long-form content creation"}

Query: "Analyze this CSV data and find trends"
{"agent": "data", "confidence": 0.9, "reason": "Data analysis task"}

Query: "Generate an image of a sunset over mountains"
{"agent": "image", "confidence": 0.95, "reason": "Image generation request"}

Query: "Create a picture of a cute robot"
{"agent": "image", "confidence": 0.95, "reason": "Requesting visual content creation"}

Query: "Go to amazon.com and find the price of iPhone 15"
{"agent": "computer", "confidence": 0.95, "reason": "Requires browsing a website and interacting with it"}

Query: "Fill out the contact form on example.com"
{"agent": "computer", "confidence": 0.95, "reason": "Requires form interaction on a website"}

Query: "Take a screenshot of the Google homepage"
{"agent": "computer", "confidence": 0.9, "reason": "Requires visual browser interaction"}

Query: "Click the login button and sign in to my account"
{"agent": "computer", "confidence": 0.95, "reason": "Requires clicking and typing in a browser"}"""

# Fallback prompt for legacy parsing (backward compatibility)
ROUTER_PROMPT_LEGACY = """You are a routing assistant that determines which specialized agent should handle a user query.

Available agents:
1. CHAT - For general conversation, simple Q&A, greetings, and casual interactions
2. RESEARCH - For in-depth research tasks requiring web search, analysis, and comprehensive reports
3. CODE - For code execution, writing scripts, debugging, and programming tasks
4. WRITING - For long-form content creation like articles, documentation, essays, and creative writing
5. DATA - For data analysis, CSV/JSON processing, statistics, and data visualization
6. IMAGE - For image generation, creating pictures, artwork, illustrations, and visual content
7. COMPUTER - For tasks requiring visual desktop interaction, browser automation, form filling, or clicking buttons

Analyze the user's query and respond with ONLY the agent name (CHAT, RESEARCH, CODE, WRITING, DATA, IMAGE, or COMPUTER) followed by a brief reason.

Format your response exactly as:
AGENT: <agent_name>
REASON: <brief_explanation>"""


@dataclass
class RoutingResult:
    """Result from the routing decision."""

    agent: AgentType
    reason: str
    confidence: float = 1.0
    is_low_confidence: bool = False


# Confidence threshold - below this, routing is considered low confidence
ROUTING_CONFIDENCE_THRESHOLD = 0.5


# Agent name mapping (handles both lowercase and uppercase)
AGENT_NAME_MAP = {
    "chat": AgentType.CHAT,
    "research": AgentType.RESEARCH,
    "code": AgentType.CODE,
    "writing": AgentType.WRITING,
    "data": AgentType.DATA,
    "image": AgentType.IMAGE,
    "computer": AgentType.COMPUTER,
    "CHAT": AgentType.CHAT,
    "RESEARCH": AgentType.RESEARCH,
    "CODE": AgentType.CODE,
    "WRITING": AgentType.WRITING,
    "DATA": AgentType.DATA,
    "IMAGE": AgentType.IMAGE,
    "COMPUTER": AgentType.COMPUTER,
}


def parse_router_response_json(response: str) -> RoutingResult | None:
    """Parse JSON-formatted router response.

    Args:
        response: Raw LLM response string (expected to be JSON)

    Returns:
        RoutingResult if parsing succeeds, None otherwise
    """
    try:
        # Clean up response (remove markdown code blocks if present)
        clean_response = response.strip()
        if clean_response.startswith("```"):
            # Remove code block markers
            lines = clean_response.split("\n")
            clean_response = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        data = json.loads(clean_response)

        agent_name = data.get("agent", "chat").lower()
        agent_type = AGENT_NAME_MAP.get(agent_name, AgentType.CHAT)
        confidence = float(data.get("confidence", 0.8))

        return RoutingResult(
            agent=agent_type,
            reason=data.get("reason", ""),
            confidence=confidence,
            is_low_confidence=confidence < ROUTING_CONFIDENCE_THRESHOLD,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.debug("json_router_parse_failed", error=str(e))
        return None


def parse_router_response_legacy(response: str) -> RoutingResult:
    """Parse legacy text-formatted router response.

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
            agent_part = line.split(":", 1)[1].strip()
            # Handle both "CHAT" and "AGENT: CHAT | REASON: ..." formats
            if "|" in agent_part:
                parts = [part.strip() for part in agent_part.split("|")]
                agent_part = parts[0].upper()
                for part in parts[1:]:
                    if part.upper().startswith("REASON:"):
                        reason = part.split(":", 1)[1].strip()
            else:
                agent_part = agent_part.upper()
            # Map to AgentType
            agent_type = AGENT_NAME_MAP.get(agent_part, AgentType.CHAT)
            agent_str = agent_type.value
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    return RoutingResult(agent=AgentType(agent_str), reason=reason)


def parse_router_response(response: str) -> RoutingResult:
    """Parse the LLM router response into a structured result.

    Attempts JSON parsing first, falls back to legacy text parsing.

    Args:
        response: Raw LLM response string

    Returns:
        RoutingResult with agent type and reason
    """
    # Try JSON parsing first
    result = parse_router_response_json(response)
    if result:
        return result

    # Fall back to legacy parsing
    return parse_router_response_legacy(response)


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

    # LLM-based routing (use FLASH tier for fast, cost-efficient routing)
    query = state.get("query", "")
    provider = state.get("provider")
    llm = llm_service.get_llm_for_tier(ModelTier.FLASH, provider=provider)

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=ROUTER_PROMPT),
                HumanMessage(content=f"Query: {query}"),
            ]
        )
        result = parse_router_response(response.content)

        # Log with confidence level
        log_method = logger.warning if result.is_low_confidence else logger.info
        log_method(
            "routing_llm",
            query=query[:50],
            agent=result.agent.value,
            reason=result.reason,
            confidence=result.confidence,
            is_low_confidence=result.is_low_confidence,
        )

        # Build routing event with confidence info
        routing_event = {
            "type": "routing",
            "agent": result.agent.value,
            "reason": result.reason,
            "confidence": result.confidence,
        }

        # Add low confidence warning to event if applicable
        if result.is_low_confidence:
            routing_event["low_confidence"] = True
            routing_event["message"] = (
                f"Low confidence ({result.confidence:.0%}) routing to {result.agent.value}. "
                "If the response doesn't match your intent, try rephrasing your query."
            )

        return {
            "selected_agent": result.agent.value,
            "routing_reason": result.reason,
            "routing_confidence": result.confidence,
            "events": [routing_event],
        }
    except Exception as e:
        logger.error("routing_failed", error=str(e))
        # Default to chat on routing failure
        return {
            "selected_agent": AgentType.CHAT.value,
            "routing_reason": f"Default (routing error: {str(e)})",
            "routing_confidence": 0.0,
            "events": [
                {
                    "type": "routing",
                    "agent": AgentType.CHAT.value,
                    "reason": "Default due to routing error",
                    "confidence": 0.0,
                }
            ],
        }
