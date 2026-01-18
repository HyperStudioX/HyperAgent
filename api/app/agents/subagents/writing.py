"""Writing subagent for long-form content creation with handoff support."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.prompts import (
    WRITING_SYSTEM_PROMPT,
    get_draft_prompt,
    get_outline_prompt,
)
from app.agents.state import WritingState
from app.agents.tools import (
    web_search,
    generate_image,
    analyze_image,
    get_handoff_tools_for_agent,
    execute_react_loop,
    get_react_config,
)
from app.agents.tools.tool_gate import should_enable_tools
from app.agents.utils import (
    append_history,
    build_image_context_message,
    get_image_analysis_context,
    extract_and_add_image_events,
    create_stage_event,
    create_error_event,
    create_tool_call_event,
    create_tool_result_event,
)
from app.agents import events
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import llm_service, extract_text_from_content

logger = get_logger(__name__)

WRITING_TOOLS = [web_search, generate_image, analyze_image]


async def analyze_task_node(state: WritingState) -> dict:
    """Analyze the writing task and determine type/tone.

    Args:
        state: Current writing state with query

    Returns:
        Dict with writing configuration and events
    """
    query = state.get("query") or ""

    event_list = [create_stage_event("analyze", "Analyzing writing task...", "running")]

    writing_type = _detect_writing_type(query)
    tone = _detect_tone(query)

    event_list.append(create_stage_event(
        "analyze",
        f"Writing type: {writing_type}, Tone: {tone}",
        "completed",
    ))

    logger.info(
        "writing_task_analyzed",
        query=query[:50],
        writing_type=writing_type,
        tone=tone,
    )

    return {
        "writing_type": writing_type,
        "tone": tone,
        "events": event_list,
    }


async def create_outline_node(state: WritingState) -> dict:
    """Create an outline for the writing task using the canonical ReAct loop.

    Args:
        state: Current writing state

    Returns:
        Dict with outline, events, and potential handoff
    """
    query = state.get("query") or ""
    writing_type = state.get("writing_type", "general")
    tone = state.get("tone", "neutral")
    image_attachments = state.get("image_attachments") or []

    event_list = [create_stage_event("outline", "Creating outline...", "running")]

    # Get handoff tools for writing agent
    handoff_tools = get_handoff_tools_for_agent("writing")

    # Get agent-specific ReAct configuration
    config = get_react_config("writing")

    try:
        outline_prompt = get_outline_prompt(query, writing_type, tone)
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)

        # Build system prompt with image context if images are attached
        system_prompt = WRITING_SYSTEM_PROMPT
        if image_attachments:
            image_context = get_image_analysis_context(image_attachments)
            system_prompt = f"{WRITING_SYSTEM_PROMPT}\n\n{image_context}"

        messages = [SystemMessage(content=system_prompt)]
        append_history(messages, state.get("messages", []))

        # Add multimodal image message if images are attached
        image_message = build_image_context_message(
            image_attachments,
            "The user has attached the following image(s) for reference. Please analyze these images and use them to inform your writing if relevant.",
        )
        if image_message:
            messages.append(image_message)
            logger.info("image_context_added_to_outline", image_count=len(image_attachments))

        messages.append(HumanMessage(content=outline_prompt))
        history = state.get("messages", [])

        # Enable tools if search/image triggers detected OR images are attached
        enable_tools = should_enable_tools(query, history) or bool(image_attachments)

        if enable_tools:
            all_tools = WRITING_TOOLS + handoff_tools
            llm_with_tools = llm.bind_tools(all_tools)

            # Define callbacks for tool events
            def on_tool_call(tool_name: str, args: dict):
                event_list.append(create_tool_call_event(tool_name, args))

            def on_tool_result(tool_name: str, result: str):
                if tool_name == "generate_image":
                    extract_and_add_image_events(result, event_list)
                event_list.append(create_tool_result_event(tool_name, result))

            def on_handoff(source: str, target: str, task: str):
                event_list.append(events.handoff(source=source, target=target, task=task))

            # Execute the canonical ReAct loop
            result = await execute_react_loop(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=all_tools,
                query=query,
                config=config,
                source_agent="writing",
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_handoff=on_handoff,
            )

            # Add events from the ReAct loop
            event_list.extend(result.events)
            messages = result.messages

            # Check for pending handoff
            if result.pending_handoff:
                logger.info("writing_handoff_detected", target=result.pending_handoff.get("target_agent"))
                return {
                    "outline": "",
                    "events": event_list,
                    "pending_handoff": result.pending_handoff,
                }

        # Stream the outline
        outline_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    outline_chunks.append(content)
                    event_list.append(events.token(content))

        outline = "".join(outline_chunks)

        if outline and len(outline.strip()) < 50:
            logger.warning("outline_too_short", length=len(outline))

        event_list.append(create_stage_event("outline", "Outline created", "completed"))

        logger.info(
            "outline_created",
            query=query[:50],
            writing_type=writing_type,
            tone=tone,
            outline_length=len(outline),
        )

        return {
            "outline": outline,
            "events": event_list,
        }

    except Exception as e:
        logger.error("outline_creation_failed", error=str(e))
        event_list.append(create_error_event("outline", str(e)))
        return {
            "outline": "",
            "events": event_list,
        }


async def write_content_node(state: WritingState) -> dict:
    """Write the content based on outline using the canonical ReAct loop.

    Args:
        state: Current writing state with outline

    Returns:
        Dict with draft content, events, and potential handoff
    """
    query = state.get("query", "")
    outline = state.get("outline", "")
    writing_type = state.get("writing_type", "general")
    tone = state.get("tone", "neutral")
    image_attachments = state.get("image_attachments") or []

    event_list = [create_stage_event("write", "Writing content...", "running")]

    # Get handoff tools for writing agent
    handoff_tools = get_handoff_tools_for_agent("writing")

    # Get agent-specific ReAct configuration
    config = get_react_config("writing")

    # If no outline, write directly with type/tone context
    if not outline:
        prompt = f"{query}\n\nWriting Type: {writing_type}\nTone: {tone}"
    else:
        prompt = get_draft_prompt(query, outline, writing_type, tone)

    try:
        provider = state.get("provider") or LLMProvider.ANTHROPIC
        model = state.get("model")
        llm = llm_service.get_llm(provider=provider, model=model)

        # Build system prompt with image context if images are attached
        system_prompt = WRITING_SYSTEM_PROMPT
        if image_attachments:
            image_context = get_image_analysis_context(image_attachments)
            system_prompt = f"{WRITING_SYSTEM_PROMPT}\n\n{image_context}"

        messages = [SystemMessage(content=system_prompt)]
        append_history(messages, state.get("messages", []))

        # Add multimodal image message if images are attached
        image_message = build_image_context_message(
            image_attachments,
            "The user has attached the following image(s) for reference. Please analyze these images and use them to inform your writing if relevant.",
        )
        if image_message:
            messages.append(image_message)
            logger.info("image_context_added_to_write", image_count=len(image_attachments))

        messages.append(HumanMessage(content=prompt))
        history = state.get("messages", [])

        # Enable tools if search/image triggers detected OR images are attached
        enable_tools = should_enable_tools(query, history) or bool(image_attachments)

        if enable_tools:
            all_tools = WRITING_TOOLS + handoff_tools
            llm_with_tools = llm.bind_tools(all_tools)

            # Define callbacks for tool events
            def on_tool_call(tool_name: str, args: dict):
                event_list.append(create_tool_call_event(tool_name, args))

            def on_tool_result(tool_name: str, result: str):
                if tool_name == "generate_image":
                    extract_and_add_image_events(result, event_list)
                event_list.append(create_tool_result_event(tool_name, result))

            def on_handoff(source: str, target: str, task: str):
                event_list.append(events.handoff(source=source, target=target, task=task))

            # Execute the canonical ReAct loop
            result = await execute_react_loop(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=all_tools,
                query=query,
                config=config,
                source_agent="writing",
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
                on_handoff=on_handoff,
            )

            # Add events from the ReAct loop
            event_list.extend(result.events)
            messages = result.messages

            # Check for pending handoff
            if result.pending_handoff:
                logger.info("writing_handoff_detected", target=result.pending_handoff.get("target_agent"))
                return {
                    "response": "",
                    "events": event_list,
                    "pending_handoff": result.pending_handoff,
                }

        # Stream the content
        content_chunks = []
        async for chunk in llm.astream(messages):
            if chunk.content:
                content = extract_text_from_content(chunk.content)
                if content:
                    content_chunks.append(content)
                    event_list.append(events.token(content))

        content = "".join(content_chunks)

        event_list.append(create_stage_event("write", "Content written", "completed"))

        logger.info(
            "content_written",
            query=query[:50],
            length=len(content),
            writing_type=writing_type,
            tone=tone,
        )

        result = {
            "draft": content,
            "final_content": content,
            "response": content,
            "events": event_list,
        }

        # Propagate handoff if present from outline stage
        pending_handoff = state.get("pending_handoff")
        if pending_handoff:
            result["pending_handoff"] = pending_handoff

        return result

    except Exception as e:
        logger.error("content_writing_failed", error=str(e))
        event_list.append(create_error_event("write", str(e)))
        return {
            "response": f"I apologize, but I encountered an error writing content: {str(e)}",
            "events": event_list,
        }


def should_create_outline(state: WritingState) -> str:
    """Determine whether to create an outline first.

    Args:
        state: Current writing state

    Returns:
        Next node name: "outline" or "write"
    """
    # Check for pending handoff
    if state.get("pending_handoff"):
        return "write"

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

    Returns:
        Compiled writing graph
    """
    graph = StateGraph(WritingState)

    graph.add_node("analyze", analyze_task_node)
    graph.add_node("outline", create_outline_node)
    graph.add_node("write", write_content_node)

    graph.set_entry_point("analyze")

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


writing_subgraph = create_writing_graph()
