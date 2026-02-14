export interface SkillTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  source_code: string;
}

export const SKILL_TEMPLATES: SkillTemplate[] = [
  {
    id: "web_research",
    name: "Web Research",
    description: "A skill that searches the web and summarizes findings",
    category: "research",
    source_code: `class CustomResearchSkill(Skill):
    """Custom web research skill."""

    def __init__(self):
        super().__init__(
            metadata=SkillMetadata(
                id="custom_research",
                name="Custom Research",
                version="1.0.0",
                description="Searches the web and summarizes findings",
                category="research",
                parameters=[
                    SkillParameter(
                        name="query",
                        type="string",
                        description="The search query",
                        required=True,
                    ),
                    SkillParameter(
                        name="max_results",
                        type="number",
                        description="Maximum number of results",
                        required=False,
                        default=5,
                    ),
                ],
                output_schema={"type": "object", "properties": {"summary": {"type": "string"}}},
                tags=["research", "web", "search"],
            )
        )

    def build_graph(self):
        graph = StateGraph(SkillState)

        async def research(state: SkillState) -> dict:
            query = state.get("input_data", {}).get("query", "")
            results = await search_service.search(query)
            return {"output_data": {"summary": str(results)}, "status": "completed"}

        graph.add_node("research", research)
        graph.set_entry_point("research")
        graph.add_edge("research", END)
        return graph.compile()
`,
  },
  {
    id: "code_generation",
    name: "Code Generation",
    description: "A skill that generates code based on a prompt",
    category: "code",
    source_code: `class CustomCodeSkill(Skill):
    """Custom code generation skill."""

    def __init__(self):
        super().__init__(
            metadata=SkillMetadata(
                id="custom_code",
                name="Custom Code Generator",
                version="1.0.0",
                description="Generates code based on a prompt",
                category="code",
                parameters=[
                    SkillParameter(
                        name="prompt",
                        type="string",
                        description="Description of the code to generate",
                        required=True,
                    ),
                    SkillParameter(
                        name="language",
                        type="string",
                        description="Programming language",
                        required=False,
                        default="python",
                    ),
                ],
                output_schema={"type": "object", "properties": {"code": {"type": "string"}}},
                tags=["code", "generation"],
            )
        )

    def build_graph(self):
        graph = StateGraph(SkillState)

        async def generate(state: SkillState) -> dict:
            input_data = state.get("input_data", {})
            prompt = input_data.get("prompt", "")
            language = input_data.get("language", "python")
            messages = [
                SystemMessage(content=f"Generate {language} code for the following request."),
                HumanMessage(content=prompt),
            ]
            llm = llm_service.get_llm()
            response = await llm.ainvoke(messages)
            return {"output_data": {"code": response.content}, "status": "completed"}

        graph.add_node("generate", generate)
        graph.set_entry_point("generate")
        graph.add_edge("generate", END)
        return graph.compile()
`,
  },
  {
    id: "data_processing",
    name: "Data Processing",
    description: "A skill that processes and analyzes data",
    category: "data",
    source_code: `class CustomDataSkill(Skill):
    """Custom data processing skill."""

    def __init__(self):
        super().__init__(
            metadata=SkillMetadata(
                id="custom_data",
                name="Custom Data Processor",
                version="1.0.0",
                description="Processes and analyzes data",
                category="data",
                parameters=[
                    SkillParameter(
                        name="data",
                        type="string",
                        description="Data to process (JSON string)",
                        required=True,
                    ),
                    SkillParameter(
                        name="operation",
                        type="string",
                        description="Operation to perform (summarize, transform, analyze)",
                        required=False,
                        default="summarize",
                    ),
                ],
                output_schema={"type": "object", "properties": {"result": {"type": "string"}}},
                tags=["data", "analysis"],
            )
        )

    def build_graph(self):
        graph = StateGraph(SkillState)

        async def process(state: SkillState) -> dict:
            input_data = state.get("input_data", {})
            data = input_data.get("data", "")
            operation = input_data.get("operation", "summarize")
            messages = [
                SystemMessage(content=f"Perform a '{operation}' operation on the following data."),
                HumanMessage(content=data),
            ]
            llm = llm_service.get_llm()
            response = await llm.ainvoke(messages)
            return {"output_data": {"result": response.content}, "status": "completed"}

        graph.add_node("process", process)
        graph.set_entry_point("process")
        graph.add_edge("process", END)
        return graph.compile()
`,
  },
  {
    id: "custom",
    name: "Custom (Blank)",
    description: "Start from scratch with a minimal skill template",
    category: "automation",
    source_code: `class CustomSkill(Skill):
    """A custom skill."""

    def __init__(self):
        super().__init__(
            metadata=SkillMetadata(
                id="custom_skill",
                name="Custom Skill",
                version="1.0.0",
                description="A custom skill",
                category="automation",
                parameters=[
                    SkillParameter(
                        name="input",
                        type="string",
                        description="Input for the skill",
                        required=True,
                    ),
                ],
                output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
                tags=["custom"],
            )
        )

    def build_graph(self):
        graph = StateGraph(SkillState)

        async def execute(state: SkillState) -> dict:
            input_data = state.get("input_data", {})
            # Add your logic here
            return {"output_data": {"output": str(input_data)}, "status": "completed"}

        graph.add_node("execute", execute)
        graph.set_entry_point("execute")
        graph.add_edge("execute", END)
        return graph.compile()
`,
  },
];
