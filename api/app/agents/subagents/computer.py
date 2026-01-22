"""Computer subagent for autonomous desktop control using E2B sandbox."""

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import END, StateGraph

from app.agents.prompts import COMPUTER_USE_SYSTEM_PROMPT
from app.agents.state import ComputerState
from app.agents.tools import (
    execute_react_loop,
    get_react_config,
)
from app.agents.tools.computer_use import COMPUTER_TOOLS
from app.agents.utils import (
    append_history,
    create_stage_event,
    create_tool_call_event,
    create_tool_result_event,
)
from app.agents import events
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.ai.llm import llm_service

logger = get_logger(__name__)

# React config for computer agent - allow more iterations for complex tasks
COMPUTER_REACT_CONFIG = {
    "max_iterations": 30,  # More iterations for complex desktop tasks
    "max_retries": 3,
    "retry_delay_ms": 500,
}


async def agent_node(state: ComputerState) -> dict:
    """Process a computer use task using the ReAct loop.

    This node handles autonomous desktop control including:
    - Taking screenshots to observe state
    - Clicking, typing, and other interactions
    - Planning and executing multi-step tasks
    - Iterating until task completion

    Args:
        state: Current computer state with query and task info

    Returns:
        Dict with events, response, and task results
    """
    query = state.get("query") or ""
    task_id = state.get("task_id")
    user_id = state.get("user_id")

    logger.info("computer_agent_processing", query=query[:50], task_id=task_id)

    event_list = [create_stage_event("computer", "Initializing desktop control...", "running")]

    # Build initial messages with computer use system prompt
    lc_messages = [SystemMessage(content=COMPUTER_USE_SYSTEM_PROMPT)]

    # Add history if present
    history = state.get("messages", [])
    append_history(lc_messages, history)

    # Add current query with task context
    user_message = f"""Complete this task using the computer:

Task: {query}

Remember:
1. Start by launching the browser if you need to browse the web
2. Take a screenshot first to see the current state
3. Execute actions step by step, verifying with screenshots
4. Continue until the task is complete or you've determined it cannot be completed"""

    lc_messages.append(HumanMessage(content=user_message))

    # Get LLM - use PRO tier for complex reasoning
    provider = state.get("provider") or LLMProvider.ANTHROPIC
    tier = state.get("tier")
    model = state.get("model")
    llm = llm_service.get_llm_for_task(
        task_type="computer",
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    # Get computer use tools with session context injected
    tools = []
    for tool in COMPUTER_TOOLS:
        # Create a wrapped version that injects user_id and task_id
        tools.append(tool)

    llm_with_tools = llm.bind_tools(tools) if tools else llm

    # Use computer-specific config with more iterations
    config = COMPUTER_REACT_CONFIG

    try:
        # Define callbacks for tool events
        def on_tool_call(tool_name: str, args: dict, tool_id: str):
            event_list.append(create_tool_call_event(tool_name, args, tool_id))
            # Log computer use actions for visibility
            if tool_name == "computer_use":
                action = args.get("action", "unknown")
                logger.info(
                    "computer_action",
                    action=action,
                    coordinate=args.get("coordinate"),
                    has_text=bool(args.get("text")),
                )

        def on_tool_result(tool_name: str, result: str, tool_id: str):
            event_list.append(create_tool_result_event(tool_name, result, tool_id))
            # Emit browser_stream event when we get stream URL from computer_use
            if tool_name == "computer_use" and "stream_url" in result:
                import json
                try:
                    result_data = json.loads(result)
                    if result_data.get("success") and result_data.get("stream_url"):
                        # Use the on_browser_stream callback for immediate emission
                        on_browser_stream(
                            result_data["stream_url"],
                            result_data.get("sandbox_id", ""),
                            result_data.get("auth_key"),
                        )
                except json.JSONDecodeError:
                    pass

        def on_handoff(source: str, target: str, task: str):
            # Computer agent doesn't typically handoff, but support it
            event_list.append(events.handoff(source=source, target=target, task=task))

        def on_token(token: str):
            event_list.append(events.token(token))

        def on_browser_stream(stream_url: str, sandbox_id: str, auth_key: str | None):
            # Emit browser_stream event immediately for real-time frontend display
            event_list.append(events.browser_stream(
                stream_url=stream_url,
                sandbox_id=sandbox_id,
                auth_key=auth_key,
            ))
            logger.info(
                "computer_stream_event_emitted",
                sandbox_id=sandbox_id[:8] if sandbox_id else "",
            )

        # Inject user_id and task_id into tool args
        extra_tool_args = {
            "user_id": user_id,
            "task_id": task_id,
        }

        # Execute the ReAct loop
        result = await execute_react_loop(
            llm_with_tools=llm_with_tools,
            messages=lc_messages,
            tools=tools,
            query=query,
            config=config,
            source_agent="computer",
            on_tool_call=on_tool_call,
            on_tool_result=on_tool_result,
            on_handoff=on_handoff,
            on_token=on_token,
            extra_tool_args=extra_tool_args,
            on_browser_stream=on_browser_stream,
        )

        # Add events from the ReAct loop
        event_list.extend(result.events)

        event_list.append(create_stage_event("computer", "Task completed", "completed"))

        return {
            "lc_messages": result.messages,
            "response": result.final_response,
            "events": event_list,
            "tool_iterations": result.tool_iterations,
            "task_complete": True,
            "task_result": result.final_response,
        }

    except Exception as e:
        logger.error("computer_agent_failed", error=str(e))
        event_list.append(create_stage_event("computer", f"Error: {str(e)}", "completed"))
        error_msg = AIMessage(content=f"I encountered an error while controlling the computer: {e}")
        lc_messages.append(error_msg)
        return {
            "lc_messages": lc_messages,
            "response": f"I encountered an error while controlling the computer: {e}",
            "events": event_list,
            "task_complete": False,
        }


def create_computer_graph() -> StateGraph:
    """Create the computer subagent graph.

    The graph uses the ReAct pattern for autonomous desktop control.

    Graph structure:
    [agent] -> END

    Returns:
        Compiled computer graph
    """
    graph = StateGraph(ComputerState)

    # Add single agent node that handles the complete ReAct loop
    graph.add_node("agent", agent_node)

    # Set entry point
    graph.set_entry_point("agent")

    # Agent directly ends the graph
    graph.add_edge("agent", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
computer_subgraph = create_computer_graph()
