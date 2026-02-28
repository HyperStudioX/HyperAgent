"""Shared helper functions for agent subgraphs.

Provides common patterns used across chat, research, and data agents.
Uses functional style (not class hierarchy) to maintain LangGraph compatibility.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.agents.utils import append_history, build_image_context_message
from app.ai.llm import llm_service


def get_agent_llm_with_tools(
    agent_name: str,
    state: dict,
    tools: list | None = None,
    task_type: str | None = None,
) -> tuple[BaseChatModel, BaseChatModel | None]:
    """Get an LLM for the given agent, optionally with tools bound.

    Uses choose_llm_for_task() as the single standardized entry point.

    Args:
        agent_name: Name of the agent (e.g., "task", "research", "data")
        state: Agent state containing provider, tier, model overrides
        tools: Optional list of tools to bind to the LLM
        task_type: Task type for LLM selection (defaults to agent_name)

    Returns:
        Tuple of (llm_with_tools_or_plain, llm_plain).
        If tools are provided, first element has tools bound, second is plain LLM.
        If no tools, both are the same plain LLM.
    """
    provider = state.get("provider")
    tier = state.get("tier")
    model = state.get("model")

    llm = llm_service.choose_llm_for_task(
        task_type or agent_name,
        provider=provider,
        tier_override=tier,
        model_override=model,
    )

    if tools:
        return llm.bind_tools(tools), llm
    return llm, llm


def build_initial_messages(
    system_prompt: str,
    history: list[dict] | None = None,
    query: str = "",
    image_attachments: list[dict] | None = None,
    cache_system_prompt: bool = True,
) -> list[BaseMessage]:
    """Build the standard [System, ...history, Human] message list.

    Args:
        system_prompt: System prompt for the agent
        history: Optional conversation history dicts with role/content
        query: Current user query
        image_attachments: Optional image attachments for vision context
        cache_system_prompt: Whether to add cache_control for Anthropic prompt caching

    Returns:
        List of LangChain messages ready for LLM invocation
    """
    kwargs = {}
    if cache_system_prompt:
        kwargs["additional_kwargs"] = {"cache_control": {"type": "ephemeral"}}
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt, **kwargs)]

    if history:
        append_history(messages, history)

    if query:
        messages.append(HumanMessage(content=query))

    # Add image context if available
    if image_attachments:
        image_message = build_image_context_message(image_attachments)
        if image_message:
            messages.append(image_message)

    return messages
