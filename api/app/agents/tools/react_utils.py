"""Utilities for ReAct-style tool invocation with streamed LLM responses."""

from langchain_core.messages import AIMessage

from app.services.llm import extract_text_from_content


def build_ai_message_from_chunks(response_chunks: list, query: str) -> AIMessage:
    """Build an AIMessage from streamed chunks with normalized tool calls."""
    if not response_chunks:
        return AIMessage(content="")

    full_content = ""
    all_tool_calls: list[dict] = []
    for chunk in response_chunks:
        if hasattr(chunk, "content") and chunk.content:
            full_content += extract_text_from_content(chunk.content)
        if hasattr(chunk, "tool_calls") and chunk.tool_calls:
            all_tool_calls.extend(chunk.tool_calls)

    normalized_tool_calls = []
    for tool_call in all_tool_calls:
        tool_name = tool_call.get("name") or tool_call.get("tool") or ""
        if not tool_name:
            continue
        tool_args = tool_call.get("args") or {}
        if tool_name == "web_search" and not tool_args.get("query"):
            if query:
                tool_args = {**tool_args, "query": query}
            else:
                continue
        tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id")
        if not tool_call_id:
            import uuid

            tool_call_id = str(uuid.uuid4())
        normalized_tool_calls.append(
            {
                **tool_call,
                "id": tool_call_id,
                "name": tool_name,
                "args": tool_args,
            }
        )

    return AIMessage(
        content=full_content,
        tool_calls=normalized_tool_calls if normalized_tool_calls else None,
    )
