"""Event extraction from tool results.

Extracts SSE events (images, terminal, browser_stream, workspace_update)
from tool execution results. Used by the chat agent's act_node.
"""

import json

from app.agents import events
from app.agents.utils import extract_and_add_image_events
from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_image_events(
    tool_name: str,
    result_str: str,
    event_list: list[dict],
    image_event_count: int,
) -> tuple[list[dict], int]:
    """Extract image events from generate_image tool results.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        event_list: Existing event list (read-only, used for counting)
        image_event_count: Current count of image events for indexing

    Returns:
        Tuple of (new_events, updated_image_event_count)
    """
    if tool_name != "generate_image" or not result_str:
        return [], image_event_count

    new_events: list[dict] = []
    extract_and_add_image_events(result_str, new_events, start_index=image_event_count)
    all_events = list(event_list) + new_events
    updated_count = sum(1 for e in all_events if isinstance(e, dict) and e.get("type") == "image")
    return new_events, updated_count


def extract_skill_events(
    tool_name: str,
    result_str: str,
    event_list: list[dict],
    image_event_count: int,
    task_id: str | None,
    user_id: str | None,
) -> tuple[list[dict], int]:
    """Extract events from invoke_skill tool results.

    Handles image_generation, app_builder, and generic skill events
    (terminal, stage, browser_stream).

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        event_list: Existing event list (read-only, used for counting)
        image_event_count: Current count of image events
        task_id: Task ID for sandbox identification
        user_id: User ID for sandbox identification

    Returns:
        Tuple of (new_events, updated_image_event_count)
    """
    if tool_name != "invoke_skill" or not result_str:
        return [], image_event_count

    new_events: list[dict] = []

    try:
        parsed = json.loads(result_str)
        skill_id = parsed.get("skill_id")

        # Extract images from image_generation skill
        if skill_id == "image_generation":
            output = parsed.get("output") or {}
            images = output.get("images") or []
            if images:
                extract_and_add_image_events(
                    json.dumps({"success": True, "images": images}),
                    new_events,
                    start_index=image_event_count,
                )
                all_events = list(event_list) + new_events
                image_event_count = sum(
                    1 for e in all_events if isinstance(e, dict) and e.get("type") == "image"
                )

        # Emit browser_stream event for app_builder skill with preview_url
        elif skill_id == "app_builder":
            output = parsed.get("output") or {}
            preview_url = output.get("preview_url")
            if preview_url and output.get("success"):
                sandbox_id = task_id or user_id or "app-sandbox"
                new_events.append(
                    events.browser_stream(
                        stream_url=preview_url,
                        sandbox_id=sandbox_id,
                        auth_key=None,
                        display_url=output.get("display_url"),
                    )
                )
                logger.info(
                    "app_builder_browser_stream_emitted",
                    preview_url=preview_url,
                    sandbox_id=sandbox_id,
                )

        # Note: stage/terminal/browser_stream events are dispatched in real-time
        # via dispatch_custom_event in invoke_skill — no JSON extraction needed here.
    except Exception as e:
        logger.warning("invoke_skill_event_extraction_failed", error=str(e))

    return new_events, image_event_count


def extract_app_builder_events(
    tool_name: str,
    result_str: str,
    app_builder_tool_names: set[str],
    task_id: str | None,
    user_id: str | None,
) -> list[dict]:
    """Extract terminal and browser events from app builder tool results.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        app_builder_tool_names: Set of app builder tool names
        task_id: Task ID for sandbox identification
        user_id: User ID for sandbox identification

    Returns:
        List of new events extracted from the tool result.
    """
    if tool_name not in app_builder_tool_names or not result_str:
        return []

    new_events: list[dict] = []

    try:
        parsed = json.loads(result_str)

        # Extract terminal events
        terminal_events = parsed.get("terminal_events") or []
        if terminal_events:
            logger.info(
                "app_builder_terminal_events_extracted",
                tool_name=tool_name,
                event_count=len(terminal_events),
            )
        for terminal_event in terminal_events:
            if isinstance(terminal_event, dict):
                event_type = terminal_event.get("type")
                if event_type in (
                    "terminal_command",
                    "terminal_output",
                    "terminal_error",
                    "terminal_complete",
                ):
                    new_events.append(terminal_event)

        # Emit browser_stream event if preview_url is present
        preview_url = parsed.get("preview_url")
        if preview_url and parsed.get("success"):
            sandbox_id = parsed.get("sandbox_id") or task_id or user_id or "app-sandbox"
            new_events.append(
                events.browser_stream(
                    stream_url=preview_url,
                    sandbox_id=sandbox_id,
                    auth_key=None,
                    display_url=parsed.get("display_url"),
                )
            )
            logger.info(
                "app_builder_browser_stream_emitted_from_tool",
                preview_url=preview_url,
                sandbox_id=sandbox_id,
            )

        # Extract workspace_update events (file create/modify/delete)
        workspace_events = parsed.get("workspace_events") or []
        for ws_event in workspace_events:
            if isinstance(ws_event, dict) and ws_event.get("type") == "workspace_update":
                new_events.append(ws_event)
        if workspace_events:
            logger.info(
                "app_builder_workspace_events_extracted",
                tool_name=tool_name,
                event_count=len(workspace_events),
            )
    except Exception as e:
        logger.warning("app_builder_event_extraction_failed", error=str(e))

    return new_events


def extract_shell_and_code_events(
    tool_name: str,
    result_str: str,
) -> list[dict]:
    """Extract terminal and workspace events from shell_exec and execute_code results.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool

    Returns:
        List of new events extracted from the tool result.
    """
    if tool_name not in ("shell_exec", "execute_code") or not result_str:
        return []

    new_events: list[dict] = []

    try:
        parsed = json.loads(result_str)
        if not isinstance(parsed, dict):
            return []

        # If terminal events were already streamed in real-time, skip extraction
        if parsed.get("terminal_streamed"):
            # Only extract workspace events (not terminal — already dispatched)
            workspace_events = parsed.get("workspace_events") or []
            for ws_evt in workspace_events:
                if isinstance(ws_evt, dict) and ws_evt.get("type") == "workspace_update":
                    new_events.append(ws_evt)
            if workspace_events:
                logger.info(
                    "shell_code_workspace_events_extracted",
                    tool_name=tool_name,
                    event_count=len(workspace_events),
                )
            return new_events

        # Extract terminal events (fallback path — not streamed)
        terminal_events = parsed.get("terminal_events") or []
        for evt in terminal_events:
            if isinstance(evt, dict) and evt.get("type") in (
                "terminal_command",
                "terminal_output",
                "terminal_error",
                "terminal_complete",
            ):
                new_events.append(evt)

        if terminal_events:
            logger.info(
                "shell_code_terminal_events_extracted",
                tool_name=tool_name,
                event_count=len(terminal_events),
            )

        # Extract workspace events
        workspace_events = parsed.get("workspace_events") or []
        for ws_evt in workspace_events:
            if isinstance(ws_evt, dict) and ws_evt.get("type") == "workspace_update":
                new_events.append(ws_evt)

        if workspace_events:
            logger.info(
                "shell_code_workspace_events_extracted",
                tool_name=tool_name,
                event_count=len(workspace_events),
            )
    except Exception as e:
        logger.warning("shell_code_event_extraction_failed", tool_name=tool_name, error=str(e))

    return new_events


def extract_slide_events(
    tool_name: str,
    result_str: str,
) -> list[dict]:
    """Extract slide generation events from generate_slides tool results.

    Converts successful generate_slides results into skill_output events
    that the frontend's SlideOutputPanel can render.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool

    Returns:
        List of new events extracted from the tool result.
    """
    if tool_name != "generate_slides" or not result_str:
        return []

    try:
        parsed = json.loads(result_str)
        if parsed.get("success") and parsed.get("download_url"):
            return [events.skill_output(
                skill_id="slide_generation",
                output={
                    "download_url": parsed["download_url"],
                    "storage_key": parsed.get("storage_key", ""),
                    "title": parsed.get("title", ""),
                    "slide_count": parsed.get("slide_count", 0),
                    "sources": parsed.get("sources", []),
                    "slide_outline": parsed.get("slide_outline", []),
                },
            )]
    except Exception as e:
        logger.warning("slide_event_extraction_failed", error=str(e))

    return []
