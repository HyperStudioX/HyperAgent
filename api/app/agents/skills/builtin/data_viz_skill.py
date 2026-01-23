"""Data Visualization Skill for creating charts and graphs."""

from langgraph.graph import StateGraph, END

from app.ai.llm import LLMService
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)
llm_service = LLMService()


class DataVisualizationSkill(Skill):
    """Creates charts and visualizations from data."""

    metadata = SkillMetadata(
        id="data_visualization",
        name="Data Visualization",
        version="1.0.0",
        description="Generates Python code for creating charts and visualizations from data using matplotlib",
        category="data",
        parameters=[
            SkillParameter(
                name="data_description",
                type="string",
                description="Description of the data to visualize",
                required=True,
            ),
            SkillParameter(
                name="chart_type",
                type="string",
                description="Type of chart: bar, line, scatter, pie, histogram, auto (default)",
                required=False,
                default="auto",
            ),
            SkillParameter(
                name="data",
                type="object",
                description="Optional: Actual data to visualize (JSON format)",
                required=False,
                default=None,
            ),
        ],
        output_schema={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code for creating the visualization",
                },
                "chart_type": {
                    "type": "string",
                    "description": "Type of chart recommended/used",
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation of the visualization approach",
                },
            },
        },
        required_tools=[],
        max_iterations=2,
        tags=["data", "visualization", "charts", "matplotlib"],
    )

    def create_graph(self) -> StateGraph:
        """Create the LangGraph subgraph for data visualization."""
        graph = StateGraph(SkillState)

        async def generate_viz_code_node(state: SkillState) -> dict:
            """Generate visualization code."""
            data_description = state["input_params"]["data_description"]
            chart_type = state["input_params"].get("chart_type", "auto")
            data = state["input_params"].get("data")

            logger.info(
                "data_viz_skill_generating",
                chart_type=chart_type,
                has_data=data is not None,
            )

            try:
                # Build prompt for code generation
                data_context = ""
                if data:
                    import json
                    data_context = f"\n\nData (JSON format):\n{json.dumps(data, indent=2)}\n"

                prompt = f"""Generate Python code to create a {chart_type if chart_type != 'auto' else ''} visualization.

Data Description: {data_description}{data_context}

Requirements:
1. Use matplotlib for visualization
2. Include all necessary imports
3. Create a clear, well-labeled chart
4. Use appropriate colors and styling
5. Save the figure to 'visualization.png'
6. If chart_type is 'auto', choose the most appropriate visualization

Provide your response in the following format:

CHART_TYPE: [The chart type you chose: bar/line/scatter/pie/histogram/etc]

CODE:
```python
# Your Python code here
```

EXPLANATION:
Brief explanation of why this visualization approach was chosen and what it shows.
"""

                # Get LLM for code generation
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)

                # Generate code
                response = await llm.ainvoke(prompt)
                content = response.content

                # Parse response
                code = ""
                chart_type_result = chart_type
                explanation = ""

                # Extract chart type
                if "CHART_TYPE:" in content:
                    try:
                        chart_line = [l for l in content.split("\n") if "CHART_TYPE:" in l][0]
                        chart_type_result = chart_line.split("CHART_TYPE:")[1].strip()
                    except (IndexError, ValueError):
                        pass

                # Extract code block
                if "```python" in content:
                    try:
                        code_start = content.index("```python") + 9
                        code_end = content.index("```", code_start)
                        code = content[code_start:code_end].strip()
                    except (ValueError, IndexError):
                        # Try generic code block
                        if "```" in content:
                            try:
                                code_blocks = content.split("```")
                                if len(code_blocks) >= 3:
                                    code = code_blocks[1].strip()
                                    if code.startswith("python"):
                                        code = code[6:].strip()
                            except (ValueError, IndexError):
                                pass

                # Extract explanation
                if "EXPLANATION:" in content:
                    try:
                        explanation = content.split("EXPLANATION:")[1].strip()
                    except (IndexError, ValueError):
                        pass

                if not code:
                    # Fallback: try to extract any code block
                    code = content.strip()

                logger.info(
                    "data_viz_skill_completed",
                    chart_type=chart_type_result,
                    code_length=len(code),
                )

                return {
                    "output": {
                        "code": code,
                        "chart_type": chart_type_result,
                        "explanation": explanation,
                    },
                    "iterations": state["iterations"] + 1,
                }

            except Exception as e:
                logger.error("data_viz_skill_failed", error=str(e))
                return {
                    "error": f"Visualization generation failed: {str(e)}",
                    "iterations": state["iterations"] + 1,
                }

        # Build graph
        graph.add_node("generate_viz_code", generate_viz_code_node)
        graph.set_entry_point("generate_viz_code")
        graph.add_edge("generate_viz_code", END)

        return graph.compile()
