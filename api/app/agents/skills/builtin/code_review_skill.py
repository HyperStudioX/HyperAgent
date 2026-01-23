"""Code Review Skill for analyzing code quality."""

from langgraph.graph import StateGraph, END

from app.ai.llm import LLMService
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)
llm_service = LLMService()


class CodeReviewSkill(Skill):
    """Reviews code for bugs, style issues, and best practices."""

    metadata = SkillMetadata(
        id="code_review",
        name="Code Review",
        version="1.0.0",
        description="Reviews code for bugs, style issues, security vulnerabilities, and best practices",
        category="code",
        parameters=[
            SkillParameter(
                name="code",
                type="string",
                description="Code to review",
                required=True,
            ),
            SkillParameter(
                name="language",
                type="string",
                description="Programming language (e.g., python, javascript, typescript, java)",
                required=False,
                default="python",
            ),
            SkillParameter(
                name="focus",
                type="string",
                description="Review focus: all, bugs, style, security, performance",
                required=False,
                default="all",
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "issues": {
                    "type": "array",
                    "description": "List of identified issues",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string"},
                            "category": {"type": "string"},
                            "description": {"type": "string"},
                            "line": {"type": "number"},
                        },
                    },
                },
                "suggestions": {
                    "type": "array",
                    "description": "Improvement suggestions",
                    "items": {"type": "string"},
                },
                "rating": {
                    "type": "string",
                    "description": "Overall code quality rating",
                },
                "summary": {
                    "type": "string",
                    "description": "Summary of the review",
                },
            },
        },
        max_iterations=2,
        tags=["code", "review", "quality"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for code review."""
        graph = StateGraph(SkillState)

        async def review_node(state: SkillState) -> dict:
            """Perform code review."""
            code = state["input_params"]["code"]
            language = state["input_params"].get("language", "python")
            focus = state["input_params"].get("focus", "all")

            logger.info("code_review_skill_reviewing", language=language, focus=focus)

            try:
                # Build review prompt
                focus_instructions = {
                    "all": "bugs, style issues, security vulnerabilities, performance problems, and best practices",
                    "bugs": "potential bugs and logic errors",
                    "style": "code style and formatting issues",
                    "security": "security vulnerabilities and unsafe practices",
                    "performance": "performance issues and optimization opportunities",
                }

                focus_desc = focus_instructions.get(focus, focus_instructions["all"])

                prompt = f"""Review this {language} code for {focus_desc}.

Code:
```{language}
{code}
```

Provide a detailed code review in the following format:

ISSUES:
- [SEVERITY: Critical/High/Medium/Low] [CATEGORY: Bug/Style/Security/Performance] Line X: Description

SUGGESTIONS:
- Specific improvement suggestion 1
- Specific improvement suggestion 2
- Specific improvement suggestion 3

RATING: [Excellent/Good/Fair/Needs Improvement]

SUMMARY:
Overall assessment of the code quality and main recommendations.
"""

                # Get LLM for code review
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)

                # Generate review
                response = await llm.ainvoke(prompt)
                content = response.content

                # Parse response
                issues = []
                suggestions = []
                rating = "Good"
                summary = ""

                sections = {
                    "ISSUES:": "",
                    "SUGGESTIONS:": "",
                    "RATING:": "",
                    "SUMMARY:": "",
                }

                # Extract sections
                current_section = None
                for line in content.split("\n"):
                    line = line.strip()
                    if line in sections:
                        current_section = line
                        continue
                    if current_section and line:
                        sections[current_section] += line + "\n"

                # Parse issues
                issues_text = sections.get("ISSUES:", "")
                for line in issues_text.split("\n"):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("•"):
                        # Try to parse: [SEVERITY: X] [CATEGORY: Y] Line Z: Description
                        line = line.lstrip("-").lstrip("•").strip()
                        severity = "Medium"
                        category = "General"
                        line_num = None
                        description = line

                        if "[SEVERITY:" in line.upper():
                            try:
                                severity_end = line.index("]", line.upper().index("[SEVERITY:"))
                                severity = line[line.upper().index("[SEVERITY:") + 10:severity_end].strip()
                                line = line[severity_end + 1:].strip()
                            except (ValueError, IndexError):
                                pass

                        if "[CATEGORY:" in line.upper():
                            try:
                                category_end = line.index("]", line.upper().index("[CATEGORY:"))
                                category = line[line.upper().index("[CATEGORY:") + 10:category_end].strip()
                                line = line[category_end + 1:].strip()
                            except (ValueError, IndexError):
                                pass

                        if "LINE" in line.upper():
                            try:
                                parts = line.split(":", 1)
                                if len(parts) == 2:
                                    line_part = parts[0].strip()
                                    if "LINE" in line_part.upper():
                                        line_num_str = "".join(c for c in line_part if c.isdigit())
                                        if line_num_str:
                                            line_num = int(line_num_str)
                                    description = parts[1].strip()
                            except (ValueError, IndexError):
                                pass

                        issues.append({
                            "severity": severity,
                            "category": category,
                            "line": line_num,
                            "description": description,
                        })

                # Parse suggestions
                suggestions_text = sections.get("SUGGESTIONS:", "")
                for line in suggestions_text.split("\n"):
                    line = line.strip()
                    if line.startswith("-") or line.startswith("•"):
                        suggestions.append(line.lstrip("-").lstrip("•").strip())

                # Parse rating
                rating_text = sections.get("RATING:", "").strip()
                if rating_text:
                    rating = rating_text

                # Parse summary
                summary = sections.get("SUMMARY:", "").strip()

                logger.info(
                    "code_review_skill_completed",
                    issues_count=len(issues),
                    suggestions_count=len(suggestions),
                    rating=rating,
                )

                return {
                    "output": {
                        "issues": issues,
                        "suggestions": suggestions,
                        "rating": rating,
                        "summary": summary,
                    },
                    "iterations": state["iterations"] + 1,
                }

            except Exception as e:
                logger.error("code_review_skill_failed", error=str(e))
                return {
                    "error": f"Code review failed: {str(e)}",
                    "iterations": state["iterations"] + 1,
                }

        # Build graph
        graph.add_node("review", review_node)
        graph.set_entry_point("review")
        graph.add_edge("review", END)

        return graph.compile()
