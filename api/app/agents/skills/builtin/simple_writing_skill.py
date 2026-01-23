"""Simple Writing Skill for creating documents, emails, and content."""

from langgraph.graph import StateGraph, END

from app.ai.llm import LLMService
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)
llm_service = LLMService()


class SimpleWritingSkill(Skill):
    """Creates written content like documents, emails, articles, and more."""

    metadata = SkillMetadata(
        id="simple_writing",
        name="Simple Writing",
        version="1.0.0",
        description="Creates written content including documents, emails, articles, summaries, and more with specified tone and style",
        category="creative",
        parameters=[
            SkillParameter(
                name="task",
                type="string",
                description="Description of what to write (e.g., 'email to team about project update', 'blog post about AI')",
                required=True,
            ),
            SkillParameter(
                name="writing_type",
                type="string",
                description="Type of content: email, article, document, summary, creative, technical, documentation",
                required=False,
                default="document",
            ),
            SkillParameter(
                name="tone",
                type="string",
                description="Tone: professional, casual, formal, friendly, persuasive, informative",
                required=False,
                default="professional",
            ),
            SkillParameter(
                name="length",
                type="string",
                description="Desired length: short (1-2 paragraphs), medium (3-5 paragraphs), long (6+ paragraphs)",
                required=False,
                default="medium",
            ),
            SkillParameter(
                name="context",
                type="string",
                description="Additional context or requirements for the writing",
                required=False,
                default="",
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The generated written content",
                },
                "title": {
                    "type": "string",
                    "description": "Suggested title or subject line",
                },
                "word_count": {
                    "type": "number",
                    "description": "Approximate word count",
                },
            },
        },
        required_tools=[],
        max_iterations=2,
        tags=["writing", "content", "creative", "document"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for writing."""
        graph = StateGraph(SkillState)

        async def write_node(state: SkillState) -> dict:
            """Generate written content."""
            task = state["input_params"]["task"]
            writing_type = state["input_params"].get("writing_type", "document")
            tone = state["input_params"].get("tone", "professional")
            length = state["input_params"].get("length", "medium")
            context = state["input_params"].get("context", "")

            logger.info(
                "simple_writing_skill_generating",
                writing_type=writing_type,
                tone=tone,
                length=length,
            )

            try:
                # Map length to word count guidance
                length_guidance = {
                    "short": "1-2 paragraphs (100-200 words)",
                    "medium": "3-5 paragraphs (300-500 words)",
                    "long": "6+ paragraphs (600+ words)",
                }
                length_desc = length_guidance.get(length, length_guidance["medium"])

                # Build writing prompt
                context_section = f"\n\nAdditional Context:\n{context}" if context else ""

                prompt = f"""Write {writing_type} content with the following requirements:

Task: {task}

Writing Type: {writing_type}
Tone: {tone}
Length: {length_desc}{context_section}

Please provide:
1. A suitable title or subject line
2. Well-structured content that fulfills the task
3. Proper formatting with paragraphs and sections as needed

Format your response as:

TITLE:
[Your title/subject line here]

CONTENT:
[Your written content here]
"""

                # Get LLM for writing
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)

                # Generate content
                response = await llm.ainvoke(prompt)
                content_text = response.content

                # Parse response
                title = ""
                content = content_text

                if "TITLE:" in content_text and "CONTENT:" in content_text:
                    parts = content_text.split("CONTENT:", 1)
                    title_part = parts[0].replace("TITLE:", "").strip()
                    content = parts[1].strip()
                    title = title_part
                else:
                    # Try to extract first line as title
                    lines = content_text.split("\n", 1)
                    if len(lines) > 1:
                        title = lines[0].strip().lstrip("#").strip()
                        content = lines[1].strip()

                # Count words
                word_count = len(content.split())

                logger.info(
                    "simple_writing_skill_completed",
                    writing_type=writing_type,
                    word_count=word_count,
                )

                return {
                    "output": {
                        "content": content,
                        "title": title,
                        "word_count": word_count,
                    },
                    "iterations": state["iterations"] + 1,
                }

            except Exception as e:
                logger.error("simple_writing_skill_failed", error=str(e))
                return {
                    "error": f"Writing generation failed: {str(e)}",
                    "iterations": state["iterations"] + 1,
                }

        # Build graph
        graph.add_node("write", write_node)
        graph.set_entry_point("write")
        graph.add_edge("write", END)

        return graph.compile()
