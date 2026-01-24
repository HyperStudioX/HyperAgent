"""Shared utilities for the multi-agent system.

This module consolidates common functionality used across multiple subagents
to eliminate code duplication and ensure consistent behavior.
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.logging import get_logger

logger = get_logger(__name__)


def append_history(messages: list[BaseMessage], history: list[dict]) -> None:
    """Append chat history to LangChain messages list.

    Converts dict-based message history to LangChain message objects.

    Args:
        messages: List of LangChain messages to append to (modified in place)
        history: List of message dicts with 'role' and 'content' keys
    """
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))


def build_image_context_message(
    image_attachments: list[dict],
    context_text: str | None = None,
) -> HumanMessage | None:
    """Build a HumanMessage with image content for multimodal LLMs.

    Creates a multimodal message containing text context and base64-encoded images
    for use with vision-capable LLMs.

    Args:
        image_attachments: List of image attachment dicts with:
            - base64_data: Base64-encoded image data
            - mime_type: MIME type (e.g., "image/png")
            - filename: Optional filename for display
        context_text: Optional custom context text. If None, uses default.

    Returns:
        HumanMessage with image content parts, or None if no images
    """
    if not image_attachments:
        return None

    content_parts = []

    # Add text description of images
    image_names = [img.get("filename", "image") for img in image_attachments]
    default_text = (
        f"The user has attached the following image(s): {', '.join(image_names)}. "
        "Please analyze and respond to any questions about these images."
    )
    content_parts.append({
        "type": "text",
        "text": context_text or default_text,
    })

    # Add each image as a content part
    for img in image_attachments:
        base64_data = img.get("base64_data")
        mime_type = img.get("mime_type", "image/png")
        if base64_data:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_data}",
                },
            })

    return HumanMessage(content=content_parts)


def extract_and_add_image_events(
    tool_content: str | list | None,
    events: list[dict],
    start_index: int = 0,
) -> None:
    """Extract image data from generate_image tool response and add image events.

    Parses the JSON response from the generate_image tool and creates image
    events for each generated image.

    Args:
        tool_content: JSON string or list from generate_image tool containing base64 image data
        events: List of events to append image events to (modified in place)
        start_index: Starting index for image numbering (for inline rendering)
    """
    # Handle list content (multimodal)
    if isinstance(tool_content, list):
        # Try to find text content in the list
        for item in tool_content:
            if isinstance(item, dict) and item.get("type") == "text":
                tool_content = item.get("text", "")
                break
            elif isinstance(item, str):
                tool_content = item
                break
        else:
            logger.warning(
                "image_tool_content_list_no_text",
                content=str(tool_content)[:100] if tool_content else "empty",
            )
            return

    # Skip if content is empty or None
    if not tool_content or (isinstance(tool_content, str) and not tool_content.strip()):
        logger.warning(
            "image_tool_content_empty",
            content_type=type(tool_content).__name__,
        )
        return

    # Check if this is a tool invocation error (not valid JSON)
    if isinstance(tool_content, str) and tool_content.startswith("Error invoking tool"):
        logger.warning("image_tool_invocation_error", error=tool_content[:200])
        return

    try:
        # Parse the JSON response from generate_image tool
        result = json.loads(tool_content)

        # Check if image generation was successful
        if not result.get("success"):
            logger.warning("image_generation_failed", error=result.get("error"))
            return

        # Extract images and create image events
        images = result.get("images", [])
        for i, img in enumerate(images):
            base64_data = img.get("base64_data")
            if base64_data:
                # Remove whitespace/newlines to keep SSE payloads single-line JSON.
                base64_data = re.sub(r"\s+", "", base64_data)
                # Detect mime type from base64 signature
                mime_type = "image/png"
                if base64_data.startswith("/9j/"):
                    mime_type = "image/jpeg"
                elif base64_data.startswith("R0lGOD"):
                    mime_type = "image/gif"
                elif base64_data.startswith("UklGR"):
                    mime_type = "image/webp"

                image_index = start_index + i
                events.append({
                    "type": "image",
                    "index": image_index,
                    "data": base64_data,
                    "mime_type": mime_type,
                })
                logger.info("image_event_added", index=image_index, mime_type=mime_type)

    except json.JSONDecodeError as e:
        logger.warning(
            "failed_to_parse_image_result",
            error=str(e),
            content_preview=tool_content[:100] if tool_content else "empty",
        )
    except Exception as e:
        logger.error("failed_to_extract_image_events", error=str(e))


def get_image_analysis_context(image_attachments: list[dict]) -> str:
    """Get a text-only context string describing available images.

    Used for prompts where multimodal content isn't directly supported.

    Args:
        image_attachments: List of image attachment dicts

    Returns:
        Text context describing available images
    """
    if not image_attachments:
        return ""

    image_info = []
    for img in image_attachments:
        filename = img.get("filename", "image")
        mime_type = img.get("mime_type", "unknown")
        image_info.append(f"- {filename} ({mime_type})")

    return f"""
The user has attached the following images that you can analyze using the analyze_image tool:
{chr(10).join(image_info)}

You can call the analyze_image tool with the image data to understand the image content.
"""


def truncate_content(content: str, max_length: int = 500) -> str:
    """Truncate content to a maximum length.

    Args:
        content: Content to truncate
        max_length: Maximum length

    Returns:
        Truncated content
    """
    if len(content) <= max_length:
        return content
    return content[:max_length]


def create_stage_event(
    name: str,
    description: str,
    status: str = "running",
) -> dict[str, Any]:
    """Create a stage event dictionary.

    Args:
        name: Stage name (e.g., "search", "analyze", "write")
        description: Human-readable description
        status: Stage status ("running", "completed", "failed")

    Returns:
        Stage event dictionary
    """
    return {
        "type": "stage",
        "name": name,
        "description": description,
        "status": status,
    }


def create_error_event(
    name: str,
    error: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Create an error event dictionary.

    Args:
        name: Stage/component name where error occurred
        error: Error message
        description: Optional human-readable description

    Returns:
        Error event dictionary
    """
    return {
        "type": "error",
        "name": name,
        "description": description or f"Error: {error}",
        "error": error,
        "status": "failed",
    }


def create_tool_call_event(
    tool_name: str,
    args: dict[str, Any],
    tool_id: str | None = None,
) -> dict[str, Any]:
    """Create a tool call event dictionary.

    Args:
        tool_name: Name of the tool being called
        args: Arguments passed to the tool
        tool_id: Unique ID for matching with tool_result (from LLM response)

    Returns:
        Tool call event dictionary
    """
    return {
        "type": "tool_call",
        "tool": tool_name,
        "args": args,
        "id": tool_id,
    }


def create_tool_result_event(
    tool_name: str,
    content: str,
    tool_id: str | None = None,
    max_content_length: int = 500,
) -> dict[str, Any]:
    """Create a tool result event dictionary.

    Args:
        tool_name: Name of the tool
        content: Tool result content
        tool_id: Unique ID for matching with tool_call
        max_content_length: Maximum content length to include

    Returns:
        Tool result event dictionary
    """
    return {
        "type": "tool_result",
        "tool": tool_name,
        "content": truncate_content(content, max_content_length),
        "id": tool_id,
    }


def format_shared_context(shared_memory: dict[str, Any]) -> str:
    """Format shared memory context for injection into prompts.

    Args:
        shared_memory: Shared memory dictionary from state

    Returns:
        Formatted context string
    """
    if not shared_memory:
        return ""

    context_parts = []

    if shared_memory.get("research_findings"):
        findings = shared_memory["research_findings"]
        context_parts.append(f"## Research Findings\n{findings[:2000]}")

    if shared_memory.get("research_sources"):
        sources = shared_memory["research_sources"]
        source_text = "\n".join(
            f"- [{s.get('title', 'Source')}]({s.get('url', '')})"
            for s in sources[:10]
        )
        context_parts.append(f"## Sources\n{source_text}")

    if shared_memory.get("generated_code"):
        code = shared_memory["generated_code"]
        lang = shared_memory.get("code_language", "python")
        context_parts.append(f"## Generated Code\n```{lang}\n{code[:1500]}\n```")

    if shared_memory.get("execution_results"):
        results = shared_memory["execution_results"]
        context_parts.append(f"## Execution Results\n```\n{results[:1000]}\n```")

    if shared_memory.get("writing_outline"):
        outline = shared_memory["writing_outline"]
        context_parts.append(f"## Writing Outline\n{outline[:1000]}")

    if shared_memory.get("additional_context"):
        context_parts.append(shared_memory["additional_context"])

    if not context_parts:
        return ""

    return "---\n# Context from Previous Agents\n\n" + "\n\n".join(context_parts)
