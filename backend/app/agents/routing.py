"""LLM-based routing logic for the multi-agent system."""

import json
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AgentType, SupervisorState
from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger

logger = get_logger(__name__)

# Structured JSON-based router prompt for more reliable parsing
ROUTER_PROMPT = """You are a routing assistant that determines which specialized agent should handle a user query.

Available agents:
1. chat - Primary agent for most tasks: conversation, Q&A, image generation, writing, coding, app building, and general requests. Has powerful skills for specialized tasks.
2. research - ONLY for deep, comprehensive research requiring extensive web search, multi-source analysis, and detailed reports
3. data - ONLY for data analytics: CSV/JSON processing, statistical analysis, and data visualization

IMPORTANT: Route almost everything to CHAT agent. It has skills for:
- Image generation (image_generation skill)
- Code generation (code_generation skill)
- Code review (code_review skill)
- Code execution (execute_code tool)
- App building (app_builder skill)
- Web search (web_search tool)
- Quick research (web_research skill)

Route to specialized agents ONLY when:
- RESEARCH: Comprehensive multi-step research with synthesis and detailed analysis
- DATA: Data analytics, CSV processing, statistical analysis, or data visualization

Analyze the user's query and respond with a JSON object containing:
- "agent": The agent name (chat, research, or data)
- "confidence": Your confidence level (0.0 to 1.0)
- "reason": Brief explanation for your choice

Respond with ONLY the JSON object, no other text.

Examples:
Query: "Hello, how are you?"
{"agent": "chat", "confidence": 0.95, "reason": "General conversation"}

Query: "Research and write a comprehensive report on AI developments in 2024 with citations"
{"agent": "research", "confidence": 0.95, "reason": "Deep research requiring multi-source analysis and detailed report"}

Query: "What are the latest AI developments?"
{"agent": "chat", "confidence": 0.9, "reason": "Simple question - chat can search and answer"}

Query: "Write a Python function to sort a list"
{"agent": "chat", "confidence": 0.95, "reason": "Code generation - chat has code_generation skill"}

Query: "Write and execute Python code to test this algorithm"
{"agent": "chat", "confidence": 0.95, "reason": "Code task - chat has code skills and execute_code tool"}

Query: "Review this code for bugs"
{"agent": "chat", "confidence": 0.95, "reason": "Code review - chat has code_review skill"}

Query: "Write a blog post about climate change"
{"agent": "chat", "confidence": 0.95, "reason": "Writing task - chat handles writing directly"}

Query: "Write an email to my team"
{"agent": "chat", "confidence": 0.95, "reason": "Writing task - chat handles writing directly"}

Query: "Analyze this CSV file and create visualizations of the trends"
{"agent": "data", "confidence": 0.95, "reason": "Data analytics and visualization task"}

Query: "Generate an image of a sunset over mountains"
{"agent": "chat", "confidence": 0.95, "reason": "Image generation - chat has image_generation skill"}

Query: "Go to amazon.com and find the price of iPhone 15"
{"agent": "chat", "confidence": 0.95, "reason": "Browser automation - chat agent has browser tools"}

Query: "Fill out the contact form on example.com"
{"agent": "chat", "confidence": 0.95, "reason": "Form interaction - chat agent has browser tools"}

Query: "Generate a picture of a cat"
{"agent": "chat", "confidence": 0.95, "reason": "Image generation - chat has image_generation skill"}

Query: "Create a detailed academic research paper on quantum computing"
{"agent": "research", "confidence": 0.9, "reason": "Comprehensive research requiring detailed analysis"}"""


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
# Maps all agent names (including deprecated ones) to canonical AgentType values
AGENT_NAME_MAP = {
    # Canonical agent types
    "chat": AgentType.CHAT,
    "research": AgentType.RESEARCH,
    "data": AgentType.DATA,
    "app": AgentType.CHAT,  # App mode routes to chat agent with app_builder skill
    "image": AgentType.CHAT,  # Image mode routes to chat agent with image_generation skill
    "writing": AgentType.CHAT,  # Writing mode routes to chat agent
    "CHAT": AgentType.CHAT,
    "RESEARCH": AgentType.RESEARCH,
    "DATA": AgentType.DATA,
    "APP": AgentType.CHAT,
    "IMAGE": AgentType.CHAT,
    "WRITING": AgentType.CHAT,
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

    # Fallback to legacy text parsing
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
    query = state.get("query", "")

    # Honor explicit mode if provided and valid
    explicit_mode = state.get("mode")
    if explicit_mode:
        # Normalize mode string
        mode_lower = explicit_mode.lower().strip()

        # Check if it's a valid agent type (including image/app/writing which map to chat)
        valid_modes = {"chat", "research", "data", "app", "image", "writing"}
        if mode_lower in valid_modes:
            agent_type = AGENT_NAME_MAP.get(mode_lower, AgentType.CHAT)
            logger.info(
                "routing_explicit_mode",
                query=query[:50],
                mode=mode_lower,
            )
            return {
                "selected_agent": agent_type.value,
                "routing_reason": f"Explicit mode: {explicit_mode}",
                "routing_confidence": 1.0,
                "events": [
                    {
                        "type": "routing",
                        "agent": agent_type.value,
                        "reason": f"User specified mode: {explicit_mode}",
                        "confidence": 1.0,
                    }
                ],
            }

    # Use LLM-based routing
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
