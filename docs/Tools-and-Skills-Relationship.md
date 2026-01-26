# Tools and Skills Relationship During Agent Execution

## Executive Summary

**Tools** and **Skills** are two complementary layers in HyperAgent's architecture:

- **Tools** are atomic, single-purpose functions that agents call directly (e.g., `web_search`, `execute_code`, `browser_navigate`)
- **Skills** are composable LangGraph subgraphs that agents invoke via the `invoke_skill` tool, which then orchestrate multiple steps internally using services (not tools)

The key relationship: **Agents use Tools → Skills are invoked via Tools → Skills use Services (not Tools)**

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent (Chat/Research/Data)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ReAct Loop: reason → act → reason → ... → finalize  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Has access to Tools
                            ▼
        ┌───────────────────────────────────────┐
        │         Tool Registry                  │
        │  ┌─────────────────────────────────┐  │
        │  │ Direct Tools:                   │  │
        │  │ - web_search                    │  │
        │  │ - execute_code                  │  │
        │  │ - browser_navigate              │  │
        │  │ - generate_image                │  │
        │  │ - analyze_image                 │  │
        │  │ - ask_user (HITL)               │  │
        │  │ - handoff_to_* (agent routing)  │  │
        │  └─────────────────────────────────┘  │
        │  ┌─────────────────────────────────┐  │
        │  │ Skill Invocation Tools:          │  │
        │  │ - invoke_skill                  │  │
        │  │ - list_skills                  │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
                            │
                            │ invoke_skill(skill_id, params)
                            ▼
        ┌───────────────────────────────────────┐
        │      Skill Executor                   │
        │  ┌─────────────────────────────────┐  │
        │  │ Skill Registry                  │  │
        │  │ - web_research                  │  │
        │  │ - code_review                  │  │
        │  │ - app_builder                  │  │
        │  │ - image_generation             │  │
        │  │ - data_visualization           │  │
        │  │ - simple_writing               │  │
        │  │ - task_planning                │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
                            │
                            │ Executes LangGraph subgraph
                            ▼
        ┌───────────────────────────────────────┐
        │         Skill Implementation          │
        │  ┌─────────────────────────────────┐  │
        │  │ Uses Services (NOT Tools):      │  │
        │  │ - search_service               │  │
        │  │ - llm_service                  │  │
        │  │ - app_sandbox_manager          │  │
        │  │ - (other backend services)      │  │
        │  └─────────────────────────────────┘  │
        └───────────────────────────────────────┘
```

## Detailed Relationship Analysis

### 1. Tools: Direct Agent Capabilities

**Location**: `backend/app/agents/tools/`

**Characteristics**:
- Atomic, single-purpose functions
- Directly callable by agents via LangChain tool binding
- Organized by categories (SEARCH, IMAGE, BROWSER, CODE_EXEC, SKILL, HANDOFF, HITL)
- Each agent type has access to specific tool categories

**Tool Categories**:
```python
class ToolCategory(str, Enum):
    SEARCH = "search"        # web_search
    IMAGE = "image"          # generate_image, analyze_image
    BROWSER = "browser"      # browser_navigate, browser_click, etc.
    CODE_EXEC = "code_exec"  # execute_code
    DATA = "data"            # sandbox_file
    APP_BUILDER = "app_builder"  # create_app_project, app_write_file, etc.
    HANDOFF = "handoff"      # handoff_to_research, handoff_to_data, etc.
    SKILL = "skill"          # invoke_skill, list_skills
    HITL = "hitl"            # ask_user
```

**Agent Tool Access**:
- **Chat Agent**: SEARCH, IMAGE, BROWSER, CODE_EXEC, APP_BUILDER, SKILL, HANDOFF, HITL
- **Research Agent**: SEARCH, IMAGE, BROWSER, SKILL, HANDOFF, HITL
- **Data Agent**: SEARCH, IMAGE, CODE_EXEC, DATA, SKILL, HANDOFF, HITL

**Example Tool Execution Flow**:
```python
# Agent reasoning decides to use web_search
ai_message = await llm_with_tools.ainvoke(messages)  # Returns AIMessage with tool_calls

# Act node executes the tool
for tool_call in ai_message.tool_calls:
    tool = tool_map[tool_call["name"]]
    result = await tool.ainvoke(tool_call["args"])
    # Add ToolMessage with result to conversation
```

### 2. Skills: Composable Subgraphs

**Location**: `backend/app/agents/skills/`

**Characteristics**:
- Self-contained LangGraph subgraphs
- Multi-step workflows with internal state management
- Invoked by agents through the `invoke_skill` tool
- Use backend services directly (not tools)
- Have their own metadata, parameters, and output schemas

**Skill Invocation Flow**:
```
1. Agent calls invoke_skill(skill_id="web_research", params={"topic": "..."})
   ↓
2. invoke_skill tool validates input and calls SkillExecutor
   ↓
3. SkillExecutor gets skill from SkillRegistry
   ↓
4. SkillExecutor executes skill's LangGraph subgraph
   ↓
5. Skill nodes use services (search_service, llm_service) directly
   ↓
6. Skill returns structured output to agent
```

**Key Insight**: Skills do NOT call tools. They use services directly:
- `search_service.search_raw()` instead of `web_search` tool
- `llm_service.get_llm_for_tier()` instead of LLM tool calls
- `app_sandbox_manager.create_project()` instead of app_builder tools

### 3. Why This Architecture?

**Separation of Concerns**:
- **Tools** = Simple, direct capabilities for agents
- **Skills** = Complex, multi-step workflows that need orchestration

**Benefits**:
1. **Skills encapsulate complexity**: A skill like `app_builder` handles planning, file generation, package installation, server startup - all internally
2. **Skills can be reused**: Multiple agents can invoke the same skill
3. **Skills have structured I/O**: Clear parameters and output schemas
4. **Skills can be versioned**: Metadata includes version numbers
5. **Skills can be dynamically loaded**: Custom skills can be added via database

**Example: App Builder Skill**
```python
# Agent calls: invoke_skill("app_builder", {"description": "todo app"})
# 
# Skill internally:
# 1. plan_app node: Uses llm_service to generate plan
# 2. generate_files node: Uses llm_service to generate code
# 3. create_project node: Uses app_sandbox_manager service
# 4. install_packages node: Uses app_sandbox_manager service
# 5. start_server node: Uses app_sandbox_manager service
# 
# Returns: {"preview_url": "...", "files_created": [...]}
```

### 4. Tool vs Skill Decision Matrix

| Aspect | Use Tool | Use Skill |
|--------|----------|-----------|
| **Complexity** | Single operation | Multi-step workflow |
| **State Management** | Stateless | Needs internal state |
| **Reusability** | Direct function call | Composable subgraph |
| **I/O Structure** | Simple params/return | Structured schema |
| **Examples** | `web_search("query")` | `invoke_skill("web_research", {"topic": "..."})` |
| | `execute_code("print('hi')")` | `invoke_skill("app_builder", {...})` |
| | `browser_navigate("url")` | `invoke_skill("data_visualization", {...})` |

### 5. Execution Flow Example

**Scenario**: User asks "Research the latest trends in AI"

```
1. Agent (reason_node):
   - Receives query: "Research the latest trends in AI"
   - LLM decides: Use web_research skill (better than basic web_search)
   - Calls: invoke_skill("web_research", {"topic": "latest trends in AI"})

2. Tool (invoke_skill):
   - Validates skill exists in registry
   - Validates parameters match skill schema
   - Calls SkillExecutor.execute_skill()

3. Skill Executor:
   - Gets WebResearchSkill from registry
   - Creates initial state: {"input_params": {"topic": "..."}, "output": {}}
   - Executes skill's LangGraph: search_node → summarize_node → END

4. Skill Nodes:
   - search_node: Calls search_service.search_raw() directly (NOT web_search tool)
   - summarize_node: Calls llm_service.get_llm_for_tier() directly
   - Returns: {"summary": "...", "sources": [...], "key_findings": [...]}

5. Tool (invoke_skill):
   - Collects skill output and events
   - Returns JSON string to agent

6. Agent (act_node):
   - Receives ToolMessage with skill results
   - Continues reasoning with results in context

7. Agent (reason_node):
   - Uses skill output to generate final response
   - No more tool calls needed
   - Finalizes with response
```

### 6. Key Code Locations

**Tool Registry**: `backend/app/agents/tools/registry.py`
- Defines tool categories and agent mappings
- `get_tools_for_agent()` - Returns tools available to an agent
- `TOOL_CATALOG` - All tools organized by category

**Skill Invocation Tool**: `backend/app/agents/tools/skill_invocation.py`
- `invoke_skill` - Tool that agents call to invoke skills
- `list_skills` - Tool to discover available skills

**Skill Registry**: `backend/app/services/skill_registry.py`
- Manages skill discovery and loading
- Handles both builtin and dynamic skills
- `get_skill()` - Retrieves skill by ID

**Skill Executor**: `backend/app/services/skill_executor.py`
- Executes skill LangGraph subgraphs
- Manages execution state and events
- Streams events back to agent

**Agent Implementation**: `backend/app/agents/subagents/chat.py`
- `reason_node` - LLM reasoning with tools bound
- `act_node` - Executes tool calls (including invoke_skill)
- ReAct loop: reason → act → reason → ... → finalize

### 7. Important Distinctions

**Tools are NOT available inside Skills**:
- Skills cannot call `web_search`, `execute_code`, or other tools
- Skills use services directly: `search_service`, `llm_service`, etc.
- This prevents circular dependencies and keeps skills self-contained

**Skills are invoked via Tools**:
- The `invoke_skill` tool is the bridge between agents and skills
- Agents see skills as just another tool option
- Skills appear in the tool list alongside direct tools

**Skills can specify required_tools**:
- Skills have a `required_tools` metadata field
- This is documentation only - it lists what tools the skill conceptually uses
- Example: `web_research` skill has `required_tools=["web_search"]` but actually uses `search_service`

### 8. Design Rationale

**Why Skills Don't Use Tools**:
1. **Avoid circular dependencies**: If skills called tools, and tools could call skills, we'd have cycles
2. **Service layer abstraction**: Services provide a cleaner API than tool wrappers
3. **Performance**: Direct service calls are more efficient than tool invocation overhead
4. **State management**: Skills manage their own state; tools are stateless

**Why Agents Use Tools (not services directly)**:
1. **LLM integration**: Tools are LangChain-compatible for LLM tool calling
2. **Standardization**: Tools provide consistent interface for agents
3. **Guardrails**: Tools can have safety checks (tool_scanner)
4. **HITL support**: Tools can require approval before execution

## Summary

- **Tools** = Atomic capabilities that agents call directly
- **Skills** = Composable workflows invoked via `invoke_skill` tool
- **Relationship** = Agents → Tools → Skills (via invoke_skill) → Services
- **Key Point** = Skills use services, not tools, to avoid circular dependencies and maintain clean architecture

The architecture enables:
- Simple operations via direct tools
- Complex workflows via skills
- Reusable, versioned, structured capabilities
- Clear separation between agent reasoning and skill execution

## Concrete Example: Web Search Tool vs Web Research Skill

For a detailed comparison of a specific tool vs skill pair, see:
- **[Web Search Tool vs Web Research Skill](./Web-Search-Tool-vs-Skill.md)** - Detailed comparison showing:
  - How `web_search` tool provides raw search results
  - How `web_research` skill adds AI summarization and analysis
  - When to use each approach
  - Performance and cost differences
  - Code examples and output comparisons
