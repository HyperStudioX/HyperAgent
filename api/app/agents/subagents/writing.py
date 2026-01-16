"""Writing subagent for long-form content creation."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph

from app.agents.prompts import (
    WRITING_SYSTEM_PROMPT,
    get_draft_prompt,
    get_outline_prompt,
)
from app.agents.state import WritingState
from app.agents.tools import web_search
from app.agents.tools.react_utils import build_ai_message_from_chunks
from app.agents.tools.search_gate import should_enable_web_search
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import llm_service

logger = get_logger(__name__)

WEB_TOOLS = [web_search]
MAX_TOOL_ITERATIONS = 3


async def analyze_task_node(state: WritingState) -> dict:
    """Analyze the writing task and determine type/tone.

    Args:
        state: Current writing state with query

    Returns:
        Dict with writing configuration and events
    """
    query = state.get("query") or ""

    events = [
        {
            "type": "stage",
            "name": "analyze",
            "description": "Analyzing writing task...",
            "status": "running",
        }
    ]

    # Detect writing type from query
    writing_type = _detect_writing_type(query)
    tone = _detect_tone(query)

    events.append(
        {
            "type": "stage",
            "name": "analyze",
            "description": f"Writing type: {writing_type}, Tone: {tone}",
            "status": "completed",
        }
    )

    logger.info(
        "writing_task_analyzed",
        query=query[:50],
        writing_type=writing_type,
        tone=tone,
    )

    return {
        "writing_type": writing_type,
        "tone": tone,
        "events": events,
    }


async def create_outline_node(state: WritingState) -> dict:
    """Create an outline for the writing task.

    Args:
        state: Current writing state

    Returns:
        Dict with outline and events
    """
    query = state.get("query") or ""
    writing_type = state.get("writing_type", "general")
    tone = state.get("tone", "neutral")

    events = [
        {
            "type": "stage",
            "name": "outline",
            "description": "Creating outline...",
            "status": "running",
        }
    ]

    try:
        outline_prompt = get_outline_prompt(query, writing_type, tone)
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)
        messages = [SystemMessage(content=WRITING_SYSTEM_PROMPT)]
        _append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=outline_prompt))
        history = state.get("messages", [])

        if should_enable_web_search(query, history):
            llm_with_tools = llm.bind_tools(WEB_TOOLS)
            tool_iterations = 0
            while tool_iterations < MAX_TOOL_ITERATIONS:
                response_chunks = []
                async for chunk in llm_with_tools.astream(messages):
                    response_chunks.append(chunk)

                tool_response = build_ai_message_from_chunks(response_chunks, query)
                if not tool_response.tool_calls:
                    break

                messages.append(tool_response)
                tool_iterations += 1
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                    if not tool_name:
                        continue
                    events.append(
                        {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_call.get("args") or {},
                        }
                    )

                tool_results = await ToolNode(WEB_TOOLS).ainvoke({"messages": [tool_response]})
                for msg in tool_results.get("messages", []):
                    messages.append(msg)
                    if isinstance(msg, ToolMessage):
                        events.append(
                            {
                                "type": "tool_result",
                                "tool": msg.name,
                                "content": msg.content[:500] if len(msg.content) > 500 else msg.content,
                            }
                        )

            if tool_iterations >= MAX_TOOL_ITERATIONS:
                events.append(
                    {
                        "type": "stage",
                        "name": "tool",
                        "description": "Tool limit reached; continuing without more tool calls.",
                        "status": "completed",
                    }
                )

        # Stream the outline instead of single invoke
        outline_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    outline_chunks.append(content)
                    events.append({"type": "token", "content": content})

        outline = "".join(outline_chunks)

        # Validate outline quality
        if outline and len(outline.strip()) < 50:
            logger.warning("outline_too_short", length=len(outline))

        events.append(
            {
                "type": "stage",
                "name": "outline",
                "description": "Outline created",
                "status": "completed",
            }
        )

        logger.info(
            "outline_created",
            query=query[:50],
            writing_type=writing_type,
            tone=tone,
            outline_length=len(outline),
        )

        return {
            "outline": outline,
            "events": events,
        }

    except Exception as e:
        logger.error("outline_creation_failed", error=str(e))
        events.append(
            {
                "type": "error",
                "name": "outline",
                "description": f"Error: {str(e)}",
                "error": str(e),
                "status": "failed",
            }
        )
        return {
            "outline": "",
            "events": events,
        }


async def write_content_node(state: WritingState) -> dict:
    """Write the content based on outline.

    Args:
        state: Current writing state with outline

    Returns:
        Dict with draft content and events
    """
    query = state.get("query", "")
    outline = state.get("outline", "")
    writing_type = state.get("writing_type", "general")
    tone = state.get("tone", "neutral")

    events = [
        {
            "type": "stage",
            "name": "write",
            "description": "Writing content...",
            "status": "running",
        }
    ]

    # If no outline, write directly with type/tone context
    if not outline:
        prompt = f"{query}\n\nWriting Type: {writing_type}\nTone: {tone}"
    else:
        prompt = get_draft_prompt(query, outline, writing_type, tone)

    try:
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)
        messages = [SystemMessage(content=WRITING_SYSTEM_PROMPT)]
        _append_history(messages, state.get("messages", []))
        messages.append(HumanMessage(content=prompt))
        history = state.get("messages", [])

        if should_enable_web_search(query, history):
            llm_with_tools = llm.bind_tools(WEB_TOOLS)
            tool_iterations = 0
            while tool_iterations < MAX_TOOL_ITERATIONS:
                response_chunks = []
                async for chunk in llm_with_tools.astream(messages):
                    response_chunks.append(chunk)

                tool_response = build_ai_message_from_chunks(response_chunks, query)
                if not tool_response.tool_calls:
                    break

                messages.append(tool_response)
                tool_iterations += 1
                for tool_call in tool_response.tool_calls:
                    tool_name = tool_call.get("name") or tool_call.get("tool") or ""
                    if not tool_name:
                        continue
                    events.append(
                        {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_call.get("args") or {},
                        }
                    )

                tool_results = await ToolNode(WEB_TOOLS).ainvoke({"messages": [tool_response]})
                for msg in tool_results.get("messages", []):
                    messages.append(msg)
                    if isinstance(msg, ToolMessage):
                        events.append(
                            {
                                "type": "tool_result",
                                "tool": msg.name,
                                "content": msg.content[:500] if len(msg.content) > 500 else msg.content,
                            }
                        )

            if tool_iterations >= MAX_TOOL_ITERATIONS:
                events.append(
                    {
                        "type": "stage",
                        "name": "tool",
                        "description": "Tool limit reached; continuing without more tool calls.",
                        "status": "completed",
                    }
                )

        # Stream the content
        content_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    content_chunks.append(content)
                    events.append({"type": "token", "content": content})

        content = "".join(content_chunks)

        events.append(
            {
                "type": "stage",
                "name": "write",
                "description": "Content written",
                "status": "completed",
            }
        )

        logger.info(
            "content_written",
            query=query[:50],
            length=len(content),
            writing_type=writing_type,
            tone=tone,
        )

        return {
            "draft": content,
            "final_content": content,
            "response": content,
            "events": events,
        }

    except Exception as e:
        logger.error("content_writing_failed", error=str(e))
        events.append(
            {
                "type": "error",
                "name": "write",
                "description": f"Error: {str(e)}",
                "error": str(e),
                "status": "failed",
            }
        )
        return {
            "response": f"I apologize, but I encountered an error writing content: {str(e)}",
            "events": events,
        }


def should_create_outline(state: WritingState) -> str:
    """Determine whether to create an outline first.

    Args:
        state: Current writing state

    Returns:
        Next node name: "outline" or "write"
    """
    writing_type = state.get("writing_type", "")
    query = state.get("query", "").lower()

    # Always create outline for long-form content
    long_form_types = ["article", "documentation", "academic", "creative"]
    if writing_type in long_form_types:
        return "outline"

    # Skip outline for short or simple content
    simple_types = ["email", "message", "reply", "comment"]
    if writing_type in simple_types:
        return "write"

    # Skip outline if query is very short
    if len(query) < 50 and "article" not in query and "blog" not in query:
        return "write"

    # Default to outline for better structure
    return "outline"


def _detect_writing_type(query: str) -> str:
    """Detect the type of writing from the query."""
    query_lower = query.lower()

    type_keywords = {
        "article": ["article", "blog post", "post", "piece"],
        "documentation": ["documentation", "docs", "guide", "manual", "readme"],
        "creative": ["story", "essay", "creative", "fiction", "poem"],
        "business": ["email", "proposal", "report", "memo", "letter"],
        "academic": ["paper", "thesis", "research", "academic"],
    }

    for writing_type, keywords in type_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return writing_type

    return "general"


def _detect_tone(query: str) -> str:
    """Detect the desired tone from the query."""
    query_lower = query.lower()

    tone_keywords = {
        "formal": ["formal", "professional", "business", "academic"],
        "casual": ["casual", "friendly", "conversational", "informal"],
        "technical": ["technical", "detailed", "precise"],
        "creative": ["creative", "engaging", "storytelling"],
    }

    for tone, keywords in tone_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return tone

    return "neutral"


def _append_history(messages: list[BaseMessage], history: list[dict]) -> None:
    for msg in history:
        if msg.get("role") == "user":
            messages.append(HumanMessage(content=msg.get("content", "")))
        elif msg.get("role") == "assistant":
            messages.append(AIMessage(content=msg.get("content", "")))


def create_writing_graph() -> StateGraph:
    """Create the writing subagent graph.

    Graph structure:
    [analyze_task] → [should_outline?] → [create_outline] → [write_content] → [END]
                            ↓ (no)
                      [write_content] → [END]

    Returns:
        Compiled writing graph
    """
    graph = StateGraph(WritingState)

    # Add nodes
    graph.add_node("analyze", analyze_task_node)
    graph.add_node("outline", create_outline_node)
    graph.add_node("write", write_content_node)

    # Set entry point
    graph.set_entry_point("analyze")

    # Conditional edge: create outline for longer content
    graph.add_conditional_edges(
        "analyze",
        should_create_outline,
        {
            "outline": "outline",
            "write": "write",
        },
    )

    graph.add_edge("outline", "write")
    graph.add_edge("write", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
writing_subgraph = create_writing_graph()
