# How the Task Agent Decides to Invoke Tools or Skills

## Overview

The task agent uses **LLM-based autonomous decision-making** to choose between tools and skills. The decision is not hardcoded but emerges from:

1. **System prompt guidance** - Instructions on when to use what
2. **Tool descriptions** - LangChain tool schemas that the LLM sees
3. **Context awareness** - The agent understands the user's intent
4. **Tool binding** - All tools (including skill invocation tools) are bound to the LLM

## Decision-Making Process

### Step 1: Tool Binding

**Location**: `backend/app/agents/subagents/task.py` (reason_node)

```python
# Get all tools for task agent
all_tools = get_tools_for_agent("task", include_handoffs=True)

# Bind tools to LLM
llm_with_tools = llm.bind_tools(all_tools) if all_tools else llm

# LLM reasoning with tools available
ai_message = await llm_with_tools.ainvoke(lc_messages)
```

**What this means**:
- The LLM receives **all available tools** in its context
- Tools include both direct tools (`web_search`, `execute_code`) and skill invocation tools (`invoke_skill`, `list_skills`)
- The LLM can see tool names, descriptions, and parameter schemas
- **The LLM autonomously decides** which tool(s) to call based on the query

### Step 2: System Prompt Guidance

**Location**: `backend/app/agents/prompts.py` (CHAT_SYSTEM_PROMPT)

The system prompt provides explicit guidance on when to use tools vs skills:

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
- image_generation: Generate AI images from text descriptions
- data_analysis: Full data analysis with planning, code execution, and summarization
- task_planning: Analyze complex tasks and create structured execution plans
- slide_generation: Create professional PPTX presentations with research and structured outlines
- app_builder: Build and run web applications with live preview

When to use skills:
- Use list_skills first to discover available skills and their parameters
- Use invoke_skill when a task matches a skill's purpose better than basic tools
- Skills provide structured, focused capabilities for specific task types
- Skills can combine multiple steps into a single invocation
- Use task_planning for complex multi-step tasks that need upfront planning
</tools>
"""
```

**Key Guidance Points**:
1. **Direct tools** for simple, single operations
2. **Skills** for complex, multi-step workflows
3. **list_skills first** to discover what's available
4. **Skills when task matches skill's purpose** better than basic tools

### Step 3: Tool Descriptions

Each tool has a description that the LLM sees via LangChain's tool schema:

**Example: `web_search` tool description**:
```python
@tool(args_schema=WebSearchInput)
async def web_search(...) -> str:
    """Search the web for current information on any topic.
    
    Use this tool when you need to find up-to-date information, verify facts,
    or gather data from the internet. Returns relevant web pages with titles,
    URLs, and content snippets.
    """
```

**Example: `invoke_skill` tool description**:
```python
@tool(args_schema=InvokeSkillInput)
async def invoke_skill(
    skill_id: str,
    params: dict[str, Any],
    ...
) -> str:
    """Invoke a registered skill to perform a specialized task.

    Skills are composable subgraphs that provide focused capabilities like
    web research, data analysis, app building, and more. Each skill has
    its own input requirements and output format.
    
    To see available skills and their parameters, list them first or check
    the skill registry.
    """
```

**What the LLM sees**:
- Tool name (e.g., `web_search`, `invoke_skill`)
- Tool description (what it does, when to use it)
- Parameter schema (what inputs it needs)
- Return type (what it returns)

### Step 4: LLM Decision

The LLM makes the decision based on:

1. **User query analysis**: Understanding what the user wants
2. **Tool descriptions**: Matching query intent to available tools
3. **System prompt guidance**: Following instructions on when to use what
4. **Context**: Previous conversation and tool results

**Example Decision Flow**:

```
User: "Research the latest AI trends in 2024"

LLM Reasoning:
1. This is a research task
2. System prompt says: "web_research: Focused web research with source summarization"
3. System prompt says: "Use invoke_skill when a task matches a skill's purpose better than basic tools"
4. This matches web_research skill better than web_search tool (needs summarization)
5. Decision: Call invoke_skill("web_research", {"topic": "latest AI trends in 2024"})
```

vs.

```
User: "What is the capital of France?"

LLM Reasoning:
1. This is a simple fact lookup
2. System prompt says: "Use web_search when you need to verify facts"
3. This is a quick lookup, doesn't need summarization
4. Decision: Call web_search("capital of France")
```

## Decision Factors

### When Agent Chooses Direct Tools

**Factors**:
- ✅ **Simple, single operation** needed
- ✅ **Quick fact lookup** or verification
- ✅ **Direct control** over parameters
- ✅ **No analysis or summarization** required
- ✅ **Low latency** preferred

**Examples**:
- `web_search("capital of France")` - Simple fact lookup
- `execute_code("print('hello')")` - Simple code execution
- `browser_navigate("https://example.com")` - Direct browser action
- `generate_image("a cat")` - Direct image generation

### When Agent Chooses Skills

**Factors**:
- ✅ **Complex, multi-step workflow** needed
- ✅ **Structured analysis** required (summarization, insights)
- ✅ **Task matches skill's purpose** (research, code review, writing)
- ✅ **Combined operations** (search + summarize, plan + execute)
- ✅ **Structured output** needed (not just raw results)

**Examples**:
- `invoke_skill("web_research", {"topic": "AI trends"})` - Research with analysis
- `invoke_skill("data_analysis", {"query": "Summarize trends in this CSV"})` - Data analysis with code execution
- `invoke_skill("app_builder", {"description": "todo app"})` - Multi-step app building
- `invoke_skill("slide_generation", {"topic": "AI trends"})` - Presentation generation

## Code Flow

### 1. Tool Registration

```python
# backend/app/agents/tools/registry.py

# All tools are registered by category
TOOL_CATALOG: dict[ToolCategory, list[BaseTool]] = {
    ToolCategory.SEARCH: [web_search],
    ToolCategory.SKILL: get_skill_tools(),  # invoke_skill, list_skills
    # ... other categories
}

# Chat agent gets all tools from allowed categories
def get_tools_for_agent("task", include_handoffs=True) -> list[BaseTool]:
    # Returns: [web_search, execute_code, invoke_skill, list_skills, ...]
```

### 2. Tool Binding to LLM

```python
# backend/app/agents/subagents/task.py (reason_node)

# Get all tools
all_tools = get_tools_for_agent("task", include_handoffs=True)
# all_tools = [web_search, execute_code, invoke_skill, list_skills, ...]

# Bind to LLM
llm_with_tools = llm.bind_tools(all_tools)

# LLM reasoning - can now see and call any of these tools
ai_message = await llm_with_tools.ainvoke(lc_messages)
# ai_message.tool_calls = [{"name": "invoke_skill", "args": {...}}]
```

### 3. Tool Execution

```python
# backend/app/agents/subagents/task.py (act_node)

# Get tool map
tool_map = {tool.name: tool for tool in all_tools}
# tool_map = {"web_search": web_search_tool, "invoke_skill": invoke_skill_tool, ...}

# Execute tool calls from LLM
for tool_call in ai_message.tool_calls:
    tool_name = tool_call["name"]  # e.g., "invoke_skill"
    tool = tool_map[tool_name]
    result = await tool.ainvoke(tool_call["args"])
```

## Decision Examples

### Example 1: Simple Search → Direct Tool

**User Query**: "What is Python?"

**LLM Decision Process**:
1. Simple fact lookup question
2. `web_search` tool description: "Search the web for current information"
3. System prompt: "Use web_search when you need to verify facts"
4. **Decision**: Call `web_search("What is Python")`

**Result**: Raw search results returned to agent

### Example 2: Research Task → Skill

**User Query**: "Research the latest trends in AI and summarize the findings"

**LLM Decision Process**:
1. Complex research task requiring summarization
2. System prompt: "web_research: Focused web research with source summarization"
3. System prompt: "Use invoke_skill when a task matches a skill's purpose better than basic tools"
4. This needs summarization, not just raw results
5. **Decision**: Call `invoke_skill("web_research", {"topic": "latest trends in AI"})`

**Result**: Summarized research with key findings

### Example 3: Code Execution → Direct Tool

**User Query**: "Run this code: print('hello')"

**LLM Decision Process**:
1. Direct code execution request
2. `execute_code` tool description: "Run code in an isolated sandbox"
3. System prompt: "Use execute_code when the user asks you to run, execute, or test code"
4. **Decision**: Call `execute_code({"code": "print('hello')", "language": "python"})`

**Result**: Code execution output

### Example 4: Data Analysis → Skill

**User Query**: "Analyze this CSV and tell me the key trends"

**LLM Decision Process**:
1. Data analysis task requiring planning, code execution, and synthesis
2. System prompt: "data_analysis: Full data analysis with planning, code execution, and summarization"
3. This needs a multi-step workflow, not just code execution
4. **Decision**: Call `invoke_skill("data_analysis", {"query": "Analyze key trends", "attachment_ids": [...]})`

**Result**: Structured analysis with findings, code, and visualizations

### Example 5: Image Generation → Skill (via mode)

**User Query**: "Generate an image of a cat" (with mode="image")

**LLM Decision Process**:
1. Query enhanced in reason_node: "Generate an image based on this description: ... Use the image_generation skill"
2. System prompt guidance: "Use image_generation skill for AI images"
3. **Decision**: Call `invoke_skill("image_generation", {"prompt": "a cat"})`

**Result**: Generated image

## Mode-Based Guidance

The agent can receive mode hints that influence decisions:

```python
# backend/app/agents/subagents/task.py (reason_node)

if mode == "image":
    enhanced_query = f"Generate an image based on this description: {query}\n\nUse the image_generation skill to create the image."
elif mode == "app":
    enhanced_query = f"Build a web application based on this description: {query}\n\nUse the app_builder skill to create the application."
elif mode == "slide":
    enhanced_query = f"Create a presentation slide deck based on this description: {query}\n\nUse the slide_generation skill to create the presentation."
```

**Modes provide explicit guidance**:
- `mode="image"` → Guides agent to use `image_generation` skill
- `mode="app"` → Guides agent to use `app_builder` skill
- `mode="slide"` → Guides agent to use `slide_generation` skill

## Key Insights

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

## Improving Decision Quality

To improve how the agent decides between tools and skills:

1. **Enhance System Prompt**: Add more specific guidance on when to use each
2. **Improve Tool Descriptions**: Make tool descriptions clearer and more specific
3. **Add Examples**: Include examples in the system prompt showing correct usage
4. **Mode Hints**: Use mode parameters to provide explicit guidance
5. **Skill Metadata**: Ensure skill descriptions in the registry are clear and accurate

## Summary

The task agent decides between tools and skills through:

1. **LLM-based autonomous decision-making** - No hardcoded rules
2. **System prompt guidance** - Instructions on when to use what
3. **Tool descriptions** - LangChain schemas that the LLM sees
4. **Context awareness** - Understanding user intent and task complexity
5. **All tools bound** - Both direct tools and skill invocation tools are available

The decision emerges from the LLM's understanding of:
- What the user wants (query analysis)
- What tools/skills are available (tool registry)
- When to use each (system prompt + tool descriptions)
- How to combine them (context and reasoning)

This approach provides flexibility and adaptability while maintaining clear guidance through prompts and tool descriptions.
