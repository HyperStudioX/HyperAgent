"""Image Generation Skill for creating AI-generated images."""

from langgraph.graph import StateGraph, END

from app.ai.image import image_generation_service
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)


class ImageGenerationSkill(Skill):
    """Generates AI images from text descriptions."""

    metadata = SkillMetadata(
        id="image_generation",
        name="Image Generation",
        version="1.0.0",
        description="Generates high-quality images from text descriptions using AI (Gemini/Imagen or DALL-E)",
        category="creative",
        parameters=[
            SkillParameter(
                name="prompt",
                type="string",
                description="Detailed description of the image to generate. Be specific about style, composition, colors, and subject.",
                required=True,
            ),
            SkillParameter(
                name="size",
                type="string",
                description="Image size: 1024x1024 (square), 1792x1024 (landscape), 1024x1792 (portrait), or smaller sizes",
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
                    "description": "Generated images",
                    "items": {
                        "type": "object",
                        "properties": {
                            "base64_data": {"type": "string"},
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

            logger.info(
                "image_generation_skill_generating",
                prompt=prompt[:100],
                size=size,
                n=n,
                model=model,
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

                # Format images for output
                images = [
                    {
                        "base64_data": result.base64_data,
                        "index": i,
                    }
                    for i, result in enumerate(results)
                ]

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
