"""Chat subagent for general conversation with tool calling and handoff support."""

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import END, StateGraph

from app.agents.prompts import CHAT_SYSTEM_PROMPT
from app.agents.state import ChatState
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
    extract_and_add_image_events,
    create_stage_event,
    create_tool_call_event,
    create_tool_result_event,
)
from app.agents import events
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.llm import llm_service

logger = get_logger(__name__)

# Available tools for the chat agent
CHAT_TOOLS = [web_search, generate_image, analyze_image]


async def agent_node(state: ChatState) -> dict:
    """Process a chat message using the canonical ReAct loop.

    This node handles the complete ReAct pattern including:
    - Tool calling with retry logic
    - Handoff detection and processing
    - Message streaming
    - Iteration limits

    Args:
        state: Current chat state with query and messages

    Returns:
        Dict with updated messages, events, response, and potential handoff
    """
    query = state.get("query") or ""
    system_prompt = state.get("system_prompt") or CHAT_SYSTEM_PROMPT
    image_attachments = state.get("image_attachments") or []

    logger.info("chat_agent_processing", query=query[:50], image_count=len(image_attachments))

    event_list = [create_stage_event("chat", "Processing query...", "running")]

    # Build initial messages
    lc_messages = [SystemMessage(content=system_prompt)]

    # Add history if present
    history = state.get("messages", [])
    append_history(lc_messages, history)

    # Add multimodal image message if images are attached
    image_message = build_image_context_message(image_attachments)
    if image_message:
        lc_messages.append(image_message)
        logger.info("image_context_added_to_chat", image_count=len(image_attachments))

    # Add current query
    lc_messages.append(HumanMessage(content=query))

    # Enable tools if search/image triggers detected OR images are attached
    enable_tools = should_enable_tools(query, history) or bool(image_attachments)

    # Get handoff tools for chat agent
    handoff_tools = get_handoff_tools_for_agent("chat")

    # Get LLM with tier routing (chat uses PRO tier by default)
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.get_llm_for_task(
        task_type="chat",
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    # Combine regular tools with handoff tools
    all_tools = CHAT_TOOLS + handoff_tools if enable_tools else handoff_tools
    llm_with_tools = llm.bind_tools(all_tools) if all_tools else llm

    # Get agent-specific ReAct configuration
    config = get_react_config("chat")

    try:
        # Define callbacks for tool events
        def on_tool_call(tool_name: str, args: dict, tool_id: str):
            event_list.append(create_tool_call_event(tool_name, args, tool_id))

        def on_tool_result(tool_name: str, result: str, tool_id: str):
            # Note: generate_image visualization is handled in react_tool.py
            event_list.append(create_tool_result_event(tool_name, result, tool_id))

        def on_handoff(source: str, target: str, task: str):
            event_list.append(events.handoff(source=source, target=target, task=task))

        def on_token(token: str):
            event_list.append(events.token(token))

        # Execute the canonical ReAct loop
        result = await execute_react_loop(
            llm_with_tools=llm_with_tools,
            messages=lc_messages,
            tools=all_tools,
            query=query,
            config=config,
            source_agent="chat",
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
            on_handoff=on_handoff,
            on_token=on_token,
        )

        # Add events from the ReAct loop
        event_list.extend(result.events)

        if result.pending_handoff:
            logger.info(
                "chat_handoff_detected",
                target=result.pending_handoff.get("target_agent"),
                task=result.pending_handoff.get("task_description", "")[:50],
            )
            event_list.append(create_stage_event("chat", "Handoff initiated", "completed"))
        else:
            event_list.append(create_stage_event("chat", "Response generated", "completed"))

        return {
            "lc_messages": result.messages,
            "response": result.final_response,
            "events": event_list,
            "tool_iterations": result.tool_iterations,
            "pending_handoff": result.pending_handoff,
        }

    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        event_list.append(create_stage_event("chat", f"Error: {str(e)}", "completed"))
        error_msg = AIMessage(content=f"I apologize, but I encountered an error: {e}")
        lc_messages.append(error_msg)
        return {
            "lc_messages": lc_messages,
            "response": f"I apologize, but I encountered an error: {e}",
            "events": event_list,
        }


def create_chat_graph() -> StateGraph:
    """Create the chat subagent graph with ReAct pattern and handoff support.

    The graph is now simplified since agent_node handles the complete ReAct loop
    internally using execute_react_loop().

    Graph structure:
    [agent] -> END

    Returns:
        Compiled chat graph
    """
    graph = StateGraph(ChatState)

    # Add single agent node that handles the complete ReAct loop
    graph.add_node("agent", agent_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Agent directly ends the graph - all tool calling happens inside execute_react_loop
    graph.add_edge("agent", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
chat_subgraph = create_chat_graph()
