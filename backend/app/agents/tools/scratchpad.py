"""Scratchpad tools for context offloading."""

import json

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import settings
from app.services.scratchpad_service import get_scratchpad_service


class WriteScratchpadInput(BaseModel):
    """Input for write_scratchpad tool."""

    notes: str = Field(
        ...,
        description="Notes to save for later retrieval.",
    )
    scope: str = Field(
        default="session",
        description="Storage scope: 'session' (default) or 'persistent'.",
    )
    namespace: str | None = Field(
        default=None,
        description="Optional namespace key. Defaults to conversation namespace.",
    )
    # Context fields (injected by agent, not provided by LLM)
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only).",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only).",
        json_schema_extra={"exclude": True},
    )


class ReadScratchpadInput(BaseModel):
    """Input for read_scratchpad tool."""

    reasoning: str = Field(
        ...,
        description="Why these notes are needed now.",
    )
    scope: str = Field(
        default="session",
        description="Storage scope: 'session' (default) or 'persistent'.",
    )
    namespace: str | None = Field(
        default=None,
        description="Optional namespace key. Defaults to conversation namespace.",
    )
    # Context fields (injected by agent, not provided by LLM)
    user_id: str | None = Field(
        default=None,
        description="User ID for session management (internal use only).",
        json_schema_extra={"exclude": True},
    )
    task_id: str | None = Field(
        default=None,
        description="Task ID for session management (internal use only).",
        json_schema_extra={"exclude": True},
    )


def _normalize_scope(scope: str | None) -> str:
    normalized = (scope or "session").strip().lower()
    if normalized not in {"session", "persistent"}:
        return "session"
    return normalized


@tool(args_schema=WriteScratchpadInput)
async def write_scratchpad(
    notes: str,
    scope: str = "session",
    namespace: str | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Save notes to a scratchpad for context offloading."""
    if not settings.context_offloading_enabled:
        return json.dumps({
            "success": False,
            "error": "Context offloading is disabled.",
        })

    normalized_scope = _normalize_scope(scope)
    payload = await get_scratchpad_service().write(
        notes=notes,
        user_id=user_id,
        task_id=task_id,
        scope=normalized_scope,
        namespace=namespace,
    )
    return json.dumps({
        "success": True,
        "scope": payload.scope,
        "namespace": payload.namespace,
        "saved_chars": len(payload.notes),
    })


@tool(args_schema=ReadScratchpadInput)
async def read_scratchpad(
    reasoning: str,
    scope: str = "session",
    namespace: str | None = None,
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Read notes from a scratchpad for context offloading."""
    if not settings.context_offloading_enabled:
        return json.dumps({
            "success": False,
            "error": "Context offloading is disabled.",
        })

    normalized_scope = _normalize_scope(scope)
    payload = await get_scratchpad_service().read(
        user_id=user_id,
        task_id=task_id,
        scope=normalized_scope,
        namespace=namespace,
    )
    if not payload:
        return json.dumps({
            "success": True,
            "scope": normalized_scope,
            "namespace": namespace or "",
            "notes": "",
            "found": False,
            "reasoning": reasoning,
        })
    return json.dumps({
        "success": True,
        "scope": payload.scope,
        "namespace": payload.namespace,
        "notes": payload.notes,
        "found": True,
        "reasoning": reasoning,
    })

