"""Task Planning Skill for decomposing complex tasks into executable steps."""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.skills.skill_base import (
    SkillContext,
    SkillMetadata,
    SkillParameter,
    ToolSkill,
)
from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger

logger = get_logger(__name__)


class PlanStep(BaseModel):
    """A single step in the task plan."""

    step_number: int = Field(description="Sequential step number starting from 1")
    action: str = Field(description="Clear, actionable description of what to do")
    tool_or_skill: str | None = Field(
        default=None,
        description="Recommended tool or skill to use (e.g., 'web_search', 'invoke_skill')",
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="List of step numbers this step depends on (must complete first)",
    )
    estimated_complexity: str = Field(
        default="medium",
        description="Complexity level: 'low', 'medium', or 'high'",
    )


class TaskPlan(BaseModel):
    """Complete task plan with analysis and steps."""

    task_summary: str = Field(description="Brief summary of the task being planned")
    complexity_assessment: str = Field(
        description="Overall complexity: 'simple', 'moderate', or 'complex'"
    )
    steps: list[PlanStep] = Field(description="Ordered list of steps to complete the task")
    success_criteria: list[str] = Field(
        description="Criteria to determine if the task is successfully completed"
    )
    potential_challenges: list[str] = Field(
        default_factory=list,
        description="Potential challenges or blockers to watch for",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Questions to ask the user if requirements are ambiguous",
    )


class TaskPlanningSkill(ToolSkill):
    """Decomposes complex tasks into structured, executable plans.

    This skill analyzes a task description and produces a detailed plan with:
    - Step-by-step breakdown with dependencies
    - Tool/skill recommendations for each step
    - Complexity assessment
    - Success criteria
    - Potential challenges

    Use this skill when facing multi-step tasks that benefit from upfront planning.
    """

    metadata = SkillMetadata(
        id="task_planning",
        name="Task Planning",
        version="1.0.0",
        description="Analyzes complex tasks and creates structured execution plans",
        category="automation",
        parameters=[
            SkillParameter(
                name="task_description",
                type="string",
                description="Detailed description of the task to plan",
                required=True,
            ),
            SkillParameter(
                name="context",
                type="string",
                description="Additional context about environment or constraints",
                required=False,
                default="",
            ),
            SkillParameter(
                name="available_tools",
                type="array",
                description="List of available tools/skills the plan can reference",
                required=False,
                default=None,
            ),
            SkillParameter(
                name="max_steps",
                type="number",
                description="Maximum number of steps in the plan (default: 10)",
                required=False,
                default=10,
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "task_summary": {
                    "type": "string",
                    "description": "Brief summary of the task",
                },
                "complexity_assessment": {
                    "type": "string",
                    "enum": ["simple", "moderate", "complex"],
                    "description": "Overall task complexity",
                },
                "steps": {
                    "type": "array",
                    "description": "Ordered list of execution steps",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "integer"},
                            "action": {"type": "string"},
                            "tool_or_skill": {"type": "string"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                            "estimated_complexity": {"type": "string"},
                        },
                    },
                },
                "success_criteria": {
                    "type": "array",
                    "description": "Criteria for task completion",
                    "items": {"type": "string"},
                },
                "potential_challenges": {
                    "type": "array",
                    "description": "Potential blockers or challenges",
                    "items": {"type": "string"},
                },
                "clarifying_questions": {
                    "type": "array",
                    "description": "Questions if requirements are unclear",
                    "items": {"type": "string"},
                },
            },
        },
        required_tools=[],
        max_iterations=2,
        max_execution_time_seconds=60,
        tags=["planning", "task-decomposition", "automation", "orchestration"],
    )

    async def execute(self, params: dict[str, Any], context: SkillContext) -> dict[str, Any]:
        """Analyze the task and create a structured plan."""
        task_description = params["task_description"]
        extra_context = params.get("context", "")
        available_tools = params.get("available_tools")
        max_steps = int(params.get("max_steps", 10))

        logger.info(
            "task_planning_skill_analyzing",
            task_length=len(task_description),
            has_context=bool(extra_context),
            max_steps=max_steps,
        )

        # Build the planning prompt
        tools_section = ""
        if available_tools:
            tools_section = f"""
Available Tools and Skills:
{chr(10).join(f"- {tool}" for tool in available_tools)}

When recommending tools, prefer those from this list.
"""
        else:
            tools_section = """
Common Tools Available:
- web_search: Search the web for information
- execute_code: Run Python/JavaScript code
- generate_image: Create AI-generated images
- browser_navigate: Navigate to web pages
- invoke_skill: Call skills (web_research, code_generation, data_analysis, etc.)

When recommending tools, consider which would be most effective for each step.
"""

        context_section = ""
        if extra_context:
            context_section = f"""
Additional Context:
{extra_context}
"""

        prompt = f"""You are a task planning expert. Analyze the following task and \
create a detailed, actionable execution plan.

Task Description:
{task_description}
{context_section}
{tools_section}

Guidelines for creating the plan:
1. Break down the task into clear, atomic steps (maximum {max_steps} steps)
2. Each step should be independently executable
3. Identify dependencies between steps (which steps must complete before others)
4. Recommend the most appropriate tool or skill for each step
5. Assess complexity realistically
6. Include clear success criteria so we know when the task is complete
7. Identify potential challenges or blockers proactively
8. If requirements are ambiguous, list clarifying questions

Important:
- Steps should be concrete and actionable, not vague
- Prefer parallel execution where dependencies allow
- Consider error handling and fallback approaches
- Keep the plan focused on achieving the stated goal"""

        llm = llm_service.get_llm_for_tier(ModelTier.PRO)
        structured_llm = llm.with_structured_output(TaskPlan)

        result: TaskPlan = await structured_llm.ainvoke(prompt)

        # Convert to dict for output
        output = {
            "task_summary": result.task_summary,
            "complexity_assessment": result.complexity_assessment,
            "steps": [step.model_dump() for step in result.steps],
            "success_criteria": result.success_criteria,
            "potential_challenges": result.potential_challenges,
            "clarifying_questions": result.clarifying_questions,
        }

        logger.info(
            "task_planning_skill_completed",
            step_count=len(result.steps),
            complexity=result.complexity_assessment,
            has_questions=len(result.clarifying_questions) > 0,
        )

        return output
