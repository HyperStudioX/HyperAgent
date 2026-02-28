"""Tests for the TaskPlanningSkill."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.skills.builtin.task_planning_skill import (
    PlanStep,
    TaskPlan,
    TaskPlanningSkill,
)
from app.agents.skills.skill_base import Skill, SkillContext, SkillState, ToolSkill


class TestTaskPlanningSkillMetadata:
    """Tests for TaskPlanningSkill metadata and validation."""

    @pytest.fixture
    def skill(self):
        return TaskPlanningSkill()

    def test_skill_metadata(self, skill):
        """Skill should have correct metadata."""
        assert skill.metadata.id == "task_planning"
        assert skill.metadata.name == "Task Planning"
        assert skill.metadata.category == "automation"
        assert skill.metadata.version == "1.0.0"

    def test_skill_parameters(self, skill):
        """Skill should have expected parameters."""
        param_names = [p.name for p in skill.metadata.parameters]
        assert "task_description" in param_names
        assert "context" in param_names
        assert "available_tools" in param_names
        assert "max_steps" in param_names

    def test_task_description_required(self, skill):
        """task_description parameter should be required."""
        task_desc_param = next(p for p in skill.metadata.parameters if p.name == "task_description")
        assert task_desc_param.required is True

    def test_context_optional(self, skill):
        """context parameter should be optional."""
        context_param = next(p for p in skill.metadata.parameters if p.name == "context")
        assert context_param.required is False

    def test_skill_tags(self, skill):
        """Skill should have relevant tags."""
        assert "planning" in skill.metadata.tags
        assert "task-decomposition" in skill.metadata.tags
        assert "automation" in skill.metadata.tags

    def test_is_simple_skill(self, skill):
        """TaskPlanningSkill should be a ToolSkill instance."""
        assert isinstance(skill, ToolSkill)

    def test_is_still_skill(self, skill):
        """TaskPlanningSkill should still be a Skill instance (backward compat)."""
        assert isinstance(skill, Skill)


class TestTaskPlanningSkillValidation:
    """Tests for input validation."""

    @pytest.fixture
    def skill(self):
        return TaskPlanningSkill()

    def test_valid_input_minimal(self, skill):
        """Valid input with only required params should pass."""
        is_valid, error = skill.validate_input({"task_description": "Build a todo app"})
        assert is_valid is True
        assert error == ""

    def test_valid_input_full(self, skill):
        """Valid input with all params should pass."""
        is_valid, error = skill.validate_input(
            {
                "task_description": "Build a todo app",
                "context": "Using React and TypeScript",
                "available_tools": ["web_search", "execute_code"],
                "max_steps": 8,
            }
        )
        assert is_valid is True
        assert error == ""

    def test_missing_required_param(self, skill):
        """Missing required param should fail validation."""
        is_valid, error = skill.validate_input({"context": "Some context without task description"})
        assert is_valid is False
        assert "task_description" in error

    def test_wrong_type_task_description(self, skill):
        """Wrong type for task_description should fail."""
        is_valid, error = skill.validate_input(
            {
                "task_description": 123  # Should be string
            }
        )
        assert is_valid is False
        assert "task_description" in error

    def test_wrong_type_max_steps(self, skill):
        """Wrong type for max_steps should fail."""
        is_valid, error = skill.validate_input(
            {
                "task_description": "Build an app",
                "max_steps": "ten",  # Should be number
            }
        )
        assert is_valid is False
        assert "max_steps" in error

    def test_wrong_type_available_tools(self, skill):
        """Wrong type for available_tools should fail."""
        is_valid, error = skill.validate_input(
            {
                "task_description": "Build an app",
                "available_tools": "web_search",  # Should be array
            }
        )
        assert is_valid is False
        assert "available_tools" in error


class TestPlanStepModel:
    """Tests for PlanStep Pydantic model."""

    def test_plan_step_defaults(self):
        """PlanStep should have correct defaults."""
        step = PlanStep(step_number=1, action="Do something")
        assert step.step_number == 1
        assert step.action == "Do something"
        assert step.tool_or_skill is None
        assert step.depends_on == []
        assert step.estimated_complexity == "medium"

    def test_plan_step_full(self):
        """PlanStep with all fields."""
        step = PlanStep(
            step_number=2,
            action="Search for information",
            tool_or_skill="web_search",
            depends_on=[1],
            estimated_complexity="low",
        )
        assert step.step_number == 2
        assert step.tool_or_skill == "web_search"
        assert step.depends_on == [1]
        assert step.estimated_complexity == "low"


class TestTaskPlanModel:
    """Tests for TaskPlan Pydantic model."""

    def test_task_plan_minimal(self):
        """TaskPlan with minimal fields."""
        plan = TaskPlan(
            task_summary="Build a todo app",
            complexity_assessment="moderate",
            steps=[PlanStep(step_number=1, action="Step 1")],
            success_criteria=["App works"],
        )
        assert plan.task_summary == "Build a todo app"
        assert plan.complexity_assessment == "moderate"
        assert len(plan.steps) == 1
        assert plan.potential_challenges == []
        assert plan.clarifying_questions == []

    def test_task_plan_full(self):
        """TaskPlan with all fields."""
        plan = TaskPlan(
            task_summary="Build a complex dashboard",
            complexity_assessment="complex",
            steps=[
                PlanStep(step_number=1, action="Research"),
                PlanStep(step_number=2, action="Design", depends_on=[1]),
            ],
            success_criteria=["Dashboard loads", "Shows data"],
            potential_challenges=["API rate limits"],
            clarifying_questions=["Which charting library?"],
        )
        assert len(plan.steps) == 2
        assert len(plan.success_criteria) == 2
        assert len(plan.potential_challenges) == 1
        assert len(plan.clarifying_questions) == 1


class TestTaskPlanningSkillExecution:
    """Tests for skill graph execution with mocked LLM."""

    @pytest.fixture
    def skill(self):
        return TaskPlanningSkill()

    @pytest.fixture
    def mock_task_plan(self):
        """Create a mock TaskPlan response."""
        return TaskPlan(
            task_summary="Build a simple web scraper",
            complexity_assessment="moderate",
            steps=[
                PlanStep(
                    step_number=1,
                    action="Research target website structure",
                    tool_or_skill="web_search",
                    depends_on=[],
                    estimated_complexity="low",
                ),
                PlanStep(
                    step_number=2,
                    action="Write scraping code",
                    tool_or_skill="code_generation",
                    depends_on=[1],
                    estimated_complexity="medium",
                ),
                PlanStep(
                    step_number=3,
                    action="Test and refine the scraper",
                    tool_or_skill="execute_code",
                    depends_on=[2],
                    estimated_complexity="medium",
                ),
            ],
            success_criteria=[
                "Scraper extracts required data",
                "Code handles errors gracefully",
            ],
            potential_challenges=[
                "Website may have anti-scraping measures",
                "Dynamic content may require browser automation",
            ],
            clarifying_questions=[],
        )

    @pytest.mark.asyncio
    async def test_skill_execution_success(self, skill, mock_task_plan):
        """Test successful skill execution with mocked LLM."""
        # Create initial state
        initial_state: SkillState = {
            "skill_id": "task_planning",
            "input_params": {
                "task_description": "Build a web scraper to extract product prices",
                "max_steps": 5,
            },
            "output": {},
            "error": None,
            "events": [],
            "iterations": 0,
            "user_id": "test_user",
            "task_id": "test_task",
        }

        # Mock the LLM service
        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_task_plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)

            # Execute the graph
            graph = skill.create_graph()
            final_state = await graph.ainvoke(initial_state)

        # Verify output
        assert final_state["error"] is None
        assert "output" in final_state
        output = final_state["output"]

        assert output["task_summary"] == "Build a simple web scraper"
        assert output["complexity_assessment"] == "moderate"
        assert len(output["steps"]) == 3
        assert len(output["success_criteria"]) == 2
        assert len(output["potential_challenges"]) == 2

        # Verify step structure
        first_step = output["steps"][0]
        assert first_step["step_number"] == 1
        assert first_step["tool_or_skill"] == "web_search"
        assert first_step["depends_on"] == []

    @pytest.mark.asyncio
    async def test_skill_execution_with_context(self, skill, mock_task_plan):
        """Test skill execution with additional context."""
        initial_state: SkillState = {
            "skill_id": "task_planning",
            "input_params": {
                "task_description": "Build a web scraper",
                "context": "Use Python with BeautifulSoup",
                "available_tools": ["web_search", "execute_code"],
            },
            "output": {},
            "error": None,
            "events": [],
            "iterations": 0,
            "user_id": "test_user",
            "task_id": None,
        }

        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_task_plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)

            graph = skill.create_graph()
            await graph.ainvoke(initial_state)

        # Verify LLM was called (context should be in prompt)
        mock_structured_llm.ainvoke.assert_called_once()
        prompt = mock_structured_llm.ainvoke.call_args[0][0]
        assert "Use Python with BeautifulSoup" in prompt
        assert "web_search" in prompt

    @pytest.mark.asyncio
    async def test_skill_execution_llm_error(self, skill):
        """Test skill handles LLM errors gracefully."""
        initial_state: SkillState = {
            "skill_id": "task_planning",
            "input_params": {
                "task_description": "Build something",
            },
            "output": {},
            "error": None,
            "events": [],
            "iterations": 0,
            "user_id": "test_user",
            "task_id": None,
        }

        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(side_effect=Exception("LLM service unavailable"))
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)

            graph = skill.create_graph()
            final_state = await graph.ainvoke(initial_state)

        # Verify error is captured
        assert final_state["error"] is not None
        assert "LLM service unavailable" in final_state["error"]

    @pytest.mark.asyncio
    async def test_direct_execute_success(self, skill, mock_task_plan):
        """Test calling execute() directly (ToolSkill API)."""
        params = {
            "task_description": "Build a web scraper to extract product prices",
            "max_steps": 5,
        }
        context = SkillContext(
            skill_id="task_planning",
            user_id="test_user",
            task_id="test_task",
        )

        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_task_plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)
            output = await skill.execute(params, context)

        assert output["task_summary"] == "Build a simple web scraper"
        assert output["complexity_assessment"] == "moderate"
        assert len(output["steps"]) == 3


class TestTaskPlanningRevisionMode:
    """Tests for plan revision mode."""

    @pytest.fixture
    def skill(self):
        return TaskPlanningSkill()

    @pytest.fixture
    def mock_revised_plan(self):
        """Create a mock revised TaskPlan response."""
        return TaskPlan(
            task_summary="Revised: Build a web scraper (alternative approach)",
            complexity_assessment="moderate",
            steps=[
                PlanStep(
                    step_number=2,
                    action="Use requests library instead of urllib",
                    tool_or_skill="execute_code",
                    depends_on=[],
                    estimated_complexity="medium",
                ),
                PlanStep(
                    step_number=3,
                    action="Parse with lxml as fallback",
                    tool_or_skill="execute_code",
                    depends_on=[2],
                    estimated_complexity="medium",
                ),
            ],
            success_criteria=["Scraper works with alternative approach"],
            potential_challenges=["May need to handle encoding issues"],
            clarifying_questions=[],
        )

    def test_revision_parameters_exist(self, skill):
        """Skill should have revision_mode, completed_steps, failed_steps parameters."""
        param_names = [p.name for p in skill.metadata.parameters]
        assert "revision_mode" in param_names
        assert "completed_steps" in param_names
        assert "failed_steps" in param_names

    def test_revision_parameters_optional(self, skill):
        """Revision parameters should all be optional."""
        for param in skill.metadata.parameters:
            if param.name in ("revision_mode", "completed_steps", "failed_steps"):
                assert param.required is False

    @pytest.mark.asyncio
    async def test_revision_mode_execution(self, skill, mock_revised_plan):
        """Test skill execution in revision mode with completed/failed steps."""
        params = {
            "task_description": "Build a web scraper",
            "revision_mode": True,
            "completed_steps": [
                {"step_number": 1, "action": "Search for libraries", "result_summary": "Found BeautifulSoup"},
            ],
            "failed_steps": [
                {"step_number": 2, "action": "Write scraping code with urllib", "error": "SSL certificate error"},
            ],
        }
        context = SkillContext(
            skill_id="task_planning",
            user_id="test_user",
            task_id="test_task",
        )

        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_revised_plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)
            output = await skill.execute(params, context)

        # Verify revision output
        assert output["is_revision"] is True
        assert len(output["steps"]) == 2
        assert output["task_summary"] == "Revised: Build a web scraper (alternative approach)"

        # Verify the revision prompt was built correctly
        prompt = mock_structured_llm.ainvoke.call_args[0][0]
        assert "Revise the plan" in prompt
        assert "Search for libraries" in prompt
        assert "SSL certificate error" in prompt
        assert "do not repeat the same approach" in prompt.lower()

    @pytest.mark.asyncio
    async def test_revision_mode_false_uses_normal_prompt(self, skill):
        """When revision_mode is False, should use normal planning prompt."""
        params = {
            "task_description": "Build a todo app",
            "revision_mode": False,
        }
        context = SkillContext(
            skill_id="task_planning",
            user_id="test_user",
            task_id="test_task",
        )

        mock_plan = TaskPlan(
            task_summary="Build a todo app",
            complexity_assessment="simple",
            steps=[PlanStep(step_number=1, action="Create app")],
            success_criteria=["App works"],
        )

        mock_llm = MagicMock()
        mock_structured_llm = AsyncMock()
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_plan)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

        with patch("app.agents.skills.builtin.task_planning_skill.llm_service") as mock_service:
            mock_service.get_llm_for_tier = MagicMock(return_value=mock_llm)
            output = await skill.execute(params, context)

        assert "is_revision" not in output
        prompt = mock_structured_llm.ainvoke.call_args[0][0]
        assert "Revise the plan" not in prompt

    def test_build_revision_prompt_includes_completed_steps(self, skill):
        """_build_revision_prompt should include completed step details."""
        prompt = TaskPlanningSkill._build_revision_prompt(
            task_description="Build a scraper",
            completed_steps=[
                {"step_number": 1, "action": "Search libs", "result_summary": "Found BS4"},
            ],
            failed_steps=[],
            context_section="",
            tools_section="",
            max_steps=10,
        )
        assert "Steps already completed successfully" in prompt
        assert "Step 1: Search libs" in prompt
        assert "Found BS4" in prompt

    def test_build_revision_prompt_includes_failed_steps(self, skill):
        """_build_revision_prompt should include failed step details."""
        prompt = TaskPlanningSkill._build_revision_prompt(
            task_description="Build a scraper",
            completed_steps=[],
            failed_steps=[
                {"step_number": 2, "action": "Write code", "error": "Import error"},
            ],
            context_section="",
            tools_section="",
            max_steps=10,
        )
        assert "Steps that failed" in prompt
        assert "Step 2: Write code" in prompt
        assert "FAILED: Import error" in prompt

    def test_build_revision_prompt_includes_both(self, skill):
        """_build_revision_prompt should include both completed and failed steps."""
        prompt = TaskPlanningSkill._build_revision_prompt(
            task_description="Build a scraper",
            completed_steps=[
                {"step_number": 1, "action": "Research", "result_summary": "Done"},
            ],
            failed_steps=[
                {"step_number": 2, "action": "Code", "error": "Failed"},
            ],
            context_section="",
            tools_section="",
            max_steps=5,
        )
        assert "Steps already completed successfully" in prompt
        assert "Steps that failed" in prompt
        assert "Maximum 5 new steps" in prompt


class TestSkillRegistration:
    """Tests for skill registration in the registry."""

    def test_skill_importable(self):
        """TaskPlanningSkill should be importable from builtin module."""
        from app.agents.skills.builtin import TaskPlanningSkill

        skill = TaskPlanningSkill()
        assert skill.metadata.id == "task_planning"

    def test_skill_in_all_exports(self):
        """TaskPlanningSkill should be in __all__ exports."""
        from app.agents.skills.builtin import __all__

        assert "TaskPlanningSkill" in __all__
