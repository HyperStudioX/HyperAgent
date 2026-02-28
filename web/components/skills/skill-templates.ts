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
    source_code: `class CustomResearchSkill(ToolSkill):
    """Custom web research skill."""

    metadata = SkillMetadata(
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
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sources": {"type": "array"},
            },
        },
        required_tools=["web_search"],
        tags=["research", "web", "search"],
    )

    async def execute(self, params: dict[str, Any], context: SkillContext) -> dict[str, Any]:
        query = params.get("query", "")
        max_results = int(params.get("max_results", 5))
        results = await search_service.search_raw(query=query, max_results=max_results)

        return {
            "summary": f"Found {len(results)} results for '{query}'",
            "sources": results,
        }
`,
  },
  {
    id: "code_generation",
    name: "Code Generation",
    description: "A skill that generates code based on a prompt",
    category: "code",
    source_code: `class CustomCodeSkill(ToolSkill):
    """Custom code generation skill."""

    metadata = SkillMetadata(
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

    async def execute(self, params: dict[str, Any], context: SkillContext) -> dict[str, Any]:
        prompt = params.get("prompt", "")
        language = params.get("language", "python")
        messages = [
            SystemMessage(content=f"Generate {language} code for the following request."),
            HumanMessage(content=prompt),
        ]
        llm = llm_service.get_llm()
        response = await llm.ainvoke(messages)
        return {"code": response.content, "language": language}
`,
  },
  {
    id: "data_processing",
    name: "Data Processing",
    description: "A skill that processes and analyzes data",
    category: "data",
    source_code: `class CustomDataSkill(ToolSkill):
    """Custom data processing skill."""

    metadata = SkillMetadata(
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

    async def execute(self, params: dict[str, Any], context: SkillContext) -> dict[str, Any]:
        data = params.get("data", "")
        operation = params.get("operation", "summarize")
        messages = [
            SystemMessage(content=f"Perform a '{operation}' operation on the following data."),
            HumanMessage(content=data),
        ]
        llm = llm_service.get_llm()
        response = await llm.ainvoke(messages)
        return {"result": response.content, "operation": operation}
`,
  },
  {
    id: "custom",
    name: "Custom (Blank)",
    description: "Start from scratch with a minimal skill template",
    category: "automation",
    source_code: `class CustomSkill(ToolSkill):
    """A custom skill."""

    metadata = SkillMetadata(
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

    async def execute(self, params: dict[str, Any], context: SkillContext) -> dict[str, Any]:
        # Add your logic here
        return {"output": str(params.get("input", ""))}
`,
  },
];
