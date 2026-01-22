"""Image generation subagent with multi-provider support (Gemini and OpenAI)."""

import base64
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.agents.prompts import (
    IMAGE_ANALYZE_PROMPT_TEMPLATE,
    IMAGE_REFINE_PROMPT_TEMPLATE,
    IMAGE_SYSTEM_PROMPT,
)
from app.agents.state import ImageState
from app.agents.utils import create_stage_event
from app.config import settings
from app.core.logging import get_logger
from app.models.schemas import LLMProvider
from app.services.file_storage import file_storage_service
from app.ai.image import ImageProvider, image_generation_service
from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier

logger = get_logger(__name__)

# Maximum retry attempts for image generation
MAX_GENERATION_RETRIES = 2

# Content safety patterns to filter (basic blocklist approach)
UNSAFE_CONTENT_PATTERNS = [
    r"\b(nude|naked|nsfw|pornograph|explicit)\b",
    r"\b(gore|violent|bloody|gruesome)\b",
    r"\b(child|minor|underage)\s+(sex|nude|naked)\b",
    r"\b(hate|racist|discriminat)\b",
]


def is_prompt_safe(prompt: str) -> tuple[bool, str | None]:
    """Check if an image generation prompt is safe.

    Args:
        prompt: The prompt to check

    Returns:
        Tuple of (is_safe, reason if unsafe)
    """
    prompt_lower = prompt.lower()
    for pattern in UNSAFE_CONTENT_PATTERNS:
        if re.search(pattern, prompt_lower, re.IGNORECASE):
            return False, f"Prompt contains potentially unsafe content"
    return True, None


def get_fallback_provider(current_provider: str) -> tuple[str, str] | None:
    """Get fallback provider and model if available.

    Args:
        current_provider: The current provider that failed

    Returns:
        Tuple of (provider, model) or None if no fallback available
    """
    if current_provider == ImageProvider.GEMINI.value:
        # Fallback to OpenAI if Gemini fails
        if settings.openai_api_key:
            return ImageProvider.OPENAI.value, settings.image_gen_openai_model
    elif current_provider == ImageProvider.OPENAI.value:
        # Fallback to Gemini if OpenAI fails
        if settings.gemini_api_key:
            return ImageProvider.GEMINI.value, settings.image_gen_model
    return None


async def analyze_request_node(state: ImageState) -> dict:
    """Analyze the user's image generation request.

    Parses user intent to determine:
    - Style (photorealistic, artistic, cartoon, etc.)
    - Aspect ratio and size
    - Provider and model to use
    - Whether prompt refinement is needed

    Also performs content safety filtering.

    Args:
        state: Current image state with query

    Returns:
        Dict with analyzed request parameters
    """
    query = state.get("query") or ""
    provider = state.get("provider") or LLMProvider.ANTHROPIC

    logger.info("image_analyze_request", query=query[:50])

    event_list = [create_stage_event("analyze", "Analyzing image request...", "running")]

    # Content safety check
    is_safe, safety_reason = is_prompt_safe(query)
    if not is_safe:
        logger.warning("image_prompt_unsafe", query=query[:50], reason=safety_reason)
        event_list.append(create_stage_event("analyze", "Content safety check failed", "failed"))
        return {
            "original_prompt": query,
            "generation_status": "failed",
            "generation_error": safety_reason,
            "events": event_list,
        }

    # Get LLM for analysis (use FLASH tier for quick analysis)
    llm = llm_service.get_llm_for_tier(ModelTier.FLASH, provider=provider)

    try:
        # Use LLM to analyze the request
        analyze_prompt = IMAGE_ANALYZE_PROMPT_TEMPLATE.format(query=query)
        response = await llm.ainvoke([
            SystemMessage(content=IMAGE_SYSTEM_PROMPT),
            HumanMessage(content=analyze_prompt),
        ])

        # Parse the response to extract parameters
        analysis_text = response.content if hasattr(response, "content") else str(response)

        # Default parameters
        style = "photorealistic"
        aspect_ratio = "1:1"
        size = "1024x1024"
        should_refine = True
        image_provider = ImageProvider.GEMINI.value
        image_model = settings.image_gen_model

        # Parse style from response
        style_keywords = {
            "photorealistic": ["photorealistic", "realistic", "photo", "photography"],
            "artistic": ["artistic", "art", "painting", "illustration"],
            "cartoon": ["cartoon", "anime", "comic", "animated"],
            "3d": ["3d", "render", "cgi", "three-dimensional"],
            "sketch": ["sketch", "drawing", "pencil", "line art"],
        }
        analysis_lower = analysis_text.lower()
        for style_name, keywords in style_keywords.items():
            if any(kw in analysis_lower for kw in keywords):
                style = style_name
                break

        # Parse aspect ratio from response
        if "landscape" in analysis_lower or "wide" in analysis_lower or "16:9" in analysis_lower:
            aspect_ratio = "16:9"
            size = "1792x1024"
        elif "portrait" in analysis_lower or "tall" in analysis_lower or "9:16" in analysis_lower:
            aspect_ratio = "9:16"
            size = "1024x1792"
        elif "square" in analysis_lower or "1:1" in analysis_lower:
            aspect_ratio = "1:1"
            size = "1024x1024"

        # Check for provider hints in query
        query_lower = query.lower()
        if "dall-e" in query_lower or "dalle" in query_lower or "openai" in query_lower:
            image_provider = ImageProvider.OPENAI.value
            image_model = getattr(settings, "image_gen_openai_model", "dall-e-3")
        elif "gemini" in query_lower or "imagen" in query_lower or "google" in query_lower:
            image_provider = ImageProvider.GEMINI.value
            image_model = settings.image_gen_model

        # Check state for explicit model override
        if state.get("image_model"):
            image_model = state.get("image_model")
            detected_provider = image_generation_service.detect_provider(image_model)
            image_provider = detected_provider.value

        # Determine if we need to refine the prompt
        # Skip refinement for simple, clear prompts
        should_refine = len(query.split()) < 15 or "simple" not in analysis_lower

        event_list.append(create_stage_event("analyze", "Request analyzed", "completed"))

        logger.info(
            "image_request_analyzed",
            style=style,
            aspect_ratio=aspect_ratio,
            size=size,
            provider=image_provider,
            model=image_model,
            should_refine=should_refine,
        )

        return {
            "original_prompt": query,
            "style": style,
            "aspect_ratio": aspect_ratio,
            "size": size,
            "image_provider": image_provider,
            "image_model": image_model,
            "should_refine": should_refine,
            "quality": state.get("quality") or getattr(settings, "image_gen_openai_quality", "standard"),
            "generation_status": "pending",
            "events": event_list,
        }

    except Exception as e:
        logger.error("image_analyze_failed", error=str(e))
        event_list.append(create_stage_event("analyze", f"Analysis failed: {e}", "failed"))
        return {
            "original_prompt": query,
            "style": "photorealistic",
            "aspect_ratio": "1:1",
            "size": "1024x1024",
            "image_provider": ImageProvider.GEMINI.value,
            "image_model": settings.image_gen_model,
            "should_refine": True,
            "quality": "standard",
            "generation_status": "pending",
            "events": event_list,
        }


async def refine_prompt_node(state: ImageState) -> dict:
    """Refine the user's prompt for better image generation results.

    Uses an LLM to enhance the prompt with:
    - More detailed descriptions
    - Style-specific keywords
    - Composition guidance

    Args:
        state: Current image state

    Returns:
        Dict with refined prompt
    """
    original_prompt = state.get("original_prompt") or state.get("query") or ""
    style = state.get("style") or "photorealistic"
    provider = state.get("provider") or LLMProvider.ANTHROPIC

    logger.info("image_refine_prompt", original_prompt=original_prompt[:50], style=style)

    event_list = [create_stage_event("refine", "Refining prompt...", "running")]

    # Get LLM for refinement
    llm = llm_service.get_llm_for_tier(ModelTier.PRO, provider=provider)

    try:
        refine_prompt = IMAGE_REFINE_PROMPT_TEMPLATE.format(
            original_prompt=original_prompt,
            style=style,
        )

        response = await llm.ainvoke([
            SystemMessage(content=IMAGE_SYSTEM_PROMPT),
            HumanMessage(content=refine_prompt),
        ])

        refined = response.content if hasattr(response, "content") else str(response)

        # Clean up the refined prompt (remove any markdown or extra formatting)
        refined = refined.strip()
        if refined.startswith('"') and refined.endswith('"'):
            refined = refined[1:-1]
        if refined.startswith("```"):
            # Remove code blocks if present
            lines = refined.split("\n")
            refined = "\n".join(l for l in lines if not l.startswith("```")).strip()

        event_list.append(create_stage_event("refine", "Prompt refined", "completed"))

        logger.info("image_prompt_refined", original_len=len(original_prompt), refined_len=len(refined))

        return {
            "refined_prompt": refined,
            "events": event_list,
        }

    except Exception as e:
        logger.error("image_refine_failed", error=str(e))
        event_list.append(create_stage_event("refine", f"Refinement failed: {e}", "completed"))
        # Fall back to original prompt
        return {
            "refined_prompt": original_prompt,
            "events": event_list,
        }


async def generate_images_node(state: ImageState) -> dict:
    """Generate images using the selected provider with retry and fallback support.

    Args:
        state: Current image state with refined prompt and parameters

    Returns:
        Dict with generated images and status
    """
    # Use refined prompt if available, otherwise original
    prompt = state.get("refined_prompt") or state.get("original_prompt") or state.get("query") or ""
    size = state.get("size") or "1024x1024"
    quality = state.get("quality") or "standard"
    model = state.get("image_model") or settings.image_gen_model
    provider = state.get("image_provider") or ImageProvider.GEMINI.value

    logger.info(
        "image_generate_start",
        prompt=prompt[:50],
        size=size,
        model=model,
        provider=provider,
        quality=quality,
    )

    event_list = [create_stage_event("generate", "Generating image...", "running")]

    # Content safety check on refined prompt as well
    is_safe, safety_reason = is_prompt_safe(prompt)
    if not is_safe:
        logger.warning("image_refined_prompt_unsafe", prompt=prompt[:50], reason=safety_reason)
        event_list.append(create_stage_event("generate", "Content safety check failed", "failed"))
        return {
            "generated_images": [],
            "generation_status": "failed",
            "generation_error": safety_reason,
            "events": event_list,
        }

    results = None
    last_error = None
    current_model = model
    current_provider = provider
    attempts = 0

    # Retry loop with fallback provider support
    while attempts < MAX_GENERATION_RETRIES:
        attempts += 1
        try:
            logger.info(
                "image_generate_attempt",
                attempt=attempts,
                model=current_model,
                provider=current_provider,
            )

            # Generate the image
            results = await image_generation_service.generate_image(
                prompt=prompt,
                size=size,
                n=1,  # Generate one image
                model=current_model,
                quality=quality,
            )

            if results:
                break  # Success, exit retry loop

            raise ValueError("No images generated")

        except Exception as e:
            last_error = e
            logger.warning(
                "image_generate_attempt_failed",
                attempt=attempts,
                model=current_model,
                provider=current_provider,
                error=str(e),
            )

            # Try fallback provider if available and we have retries left
            if attempts < MAX_GENERATION_RETRIES:
                fallback = get_fallback_provider(current_provider)
                if fallback:
                    current_provider, current_model = fallback
                    event_list.append(
                        create_stage_event(
                            "generate",
                            f"Retrying with {current_provider}...",
                            "running"
                        )
                    )
                    logger.info(
                        "image_generate_fallback",
                        fallback_provider=current_provider,
                        fallback_model=current_model,
                    )
                else:
                    # No fallback available, break out of retry loop
                    break

    if not results:
        error_msg = str(last_error) if last_error else "No images generated"
        logger.error("image_generate_failed_all_attempts", error=error_msg, attempts=attempts)
        event_list.append(create_stage_event("generate", f"Generation failed: {error_msg}", "failed"))
        return {
            "generated_images": [],
            "generation_status": "failed",
            "generation_error": error_msg,
            "events": event_list,
        }

    # Get user_id from state for storage
    user_id = state.get("user_id") or "anonymous"

    # Save images to storage and convert results to dict format
    generated_images = []
    for i, r in enumerate(results):
        img_data = {
            "base64_data": r.base64_data,
            "url": r.url,
            "revised_prompt": r.revised_prompt,
        }

        # Save to storage if we have base64 data
        if r.base64_data:
            try:
                # Decode base64 to bytes
                image_bytes = base64.b64decode(r.base64_data)

                # Save to storage
                storage_result = await file_storage_service.save_generated_image(
                    image_data=image_bytes,
                    user_id=user_id,
                    content_type="image/png",
                    metadata={
                        "prompt": prompt,
                        "model": current_model,
                        "provider": current_provider,
                        "size": size,
                    },
                )

                # Add storage info to image data
                img_data["storage_key"] = storage_result["storage_key"]
                img_data["file_id"] = storage_result["file_id"]
                img_data["url"] = storage_result["url"]

                logger.info(
                    "image_saved_to_storage",
                    file_id=storage_result["file_id"],
                    storage_key=storage_result["storage_key"],
                )
            except Exception as e:
                logger.warning("image_storage_failed", error=str(e), index=i)
                # Continue without storage - fall back to base64

        generated_images.append(img_data)

    # Add image events for each generated image
    # Include URL for persistence, base64 for immediate display
    for i, img in enumerate(generated_images):
        event_data = {
            "type": "image",
            "index": i,
            "mime_type": "image/png",
        }
        # Include URL if available (for persistence)
        if img.get("url"):
            event_data["url"] = img["url"]
        if img.get("storage_key"):
            event_data["storage_key"] = img["storage_key"]
        if img.get("file_id"):
            event_data["file_id"] = img["file_id"]
        # Include base64 for immediate display
        if img.get("base64_data"):
            event_data["data"] = img["base64_data"]

        event_list.append(event_data)

    event_list.append(create_stage_event("generate", "Image generated", "completed"))

    # Count image events in the event list for debugging
    image_events = [e for e in event_list if e.get("type") == "image"]
    logger.info(
        "image_generate_completed",
        image_count=len(generated_images),
        final_model=current_model,
        final_provider=current_provider,
        attempts=attempts,
        image_events_count=len(image_events),
        image_events_have_data=[bool(e.get("data")) for e in image_events],
        image_events_have_url=[bool(e.get("url")) for e in image_events],
    )

    return {
        "generated_images": generated_images,
        "generation_status": "completed",
        "events": event_list,
    }


async def present_results_node(state: ImageState) -> dict:
    """Format and present the generation results to the user.

    Creates a response message with inline image placeholders that will be
    replaced with actual images in the frontend.

    Args:
        state: Current image state with generated images

    Returns:
        Dict with formatted response
    """
    generated_images = state.get("generated_images") or []
    generation_status = state.get("generation_status") or "unknown"
    generation_error = state.get("generation_error")
    original_prompt = state.get("original_prompt") or state.get("query") or ""
    refined_prompt = state.get("refined_prompt") or ""
    style = state.get("style") or ""
    model = state.get("image_model") or ""

    logger.info(
        "image_present_results",
        status=generation_status,
        image_count=len(generated_images),
    )

    event_list = [create_stage_event("present", "Preparing response...", "running")]

    if generation_status == "failed" or not generated_images:
        error_msg = generation_error or "No images were generated"
        response = f"I apologize, but I wasn't able to generate the image. Error: {error_msg}\n\nPlease try rephrasing your request or using a different style."
        event_list.append({"type": "token", "content": response})
        event_list.append(create_stage_event("present", "Presenting error", "completed"))
        return {
            "response": response,
            "events": event_list,
        }

    # Build response with image placeholders
    # The frontend expects markdown image format: ![generated-image:INDEX](placeholder)
    response_parts = []

    # Add a brief description
    if len(generated_images) == 1:
        response_parts.append(f"Here's your generated image based on: \"{original_prompt}\"")
    else:
        response_parts.append(f"Here are {len(generated_images)} generated images based on: \"{original_prompt}\"")

    # Add image placeholders in markdown format that frontend can parse
    for i, img in enumerate(generated_images):
        response_parts.append(f"\n\n![generated-image:{i}](placeholder)")

        # If there's a revised prompt from OpenAI, mention it
        if img.get("revised_prompt") and img["revised_prompt"] != original_prompt:
            response_parts.append(f"\n*The AI enhanced your prompt to: \"{img['revised_prompt'][:200]}...\"*")

    # Add metadata
    if refined_prompt and refined_prompt != original_prompt:
        response_parts.append(f"\n\n**Enhanced prompt used:** {refined_prompt[:300]}{'...' if len(refined_prompt) > 300 else ''}")

    if style:
        response_parts.append(f"\n**Style:** {style}")

    if model:
        response_parts.append(f"\n**Model:** {model}")

    response = "".join(response_parts)

    # NOTE: We emit the response as a token event in the events list (not as real-time streaming)
    # The supervisor will collect and emit these events from the node output
    # Image events are emitted BEFORE the token event so they arrive first
    event_list.append({"type": "token", "content": response})

    event_list.append(create_stage_event("present", "Results presented", "completed"))

    return {
        "response": response,
        "events": event_list,
    }


def should_refine(state: ImageState) -> Literal["refine", "generate"]:
    """Determine if prompt refinement is needed.

    Args:
        state: Current image state

    Returns:
        "refine" if refinement needed, "generate" to skip directly to generation
    """
    return "refine" if state.get("should_refine", True) else "generate"


def create_image_graph() -> StateGraph:
    """Create the image generation subagent graph.

    Graph structure:
    analyze -> [refine (conditional)] -> generate -> present -> END

    Returns:
        Compiled image graph
    """
    graph = StateGraph(ImageState)

    # Add nodes
    graph.add_node("analyze", analyze_request_node)
    graph.add_node("refine", refine_prompt_node)
    graph.add_node("generate", generate_images_node)
    graph.add_node("present", present_results_node)

    # Set entry point
    graph.set_entry_point("analyze")

    # Add conditional edge from analyze: either refine or skip to generate
    graph.add_conditional_edges(
        "analyze",
        should_refine,
        {
            "refine": "refine",
            "generate": "generate",
        },
    )

    # Add edges
    graph.add_edge("refine", "generate")
    graph.add_edge("generate", "present")
    graph.add_edge("present", END)

    return graph.compile()


# Compiled subgraph for use by supervisor
image_subgraph = create_image_graph()
