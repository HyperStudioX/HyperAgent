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
) -> int:
    """Extract image events from generate_image tool results.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        event_list: Event list to append to (mutated in-place)
        image_event_count: Current count of image events for indexing

    Returns:
        Updated image event count
    """
    if tool_name != "generate_image" or not result_str:
        return image_event_count

    extract_and_add_image_events(result_str, event_list, start_index=image_event_count)
    return sum(1 for e in event_list if isinstance(e, dict) and e.get("type") == "image")


def extract_skill_events(
    tool_name: str,
    result_str: str,
    event_list: list[dict],
    image_event_count: int,
    task_id: str | None,
    user_id: str | None,
) -> int:
    """Extract events from invoke_skill tool results.

    Handles image_generation, app_builder, and generic skill events
    (terminal, stage, browser_stream).

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        event_list: Event list to append to (mutated in-place)
        image_event_count: Current count of image events
        task_id: Task ID for sandbox identification
        user_id: User ID for sandbox identification

    Returns:
        Updated image event count
    """
    if tool_name != "invoke_skill" or not result_str:
        return image_event_count

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
                    event_list,
                    start_index=image_event_count,
                )
                image_event_count = sum(
                    1 for e in event_list if isinstance(e, dict) and e.get("type") == "image"
                )

        # Emit browser_stream event for app_builder skill with preview_url
        elif skill_id == "app_builder":
            output = parsed.get("output") or {}
            preview_url = output.get("preview_url")
            if preview_url and output.get("success"):
                sandbox_id = task_id or user_id or "app-sandbox"
                event_list.append(
                    events.browser_stream(
                        stream_url=preview_url,
                        sandbox_id=sandbox_id,
                        auth_key=None,
                    )
                )
                logger.info(
                    "app_builder_browser_stream_emitted",
                    preview_url=preview_url,
                    sandbox_id=sandbox_id,
                )

        # Extract terminal and stage events from any skill execution
        skill_events = parsed.get("events") or []
        if skill_events:
            logger.info(
                "chat_act_node_skill_events",
                skill_id=skill_id,
                event_count=len(skill_events),
                event_types=[e.get("type") for e in skill_events if isinstance(e, dict)],
            )
        for skill_event in skill_events:
            if isinstance(skill_event, dict):
                event_type = skill_event.get("type")
                if event_type in (
                    "terminal_command",
                    "terminal_output",
                    "terminal_error",
                    "terminal_complete",
                    "stage",
                    "browser_stream",
                ):
                    event_list.append(skill_event)
                    logger.info(
                        "skill_event_extracted",
                        skill_id=skill_id,
                        event_type=event_type,
                    )
    except Exception as e:
        logger.warning("invoke_skill_event_extraction_failed", error=str(e))

    return image_event_count


def extract_app_builder_events(
    tool_name: str,
    result_str: str,
    event_list: list[dict],
    app_builder_tool_names: set[str],
    task_id: str | None,
    user_id: str | None,
) -> None:
    """Extract terminal and browser events from app builder tool results.

    Args:
        tool_name: Name of the tool
        result_str: JSON result string from the tool
        event_list: Event list to append to (mutated in-place)
        app_builder_tool_names: Set of app builder tool names
        task_id: Task ID for sandbox identification
        user_id: User ID for sandbox identification
    """
    if tool_name not in app_builder_tool_names or not result_str:
        return

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
                    event_list.append(terminal_event)

        # Emit browser_stream event if preview_url is present
        preview_url = parsed.get("preview_url")
        if preview_url and parsed.get("success"):
            sandbox_id = parsed.get("sandbox_id") or task_id or user_id or "app-sandbox"
            event_list.append(
                events.browser_stream(
                    stream_url=preview_url,
                    sandbox_id=sandbox_id,
                    auth_key=None,
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
                event_list.append(ws_event)
        if workspace_events:
            logger.info(
                "app_builder_workspace_events_extracted",
                tool_name=tool_name,
                event_count=len(workspace_events),
            )
    except Exception as e:
        logger.warning("app_builder_event_extraction_failed", error=str(e))
