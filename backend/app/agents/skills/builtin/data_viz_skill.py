"""Data Visualization Skill for creating charts and graphs."""

from langgraph.graph import StateGraph, END

from app.ai.llm import llm_service
from app.ai.model_tiers import ModelTier
from app.core.logging import get_logger
from app.agents.skills.skill_base import Skill, SkillMetadata, SkillParameter, SkillState

logger = get_logger(__name__)


class DataVisualizationSkill(Skill):
    """Creates charts and visualizations from data."""

    metadata = SkillMetadata(
        id="data_visualization",
        name="Data Visualization",
        version="2.0.0",
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
        
        from pydantic import BaseModel, Field

        class DataVizResponse(BaseModel):
            """Structured data visualization response."""
            chart_type: str = Field(description="The chart type chosen (e.g., bar, line, scatter)")
            code: str = Field(description="Complete Python code to generate the chart using matplotlib")
            explanation: str = Field(description="Brief explanation of why this chart type was chosen and what it shows")

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
6. If chart_type is 'auto', choose the most appropriate visualization"""

                # Get LLM for code generation
                llm = llm_service.get_llm_for_tier(ModelTier.PRO)
                
                # Use structured output
                structured_llm = llm.with_structured_output(DataVizResponse)
                
                # Generate code
                result: DataVizResponse = await structured_llm.ainvoke(prompt)

                # Clean up code block markers if LLM still includes them despite structured output request
                code = result.code
                if "```python" in code:
                    code = code.split("```python")[1].split("```")[0].strip()
                elif "```" in code:
                    code = code.split("```")[1].strip()

                logger.info(
                    "data_viz_skill_completed",
                    chart_type=result.chart_type,
                    code_length=len(code),
                )

                return {
                    "output": {
                        "code": code,
                        "chart_type": result.chart_type,
                        "explanation": result.explanation,
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
