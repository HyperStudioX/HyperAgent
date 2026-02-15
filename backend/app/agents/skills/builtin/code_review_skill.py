"""Code Review Skill for analyzing code quality."""

from langgraph.graph import StateGraph, END

from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)


class CodeReviewSkill(Skill):
    """Reviews code for bugs, style issues, and best practices."""

    metadata = SkillMetadata(
        id="code_review",
        name="Code Review",
        version="2.0.0",
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
        
        from pydantic import BaseModel, Field

        class CodeIssue(BaseModel):
            """Represents a single issue found in the code."""
            severity: str = Field(description="Severity of the issue: Critical, High, Medium, or Low")
            category: str = Field(description="Category: Bug, Style, Security, Performance, or Best Practice")
            description: str = Field(description="Detailed description of the issue")
            line: int | None = Field(default=None, description="Line number where the issue occurs, if applicable")

        class CodeReviewResponse(BaseModel):
            """Structured code review response."""
            issues: list[CodeIssue] = Field(description="List of issues identified in the code")
            suggestions: list[str] = Field(description="List of specific improvement suggestions")
            rating: str = Field(description="Overall rating: Excellent, Good, Fair, or Needs Improvement")
            summary: str = Field(description="Overall assessment summary of the code quality")

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

Provide a detailed structured code review."""

                # Get LLM for code review
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)
                
                # Use structured output
                structured_llm = llm.with_structured_output(CodeReviewResponse)
                
                # Generate review
                result: CodeReviewResponse = await structured_llm.ainvoke(prompt)

                # Convert Pydantic models to dicts for output schema compliance
                issues_list = [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "description": issue.description,
                        "line": issue.line,
                    }
                    for issue in result.issues
                ]

                logger.info(
                    "code_review_skill_completed",
                    issues_count=len(issues_list),
                    suggestions_count=len(result.suggestions),
                    rating=result.rating,
                )

                return {
                    "output": {
                        "issues": issues_list,
                        "suggestions": result.suggestions,
                        "rating": result.rating,
                        "summary": result.summary,
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
