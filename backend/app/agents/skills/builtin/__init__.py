"""Builtin skills for HyperAgent."""

from app.agents.skills.builtin.web_research_skill import WebResearchSkill
from app.agents.skills.builtin.code_review_skill import CodeReviewSkill
from app.agents.skills.builtin.data_viz_skill import DataVisualizationSkill
from app.agents.skills.builtin.image_generation_skill import ImageGenerationSkill
from app.agents.skills.builtin.code_generation_skill import CodeGenerationSkill
from app.agents.skills.builtin.task_planning_skill import TaskPlanningSkill
from app.agents.skills.builtin.app_builder_skill import AppBuilderSkill
from app.agents.skills.builtin.slide_generation_skill import SlideGenerationSkill

__all__ = [
    "WebResearchSkill",
    "CodeReviewSkill",
    "DataVisualizationSkill",
    "ImageGenerationSkill",
    "CodeGenerationSkill",
    "TaskPlanningSkill",
    "AppBuilderSkill",
    "SlideGenerationSkill",
]
