# Agent Skills System

This document describes how skills are defined, registered, and invoked in HyperAgent's multi-agent architecture.

## Overview

Skills are self-contained, composable capabilities implemented as LangGraph subgraphs. Agents invoke skills through LangChain tools (`invoke_skill`, `list_skills`), enabling modular and reusable functionality.

```
User Request → Agent Reasoning → invoke_skill(skill_id, params)
    → SkillRegistry → SkillExecutor → LangGraph Execution → Output
```

## Skill Architecture

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Skill Base Classes | `backend/app/agents/skills/skill_base.py` | Base class and metadata definitions |
| Builtin Skills | `backend/app/agents/skills/builtin/` | Pre-built skill implementations |
| Skill Registry | `backend/app/services/skill_registry.py` | Skill discovery and management |
| Skill Executor | `backend/app/services/skill_executor.py` | Skill execution and event streaming |
| Invocation Tools | `backend/app/agents/tools/skill_invocation.py` | LangChain tools for agents |
| Tool Registry | `backend/app/agents/tools/registry.py` | Tool-to-agent mapping |

### Skill Definition Structure

```python
# backend/app/agents/skills/skill_base.py

class SkillParameter(BaseModel):
    name: str              # Parameter name (e.g., "topic")
    type: str              # "string", "number", "boolean", "object", "array"
    description: str       # User-facing documentation
    required: bool = True
    default: Any = None

class SkillMetadata(BaseModel):
    id: str                           # Unique identifier (e.g., "web_research")
    name: str                         # Display name
    version: str = "1.0.0"
    description: str                  # What the skill does
    category: str                     # "research", "data", "creative", "automation", "code"
    parameters: list[SkillParameter]  # Input requirements
    output_schema: dict[str, Any]     # JSON schema for output
    required_tools: list[str]         # Tools skill needs (e.g., ["web_search"])
    max_execution_time_seconds: int = 300
    max_iterations: int = 10
    author: str = "hyperagent"
    tags: list[str]                   # Categorization tags
    enabled: bool = True

class SkillState(TypedDict, total=False):
    skill_id: str
    input_params: dict[str, Any]      # User-provided parameters
    output: dict[str, Any]            # Result of execution
    error: str | None
    events: list[dict[str, Any]]
    iterations: int
    user_id: str | None
    task_id: str | None
```

### Base Skill Class

```python
class Skill:
    metadata: SkillMetadata

    def create_graph(self) -> StateGraph:
        """Create LangGraph subgraph for skill execution."""
        raise NotImplementedError()

    def validate_input(self, params: dict[str, Any]) -> tuple[bool, str]:
        """Validate parameters against schema."""
        # Type checking, required parameter validation
```

## Builtin Skills

Six skills are available out of the box in `backend/app/agents/skills/builtin/`:

| Skill ID | Category | Description |
|----------|----------|-------------|
| `web_research` | research | Focused web research with summarization |
| `code_generation` | code | Generate code snippets with explanations |
| `code_review` | code | Code quality analysis (bugs, style, security) |
| `simple_writing` | creative | Document, email, and article writing |
| `image_generation` | creative | AI image generation |
| `data_visualization` | data | Generate visualization code |

### Example: Web Research Skill

```python
# backend/app/agents/skills/builtin/web_research_skill.py

class WebResearchSkill(Skill):
    metadata = SkillMetadata(
        id="web_research",
        name="Web Research",
        category="research",
        parameters=[
            SkillParameter(name="topic", type="string", required=True),
            SkillParameter(name="max_sources", type="number", default=5),
        ],
        output_schema={
            "summary": "string",
            "sources": ["array"],
            "key_findings": ["array"]
        }
    )

    def create_graph(self) -> StateGraph:
        graph = StateGraph(SkillState)
        graph.add_node("search", self.search_node)
        graph.add_node("summarize", self.summarize_node)
        graph.add_edge(START, "search")
        graph.add_edge("search", "summarize")
        graph.add_edge("summarize", END)
        return graph.compile()
```

### Example: Code Generation Skill

```python
# backend/app/agents/skills/builtin/code_generation_skill.py

class CodeGenerationSkill(Skill):
    metadata = SkillMetadata(
        id="code_generation",
        category="code",
        parameters=[
            SkillParameter(name="task", type="string", required=True),
            SkillParameter(name="language", type="string", default="python"),
            SkillParameter(name="style", type="string", default="clean"),
            SkillParameter(name="include_tests", type="boolean", default=False),
        ],
        output_schema={
            "code": "string",
            "explanation": "string",
            "tests": "string | null",
            "language": "string"
        }
    )
```

## Skill Invocation

### Invocation Tools

Agents invoke skills through two LangChain tools defined in `backend/app/agents/tools/skill_invocation.py`:

#### invoke_skill

Executes a skill with given parameters:

```python
@tool(args_schema=InvokeSkillInput)
async def invoke_skill(
    skill_id: str,
    params: dict[str, Any],
    user_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Invoke a registered skill to perform specialized task."""

    # 1. Get skill from registry
    skill = skill_registry.get_skill(skill_id)
    if not skill:
        return json.dumps({"error": "Skill not found"})

    # 2. Validate input parameters
    is_valid, error_msg = skill.validate_input(params)
    if not is_valid:
        return json.dumps({
            "error": f"Invalid parameters: {error_msg}",
            "expected_parameters": [p.model_dump() for p in skill.metadata.parameters]
        })

    # 3. Execute skill via executor
    async for event in skill_executor.execute_skill(
        skill_id=skill_id,
        params=params,
        user_id=user_id or "anonymous",
        agent_type="tool",
        task_id=task_id,
    ):
        if event.get("type") == "skill_output":
            output = event.get("output", {})

    # 4. Return result as JSON
    return json.dumps({
        "skill_id": skill_id,
        "output": output,
        "success": True,
    }, indent=2)
```

#### list_skills

Discovers available skills:

```python
@tool(args_schema=ListSkillsInput)
async def list_skills(category: str | None = None) -> str:
    """List all available skills with optional category filtering."""

    skills = skill_registry.list_skills(category=category)

    skills_data = []
    for skill_metadata in skills:
        skills_data.append({
            "id": skill_metadata.id,
            "name": skill_metadata.name,
            "description": skill_metadata.description,
            "category": skill_metadata.category,
            "parameters": [...],
            "tags": skill_metadata.tags,
        })

    return json.dumps({
        "skills": skills_data,
        "count": len(skills_data),
        "category": category,
    }, indent=2)
```

## Skill Registry

The registry manages skill lifecycle in `backend/app/services/skill_registry.py`:

```python
class SkillRegistry:
    def __init__(self):
        self._loaded_skills: dict[str, Skill] = {}
        self._builtin_skills: dict[str, type[Skill]] = {}

    async def initialize(self, db: AsyncSession):
        """Initialize with builtin skills + load from database."""
        await self._register_builtin_skills()
        await self._load_from_database(db)

    async def _register_builtin_skills(self):
        """Auto-discover and instantiate builtin skills."""
        # Creates instances of each skill class
        # Registers in _loaded_skills dict by skill.metadata.id

    async def _load_dynamic_skill(self, skill_def: SkillDefinition):
        """Load skills from database with validation."""
        # Validates source code hash
        # Executes in restricted namespace
        # Finds Skill subclass and instantiates

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get loaded skill by ID."""

    def list_skills(self, category: Optional[str] = None) -> list[SkillMetadata]:
        """List available skills with optional filtering."""

# Global singleton
skill_registry = SkillRegistry()
```

### Key Features

- **Auto-discovery**: Builtin skills are automatically registered on initialization
- **Dynamic loading**: Skills can be loaded from database with code validation
- **Category filtering**: List skills by category (research, code, creative, etc.)
- **Validation**: Hash verification and restricted namespace for dynamic skills

## Skill Executor

The executor handles skill execution in `backend/app/services/skill_executor.py`:

```python
class SkillExecutor:
    async def execute_skill(
        self,
        skill_id: str,
        params: dict[str, Any],
        user_id: str,
        agent_type: str,
        task_id: str | None = None,
        db: AsyncSession | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Execute skill and stream events."""

        # 1. Get skill from registry
        skill = skill_registry.get_skill(skill_id)

        # 2. Validate input
        is_valid, error_msg = skill.validate_input(params)

        # 3. Create execution record in database
        execution = SkillExecution(
            id=execution_id,
            skill_id=skill_id,
            user_id=user_id,
            status="running",
            input_params=json.dumps(params),
        )

        # 4. Emit start event
        yield events.stage(name=f"skill_{skill_id}", status="running")

        # 5. Build initial skill state and execute
        initial_state: SkillState = {
            "skill_id": skill_id,
            "input_params": params,
            "output": {},
            "error": None,
        }

        graph = skill.create_graph()
        async with asyncio.timeout(skill.metadata.max_execution_time_seconds):
            final_state = await graph.ainvoke(initial_state)

        # 6. Emit completion events
        yield events.stage(name=f"skill_{skill_id}", status="completed")
        yield events.skill_output(skill_id=skill_id, output=output)

# Global singleton
skill_executor = SkillExecutor()
```

## How Agents Decide: Tools vs Skills

Agents use **LLM-based autonomous decision-making** to choose between direct tools and skills. The decision is not hardcoded but emerges from system prompts, tool descriptions, and context understanding.

### Decision-Making Process

#### 1. Tool Binding

All tools (including skill invocation tools) are bound to the LLM:

```python
# backend/app/agents/subagents/chat.py (reason_node)

# Get all tools for chat agent
all_tools = get_tools_for_agent("chat", include_handoffs=True)
# Returns: [web_search, execute_code, invoke_skill, list_skills, ...]

# Bind tools to LLM
llm_with_tools = llm.bind_tools(all_tools)

# LLM reasoning - can see and call any of these tools
ai_message = await llm_with_tools.ainvoke(lc_messages)
# LLM autonomously decides which tool(s) to call
```

The LLM receives:
- **All available tools** in its context (direct tools + skill invocation tools)
- **Tool descriptions** from LangChain schemas
- **System prompt guidance** on when to use each

#### 2. System Prompt Guidance

The system prompt (`CHAT_SYSTEM_PROMPT` in `backend/app/agents/prompts.py`) provides explicit guidance:

```python
CHAT_SYSTEM_PROMPT = """
<tools>
You have access to a web search tool that you can use to find current information when needed. 
Use it when:
- The user asks about recent events or news
- You need to verify facts or find up-to-date information
- The question requires knowledge beyond your training data

You have access to specialized skills via invoke_skill and list_skills:
- list_skills: Discover available skills and their parameters (use this first to see what's available)
- invoke_skill: Execute a skill with specific parameters

Available skills include:
- web_research: Focused web research with source summarization
- code_generation: Generate code snippets for specific tasks
- code_review: Review code for bugs, style issues, and security vulnerabilities
- simple_writing: Write documents, emails, articles, and other content
- image_generation: Generate AI images from text descriptions
- data_visualization: Create data visualizations and charts
- task_planning: Analyze complex tasks and create structured execution plans

When to use skills:
- Use list_skills first to discover available skills and their parameters
- Use invoke_skill when a task matches a skill's purpose better than basic tools
- Skills provide structured, focused capabilities for specific task types
- Skills can combine multiple steps into a single invocation
- Use task_planning for complex multi-step tasks that need upfront planning
</tools>
"""
```

#### 3. Decision Factors

The LLM considers multiple factors when deciding:

1. **User Query Intent**: Understanding what the user wants
   - Simple fact lookup → Direct tool (`web_search`)
   - Complex research with analysis → Skill (`invoke_skill("web_research")`)

2. **Task Complexity**: Single operation vs multi-step workflow
   - Single operation → Direct tool
   - Multi-step workflow → Skill

3. **Output Requirements**: Raw results vs structured analysis
   - Raw results → Direct tool
   - Structured analysis → Skill

4. **Tool Descriptions**: Each tool has a description the LLM sees
   - `web_search`: "Search the web for current information on any topic"
   - `invoke_skill`: "Invoke a registered skill to perform a specialized task. Skills are composable subgraphs..."

### Decision Examples

#### Example 1: Simple Search → Direct Tool

**User Query**: "What is Python?"

**LLM Decision Process**:
1. Simple fact lookup question
2. System prompt: "Use web_search when you need to verify facts"
3. **Decision**: Call `web_search("What is Python")`

**Result**: Raw search results returned to agent

#### Example 2: Research Task → Skill

**User Query**: "Research the latest trends in AI and summarize the findings"

**LLM Decision Process**:
1. Complex research task requiring summarization
2. System prompt: "web_research: Focused web research with source summarization"
3. System prompt: "Use invoke_skill when a task matches a skill's purpose better than basic tools"
4. This needs summarization, not just raw results
5. **Decision**: Call `invoke_skill("web_research", {"topic": "latest trends in AI"})`

**Result**: Summarized research with key findings

#### Example 3: Code Execution → Direct Tool

**User Query**: "Run this code: print('hello')"

**LLM Decision Process**:
1. Direct code execution request
2. System prompt: "Use execute_code when the user asks you to run, execute, or test code"
3. **Decision**: Call `execute_code({"code": "print('hello')", "language": "python"})`

**Result**: Code execution output

#### Example 4: Code Review → Skill

**User Query**: "Review this code for bugs and security issues"

**LLM Decision Process**:
1. Code review task requiring structured analysis
2. System prompt: "code_review: Review code for bugs, style issues, and security vulnerabilities"
3. This needs structured feedback, not just execution
4. **Decision**: Call `invoke_skill("code_review", {"code": "..."})`

**Result**: Structured review with categories (bugs, style, security)

### When to Use Direct Tools

**Use direct tools when**:
- ✅ Simple, single operation needed
- ✅ Quick fact lookup or verification
- ✅ Direct control over parameters
- ✅ No analysis or summarization required
- ✅ Low latency preferred

**Examples**:
- `web_search("capital of France")` - Simple fact lookup
- `execute_code("print('hello')")` - Simple code execution
- `browser_navigate("https://example.com")` - Direct browser action
- `generate_image("a cat")` - Direct image generation

### When to Use Skills

**Use skills when**:
- ✅ Complex, multi-step workflow needed
- ✅ Structured analysis required (summarization, insights)
- ✅ Task matches skill's purpose (research, code review, writing)
- ✅ Combined operations (search + summarize, plan + execute)
- ✅ Structured output needed (not just raw results)

**Examples**:
- `invoke_skill("web_research", {"topic": "AI trends"})` - Research with analysis
- `invoke_skill("code_review", {"code": "..."})` - Code review with structured feedback
- `invoke_skill("app_builder", {"description": "todo app"})` - Multi-step app building
- `invoke_skill("simple_writing", {"topic": "...", "type": "article"})` - Structured writing

### Mode-Based Guidance

The agent can receive mode hints that influence decisions:

```python
# backend/app/agents/subagents/chat.py (reason_node)

if mode == "image":
    enhanced_query = f"Generate an image based on this description: {query}\n\nUse the image_generation skill to create the image."
elif mode == "app":
    enhanced_query = f"Build a web application based on this description: {query}\n\nUse the app_builder skill to create the application."
```

**Modes provide explicit guidance**:
- `mode="image"` → Guides agent to use `image_generation` skill
- `mode="app"` → Guides agent to use `app_builder` skill

### Key Insights

1. **No Hardcoded Rules**: The agent doesn't have if/else logic for tool selection. The LLM decides autonomously.

2. **Prompt Engineering**: The system prompt is the primary mechanism for guiding decisions. Clear, specific guidance helps the LLM choose correctly.

3. **Tool Descriptions Matter**: LangChain tool descriptions are part of the LLM's context. Well-written descriptions improve decision quality.

4. **Context Awareness**: The LLM considers:
   - User query intent
   - Conversation history
   - Previous tool results
   - Task complexity

5. **Skills as Tools**: From the agent's perspective, skills are just another type of tool (via `invoke_skill`). The distinction is semantic, not architectural.

6. **Discovery Pattern**: The agent can use `list_skills` to discover available skills before invoking them, enabling dynamic skill selection.

For more detailed information, see [Agent Tool-Skill Decision Making](./Agent-Tool-Skill-Decision-Making.md).

## Tool Registry Integration

Skills are integrated as tools via `backend/app/agents/tools/registry.py`:

```python
class ToolCategory(str, Enum):
    SEARCH = "search"
    IMAGE = "image"
    BROWSER = "browser"
    CODE_EXEC = "code_exec"
    DATA = "data"
    HANDOFF = "handoff"
    SKILL = "skill"           # Skills category
    HITL = "hitl"

TOOL_CATALOG: dict[ToolCategory, list[BaseTool]] = {
    # ... other tools ...
    ToolCategory.SKILL: get_skill_tools(),  # [invoke_skill, list_skills]
}

# Agent access mapping
AGENT_TOOL_MAPPING: dict[str, list[ToolCategory]] = {
    "chat": [
        ToolCategory.SEARCH,
        ToolCategory.IMAGE,
        ToolCategory.BROWSER,
        ToolCategory.CODE_EXEC,
        ToolCategory.SKILL,        # Chat can invoke skills
        ToolCategory.HANDOFF,
        ToolCategory.HITL,
    ],
    "research": [
        ToolCategory.SEARCH,
        ToolCategory.BROWSER,
        ToolCategory.SKILL,        # Research can invoke skills
        ToolCategory.HANDOFF,
    ],
    "data": [
        ToolCategory.CODE_EXEC,
        ToolCategory.DATA,
        ToolCategory.SKILL,        # Data can invoke skills
        ToolCategory.HANDOFF,
    ],
}

def get_tools_for_agent(agent_type: str) -> list[BaseTool]:
    """Get all tools available to an agent type."""
    allowed_categories = AGENT_TOOL_MAPPING.get(agent_type, [])
    tools: list[BaseTool] = []

    for category in allowed_categories:
        tools.extend(TOOL_CATALOG.get(category, []))

    return tools
```

## Event System

Skills emit structured events during execution via `backend/app/agents/events.py`:

```python
class SkillOutputEvent(BaseModel):
    type: Literal["skill_output"] = "skill_output"
    skill_id: str
    output: dict[str, Any]

def skill_output(skill_id: str, output: dict[str, Any]) -> dict[str, Any]:
    """Create a skill output event dictionary."""
    return SkillOutputEvent(skill_id=skill_id, output=output).model_dump()
```

Events emitted during skill execution:
- `stage` events (skill started/completed/failed)
- `error` events (exception details)
- `skill_output` events (final results)

## REST API Endpoints

Skills are exposed via REST in `backend/app/api/skills.py`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/skills` | GET | List all available skills |
| `/api/v1/skills?category=code` | GET | List skills by category |
| `/api/v1/skills/{skill_id}` | GET | Get skill details |

## Complete Workflow Example

```
1. User: "Research the latest AI trends"

2. Supervisor routes to Chat Agent

3. Chat Agent reasons:
   - "User wants research, I should invoke web_research skill"

4. Chat Agent calls tool:
   invoke_skill(
       skill_id="web_research",
       params={"topic": "latest AI trends", "max_sources": 5}
   )

5. invoke_skill tool:
   a. Gets skill: skill_registry.get_skill("web_research")
   b. Validates: skill.validate_input(params)
   c. Executes: skill_executor.execute_skill(...)

6. SkillExecutor:
   a. Creates initial state with input_params
   b. Gets graph: skill.create_graph()
   c. Runs: await graph.ainvoke(initial_state)

7. WebResearchSkill graph executes:
   search_node → summarize_node

8. SkillExecutor emits:
   - stage event (completed)
   - skill_output event with results

9. invoke_skill returns:
   {
     "skill_id": "web_research",
     "output": {
       "summary": "...",
       "sources": [...],
       "key_findings": [...]
     },
     "success": true
   }

10. Chat Agent formats response to user
```

## Creating Custom Skills

To create a new skill:

1. **Define the skill class** in `backend/app/agents/skills/builtin/`:

```python
from backend.app.agents.skills.skill_base import (
    Skill, SkillMetadata, SkillParameter, SkillState
)
from langgraph.graph import StateGraph, START, END

class MyCustomSkill(Skill):
    metadata = SkillMetadata(
        id="my_custom_skill",
        name="My Custom Skill",
        version="1.0.0",
        description="Does something useful",
        category="code",  # or research, creative, data, automation
        parameters=[
            SkillParameter(
                name="input_text",
                type="string",
                description="The input to process",
                required=True,
            ),
        ],
        output_schema={
            "result": "string",
            "metadata": "object",
        },
        required_tools=[],
        tags=["custom", "example"],
    )

    def create_graph(self) -> StateGraph:
        graph = StateGraph(SkillState)
        graph.add_node("process", self._process_node)
        graph.add_edge(START, "process")
        graph.add_edge("process", END)
        return graph.compile()

    async def _process_node(self, state: SkillState) -> dict:
        input_text = state["input_params"]["input_text"]
        # Process the input
        result = f"Processed: {input_text}"
        return {
            "output": {
                "result": result,
                "metadata": {"processed": True}
            }
        }
```

2. **Register in `__init__.py`**:

```python
# backend/app/agents/skills/builtin/__init__.py
from .my_custom_skill import MyCustomSkill

__all__ = [
    # ... existing skills ...
    "MyCustomSkill",
]
```

3. The skill will be auto-discovered and registered on startup.

## Design Patterns

### LangGraph Subgraphs
Each skill is a LangGraph StateGraph defining a workflow with nodes and edges.

### Structured LLM Output
Skills use Pydantic models with `llm.with_structured_output()` for type-safe responses.

### Registry Pattern
Centralized registry enables discovery, validation, and execution management.

### Event Streaming
Skills emit events throughout execution for real-time UI updates.

### Execution Context
Skills receive `user_id` and `task_id` for multi-tenancy and tracking.

### Validation & Safety
- Input parameter validation (type checking, required fields)
- Timeout enforcement (`max_execution_time_seconds`)
- Iteration limits (`max_iterations`)
- Dynamic skill code validation with restricted namespace
