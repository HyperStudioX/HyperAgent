"""Base classes and types for the skills system."""

from typing import Any, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph


class SkillParameter(BaseModel):
    """Parameter definition for skill input."""

    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None


class SkillMetadata(BaseModel):
    """Metadata for a skill."""

    id: str  # e.g., "web_research"
    name: str
    version: str = "1.0.0"
    description: str
    category: str  # "research", "data", "creative", "automation", "code"
    parameters: list[SkillParameter]
    output_schema: dict[str, Any]  # JSON schema
    required_tools: list[str] = Field(default_factory=list)
    max_execution_time_seconds: int = 300
    max_iterations: int = 10
    author: str = "hyperagent"
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class SkillState(TypedDict, total=False):
    """Base state for skill execution."""

    skill_id: str
    input_params: dict[str, Any]
    output: dict[str, Any]
    error: str | None
    events: list[dict[str, Any]]
    iterations: int
    # Execution context - allows skills to share sessions with agents
    user_id: str | None
    task_id: str | None


class Skill:
    """Base class for all skills."""

    metadata: SkillMetadata

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for this skill.

        Returns:
            Compiled StateGraph ready for execution
        """
        raise NotImplementedError("Subclasses must implement create_graph()")

    def validate_input(self, params: dict[str, Any]) -> tuple[bool, str]:
        """Validate input parameters against schema.

        Args:
            params: Input parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check all required parameters are present
        for param in self.metadata.parameters:
            if param.required and param.name not in params:
                return False, f"Missing required parameter: {param.name}"

        # Check parameter types
        for param in self.metadata.parameters:
            if param.name not in params:
                continue

            value = params[param.name]
            expected_type = param.type

            # Basic type validation
            type_checks = {
                "string": lambda v: isinstance(v, str),
                "number": lambda v: isinstance(v, (int, float)),
                "boolean": lambda v: isinstance(v, bool),
                "object": lambda v: isinstance(v, dict),
                "array": lambda v: isinstance(v, list),
            }

            if expected_type in type_checks and not type_checks[expected_type](value):
                return False, f"Parameter '{param.name}' must be of type {expected_type}"

        return True, ""
