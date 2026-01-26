"""Image Generation Skill for creating AI-generated images."""

import base64

from langgraph.graph import END, StateGraph

from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState
from app.ai.image import image_generation_service
from app.core.logging import get_logger
from app.services.file_storage import file_storage_service

logger = get_logger(__name__)


class ImageGenerationSkill(Skill):
    """Generates AI images from text descriptions."""

    metadata = SkillMetadata(
        id="image_generation",
        name="Image Generation",
        version="1.0.0",
        description=(
            "Generates high-quality images from text descriptions "
            "using AI (Gemini/Imagen or DALL-E)"
        ),
        category="creative",
        parameters=[
            SkillParameter(
                name="prompt",
                type="string",
                description=(
                    "Detailed description of the image to generate. "
                    "Be specific about style, composition, colors, and subject."
                ),
                required=True,
            ),
            SkillParameter(
                name="size",
                type="string",
                description=(
                    "Image size: 1024x1024 (square), 1792x1024 (landscape), "
                    "1024x1792 (portrait), or smaller sizes"
                ),
                required=False,
                default="1024x1024",
            ),
            SkillParameter(
                name="n",
                type="number",
                description="Number of images to generate (1-4)",
                required=False,
                default=1,
            ),
            SkillParameter(
                name="model",
                type="string",
                description="Model: gemini-3-pro-image-preview, dall-e-3, or dall-e-2",
                required=False,
                default=None,
            ),
            SkillParameter(
                name="quality",
                type="string",
                description="Quality for DALL-E 3: standard or hd",
                required=False,
                default="standard",
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "images": {
                    "type": "array",
                    "description": "Generated images with storage URLs",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to access the stored image",
                            },
                            "storage_key": {
                                "type": "string",
                                "description": "Storage key for the image",
                            },
                            "base64_data": {
                                "type": "string",
                                "description": "Base64 encoded image data",
                            },
                            "index": {"type": "number"},
                        },
                    },
                },
                "prompt": {"type": "string", "description": "The prompt used"},
                "count": {"type": "number", "description": "Number of images generated"},
            },
        },
        required_tools=[],
        max_iterations=1,
        tags=["image", "creative", "generation", "ai-art"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for image generation."""
        graph = StateGraph(SkillState)

        async def generate_node(state: SkillState) -> dict:
            """Generate images from prompt."""
            prompt = state["input_params"]["prompt"]
            size = state["input_params"].get("size", "1024x1024")
            n = int(state["input_params"].get("n", 1))
            model = state["input_params"].get("model")
            quality = state["input_params"].get("quality", "standard")
            user_id = state.get("user_id")

            logger.info(
                "image_generation_skill_generating",
                prompt=prompt[:100],
                size=size,
                n=n,
                model=model,
                user_id=user_id,
            )

            try:
                # Generate images using the image generation service
                results = await image_generation_service.generate_image(
                    prompt=prompt,
                    size=size,
                    n=n,
                    model=model,
                    quality=quality,
                )

                if not results:
                    return {
                        "error": "No images generated",
                        "iterations": state["iterations"] + 1,
                    }

                # Save images to storage and format output
                images = []
                for i, result in enumerate(results):
                    image_data = {
                        "base64_data": result.base64_data,
                        "index": i,
                    }

                    # Save to storage if user_id is available
                    if user_id:
                        try:
                            # Decode base64 to bytes
                            image_bytes = base64.b64decode(result.base64_data)

                            # Save to storage
                            storage_result = await file_storage_service.save_generated_image(
                                image_data=image_bytes,
                                user_id=user_id,
                                content_type="image/png",
                                metadata={
                                    "prompt": prompt,
                                    "model": model or "default",
                                    "size": size,
                                    "index": i,
                                },
                            )

                            # Add storage information to output
                            image_data["url"] = storage_result["url"]
                            image_data["storage_key"] = storage_result["storage_key"]

                            logger.info(
                                "image_saved_to_storage",
                                storage_key=storage_result["storage_key"],
                                user_id=user_id,
                            )
                        except Exception as e:
                            logger.warning(
                                "image_storage_failed",
                                error=str(e),
                                index=i,
                            )
                            # Continue without storage - base64 data is still available
                    else:
                        logger.warning(
                            "image_not_saved_no_user_id",
                            index=i,
                        )

                    images.append(image_data)

                logger.info(
                    "image_generation_skill_completed",
                    prompt=prompt[:50],
                    image_count=len(images),
                )

                return {
                    "output": {
                        "images": images,
                        "prompt": prompt,
                        "count": len(images),
                    },
                    "iterations": state["iterations"] + 1,
                }

            except Exception as e:
                logger.error("image_generation_skill_failed", error=str(e))
                return {
                    "error": f"Image generation failed: {str(e)}",
                    "iterations": state["iterations"] + 1,
                }

        # Build graph
        graph.add_node("generate", generate_node)
        graph.set_entry_point("generate")
        graph.add_edge("generate", END)

        return graph.compile()
