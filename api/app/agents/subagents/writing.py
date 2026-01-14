"""Writing subagent for long-form content creation."""

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.state import WritingState
from app.core.logging import get_logger
from app.services.llm import llm_service

logger = get_logger(__name__)

WRITING_SYSTEM_PROMPT = """You are a professional writer assistant specializing in creating high-quality content.

You can help with various types of writing:
- Articles and blog posts
- Technical documentation
- Creative writing (stories, essays)
- Business communications
- Academic writing

Guidelines:
1. Understand the target audience and purpose
2. Structure content logically with clear sections
3. Use appropriate tone and style for the content type
4. Include relevant examples and explanations
5. Ensure clarity and readability

When writing, organize your response with clear headings and formatting using markdown."""


OUTLINE_PROMPT_TEMPLATE = """Create a detailed outline for the following writing task:

Task: {query}

Provide a structured outline with:
1. Main sections and subsections
2. Key points to cover in each section
3. Suggested word count for each section

Format the outline using markdown with proper headings."""


DRAFT_PROMPT_TEMPLATE = """Write the content based on this outline:

Outline:
{outline}

Original request: {query}

Write engaging, well-structured content following the outline. Use markdown formatting for headings, lists, and emphasis where appropriate."""


async def analyze_task_node(state: WritingState) -> dict:
    """Analyze the writing task and determine type/tone.

    Args:
        state: Current writing state with query

    Returns:
        Dict with writing configuration and events
    """
    query = state.get("query", "")

    events = [
        {
            "type": "step",
            "step_type": "analyze",
            "description": "Analyzing writing task...",
            "status": "running",
        }
    ]

    # Detect writing type from query
    writing_type = _detect_writing_type(query)
    tone = _detect_tone(query)

    events.append(
        {
            "type": "step",
            "step_type": "analyze",
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
    query = state.get("query", "")

    events = [
        {
            "type": "step",
            "step_type": "outline",
            "description": "Creating outline...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()

    try:
        response = await llm.ainvoke(
            [
                SystemMessage(content=WRITING_SYSTEM_PROMPT),
                HumanMessage(content=OUTLINE_PROMPT_TEMPLATE.format(query=query)),
            ]
        )
        outline = response.content

        events.append(
            {
                "type": "step",
                "step_type": "outline",
                "description": "Outline created",
                "status": "completed",
            }
        )

        logger.info("outline_created", query=query[:50])

        return {
            "outline": outline,
            "events": events,
        }

    except Exception as e:
        logger.error("outline_creation_failed", error=str(e))
        events.append(
            {
                "type": "step",
                "step_type": "outline",
                "description": f"Error: {str(e)}",
                "status": "completed",
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

    events = [
        {
            "type": "step",
            "step_type": "write",
            "description": "Writing content...",
            "status": "running",
        }
    ]

    llm = llm_service.get_llm()

    # If no outline, write directly
    if not outline:
        prompt = query
    else:
        prompt = DRAFT_PROMPT_TEMPLATE.format(outline=outline, query=query)

    try:
        # Stream the content
        content_chunks = []
        async for chunk in llm.astream(
            [
                SystemMessage(content=WRITING_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        ):
            if chunk.content:
                from app.services.llm import extract_text_from_content
                content = extract_text_from_content(chunk.content)
                if content:  # Only append non-empty content
                    content_chunks.append(content)
                    events.append({"type": "token", "content": content})

        content = "".join(content_chunks)

        events.append(
            {
                "type": "step",
                "step_type": "write",
                "description": "Content written",
                "status": "completed",
            }
        )

        logger.info("content_written", query=query[:50], length=len(content))

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
                "type": "step",
                "step_type": "write",
                "description": f"Error: {str(e)}",
                "status": "completed",
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

    # Skip outline for short or simple content
    simple_types = ["email", "message", "reply", "comment"]
    if writing_type in simple_types:
        return "write"

    # Skip outline if query is short
    if len(query) < 50 and "article" not in query and "blog" not in query:
        return "write"

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
