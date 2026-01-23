"""Code Generation Skill for creating code snippets and functions."""

from langgraph.graph import StateGraph, END

from app.ai.llm import LLMService
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)
llm_service = LLMService()


class CodeGenerationSkill(Skill):
    """Generates code snippets, functions, and small programs."""

    metadata = SkillMetadata(
        id="code_generation",
        name="Code Generation",
        version="1.0.0",
        description="Generates well-structured code snippets, functions, classes, or small programs in any programming language",
        category="code",
        parameters=[
            SkillParameter(
                name="task",
                type="string",
                description="Description of what code to generate (e.g., 'function to validate email', 'API endpoint for user login')",
                required=True,
            ),
            SkillParameter(
                name="language",
                type="string",
                description="Programming language (python, javascript, typescript, java, go, rust, etc.)",
                required=False,
                default="python",
            ),
            SkillParameter(
                name="style",
                type="string",
                description="Code style: clean, documented, minimal, production-ready",
                required=False,
                default="clean",
            ),
            SkillParameter(
                name="include_tests",
                type="boolean",
                description="Whether to include unit tests",
                required=False,
                default=False,
            ),
            SkillParameter(
                name="context",
                type="string",
                description="Additional context or requirements",
                required=False,
                default="",
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The generated code",
                },
                "language": {
                    "type": "string",
                    "description": "Programming language used",
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation of the code",
                },
                "tests": {
                    "type": "string",
                    "description": "Unit tests if requested",
                },
            },
        },
        required_tools=[],
        max_iterations=2,
        tags=["code", "programming", "generation", "development"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for code generation."""
        graph = StateGraph(SkillState)

        async def generate_node(state: SkillState) -> dict:
            """Generate code based on requirements."""
            task = state["input_params"]["task"]
            language = state["input_params"].get("language", "python")
            style = state["input_params"].get("style", "clean")
            include_tests = state["input_params"].get("include_tests", False)
            context = state["input_params"].get("context", "")

            logger.info(
                "code_generation_skill_generating",
                language=language,
                style=style,
                include_tests=include_tests,
            )

            try:
                # Build style guidance
                style_guidance = {
                    "clean": "Write clean, readable code with meaningful variable names",
                    "documented": "Include comprehensive docstrings and inline comments",
                    "minimal": "Write concise, minimalist code without unnecessary complexity",
                    "production-ready": "Include error handling, type hints, and production-quality patterns",
                }
                style_desc = style_guidance.get(style, style_guidance["clean"])

                context_section = f"\n\nAdditional Context:\n{context}" if context else ""
                tests_section = "\n\nAlso provide unit tests for the code." if include_tests else ""

                prompt = f"""Generate {language} code for the following task:

Task: {task}

Requirements:
- Language: {language}
- Style: {style_desc}
- Follow best practices for {language}{tests_section}{context_section}

Format your response as:

CODE:
```{language}
[Your code here]
```

EXPLANATION:
[Brief explanation of what the code does and key implementation details]
{
"TESTS:" + '''
```''' + language + '''
[Unit tests here]
```''' if include_tests else ""
}"""

                # Get LLM for code generation
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)

                # Generate code
                response = await llm.ainvoke(prompt)
                content = response.content

                # Parse response
                code = ""
                explanation = ""
                tests = ""

                # Extract code block
                if f"```{language}" in content:
                    try:
                        # Get first code block
                        code_start = content.index(f"```{language}") + len(f"```{language}")
                        code_end = content.index("```", code_start)
                        code = content[code_start:code_end].strip()
                    except (ValueError, IndexError):
                        pass
                elif "```" in content:
                    # Try generic code block
                    try:
                        code_blocks = content.split("```")
                        if len(code_blocks) >= 3:
                            code = code_blocks[1].strip()
                            if code.startswith(language):
                                code = code[len(language):].strip()
                    except (ValueError, IndexError):
                        pass

                # Extract explanation
                if "EXPLANATION:" in content:
                    try:
                        explanation_start = content.index("EXPLANATION:") + 12
                        # Look for next section or end
                        if "TESTS:" in content[explanation_start:]:
                            explanation_end = content.index("TESTS:", explanation_start)
                            explanation = content[explanation_start:explanation_end].strip()
                        else:
                            explanation = content[explanation_start:].strip()
                            # Remove trailing code blocks
                            if "```" in explanation:
                                explanation = explanation[:explanation.index("```")].strip()
                    except (ValueError, IndexError):
                        pass

                # Extract tests if requested
                if include_tests and "TESTS:" in content:
                    try:
                        tests_start_idx = content.index("TESTS:")
                        tests_content = content[tests_start_idx + 6:]
                        if f"```{language}" in tests_content:
                            test_code_start = tests_content.index(f"```{language}") + len(f"```{language}")
                            test_code_end = tests_content.index("```", test_code_start)
                            tests = tests_content[test_code_start:test_code_end].strip()
                        elif "```" in tests_content:
                            # Generic code block
                            test_blocks = tests_content.split("```")
                            if len(test_blocks) >= 3:
                                tests = test_blocks[1].strip()
                    except (ValueError, IndexError):
                        pass

                if not code:
                    code = content  # Fallback: use entire response

                logger.info(
                    "code_generation_skill_completed",
                    language=language,
                    code_length=len(code),
                    has_tests=bool(tests),
                )

                return {
                    "output": {
                        "code": code,
                        "language": language,
                        "explanation": explanation,
                        "tests": tests if include_tests else None,
                    },
                    "iterations": state["iterations"] + 1,
                }

            except Exception as e:
                logger.error("code_generation_skill_failed", error=str(e))
                return {
                    "error": f"Code generation failed: {str(e)}",
                    "iterations": state["iterations"] + 1,
                }

        # Build graph
        graph.add_node("generate", generate_node)
        graph.set_entry_point("generate")
        graph.add_edge("generate", END)

        return graph.compile()
