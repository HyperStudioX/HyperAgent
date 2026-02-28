# Agent System Design

## Overview

HyperAgent uses a **hybrid architecture** with two agents and a composable skills system:

- **Task Agent** — General-purpose agent with ReAct tool-calling loop. Handles ~80% of requests including chat, data analysis, app building, image generation, slide creation, and browser automation.
- **Research Agent** — Specialized multi-step research with search, analysis, synthesis, and report writing.

A supervisor routes queries and manages agent handoff.

## Core Philosophy

**Skills = Composable capabilities** (LangGraph subgraphs invoked as tools)
**Agents = Workflow orchestration** (ReAct loops with tool calling)
**Tools = Atomic operations** (web search, code execution, browser actions)

## Architecture

```
┌──────────────────────────────────┐
│          User Request            │
└───────────────┬──────────────────┘
                │
         ┌──────▼──────┐
         │  Supervisor  │
         │   (Router)   │
         └──────┬───────┘
                │
      ┌─────────┴─────────┐
      │                    │
  Most Tasks         Deep Research
      │                    │
      ▼                    ▼
┌───────────┐       ┌───────────┐
│   TASK    │       │ RESEARCH  │
│   Agent   │       │   Agent   │
│           │       │           │
│ ReAct loop│  ───► │ search →  │
│ + tools   │ hand  │ analyze → │
│ + skills  │  off  │ synthesize│
└─────┬─────┘       │ → write   │
      │              └───────────┘
      │ invoke_skill
      ▼
┌──────────────────────────┐
│     Skills System        │
├──────────────────────────┤
│ image_generation         │
│ code_generation          │
│ web_research             │
│ data_analysis            │
│ slide_generation         │
│ app_builder              │
│ task_planning            │
└──────────────────────────┘
```

## Routing

The supervisor uses LLM-based routing to select the appropriate agent. Explicit mode overrides (app, image, slide, data) skip LLM routing and go directly to the Task agent.

```
Is it deep research (10+ sources, detailed report)?
  YES → RESEARCH Agent
  NO  → TASK Agent (uses skills/tools as needed)
```

### Mode-to-Agent Mapping

| Mode | Agent | Notes |
|------|-------|-------|
| `task` (default) | Task | General chat, Q&A |
| `research` | Research | Deep multi-source research |
| `data` | Task | Data analysis via code execution |
| `app` | Task | Direct skill invocation → `app_builder` |
| `image` | Task | Direct skill invocation → `image_generation` |
| `slide` | Task | Direct skill invocation → `slide_generation` |

For dedicated modes (app, image, slide), the Task agent bypasses LLM reasoning and directly synthesizes an `invoke_skill` tool call on the first iteration.

## Task Agent

**File:** `backend/app/agents/subagents/task.py`

### ReAct Loop

```
reason_node → should_continue → act_node → should_wait_or_reason → reason_node → ... → finalize_node
```

- **reason_node**: LLM reasons about what to do, may emit tool calls
- **act_node**: Executes tool calls (with HITL approval for high-risk tools)
- **wait_interrupt_node**: Waits for user response to `ask_user` interrupts
- **finalize_node**: Extracts final response from messages

### Available Tools

| Category | Tools |
|----------|-------|
| Search | `web_search` |
| Image | `generate_image`, `analyze_image` |
| Browser | `browser_navigate`, `browser_screenshot`, `browser_click`, `browser_type`, `browser_press_key`, `browser_scroll`, `browser_get_stream_url` |
| Code | `execute_code` |
| Data | `sandbox_file` |
| App | `create_app_project`, `app_write_file`, `app_install_packages`, `app_start_server` |
| Skills | `invoke_skill`, `list_skills` |
| Slides | `generate_slides` |
| Handoff | `delegate_to_research` |
| HITL | `ask_user` |

### Planned Execution

When the `task_planning` skill returns a plan, the Task agent enters planned execution mode:
- Plan steps stored in `execution_plan` state
- Step guidance injected before each LLM call
- Progress events emitted as steps complete
- `current_step_index` tracks position

### Context Compression

Applied in `reason_node` before each LLM call when token count exceeds threshold:
1. Estimates token count for all messages
2. If above threshold (default 60k), compresses older messages using FLASH-tier LLM
3. Injects summary as system context message
4. Falls back to message truncation if compression fails

## Research Agent

**File:** `backend/app/agents/subagents/research.py`

### Pipeline

```
init_config → search_loop → analyze → synthesize → write_report
```

- **init_config**: Determines search depth and scenario (academic, market, technical, news)
- **search_loop**: Iterative web search with source collection
- **analyze**: Analyzes gathered sources for relevance and key findings
- **synthesize**: Synthesizes findings across sources
- **write_report**: Generates structured report with citations

## Skills System

### Base Classes

**File:** `backend/app/agents/skills/skill_base.py`

- `Skill` — Base class with `create_graph()` returning a LangGraph `StateGraph`
- `ToolSkill` — Simplified subclass with `execute()` (auto-generates single-node graph)
- `SkillMetadata` — Pydantic model: id, version, description, category, parameters, output_schema
- `SkillContext` — Execution context with `invoke_skill()` for skill composition

### Builtin Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `image_generation` | creative | AI image generation via Gemini or DALL-E |
| `code_generation` | code | Generate code snippets for specific tasks |
| `web_research` | research | Focused web research with source summarization |
| `data_analysis` | data | Full data analysis: plan, execute code in sandbox, summarize results |
| `slide_generation` | creative | Create PPTX presentations with research and outlines |
| `app_builder` | automation | Build web apps (React, Next.js, Vue, Express, FastAPI, Flask) with live preview. Planning uses MAX tier, code generation uses PRO. |
| `task_planning` | automation | Analyze complex tasks and create execution plans |

### Invocation

Agents invoke skills via two tools:
- `invoke_skill(skill_id, params)` — Execute a skill with parameters
- `list_skills()` — Discover available skills

Skills can compose with each other via `SkillContext.invoke_skill()`.

## Supervisor

**File:** `backend/app/agents/supervisor.py`

Orchestrates the multi-agent workflow:

1. **Routing**: LLM-based agent selection (or explicit mode override)
2. **Agent Execution**: Invokes selected agent subgraph
3. **Handoff**: Task agent can delegate to Research agent via `delegate_to_research` tool (max 3 handoffs)
4. **Event Streaming**: Normalizes and deduplicates events from LangGraph via `StreamProcessor`

### State Hierarchy

```
SupervisorState (base)
├── TaskState (extends for tool calling, planned execution, HITL)
└── ResearchState (extends for search/analysis/synthesis)
```

## LLM Provider System

### Built-in Providers

Anthropic, OpenAI, Google Gemini — each with per-tier model defaults.

### Custom Providers

Any OpenAI-compatible API can be registered via `CUSTOM_PROVIDERS` env var:

```json
[{
  "name": "qwen",
  "api_key": "sk-...",
  "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "tier_models": {"pro": "qwen3.5-plus", "flash": "qwen3.5-flash"},
  "enable_thinking": true
}]
```

### Model Tiers

| Tier | Purpose | Example (Anthropic) |
|------|---------|---------------------|
| MAX | Best quality, complex reasoning | claude-opus-4 |
| PRO | Balanced quality/speed | claude-sonnet-4 |
| FLASH | Fast, cost-efficient | claude-3.5-haiku |

Per-tier provider overrides: `MAX_MODEL_PROVIDER`, `PRO_MODEL_PROVIDER`, `FLASH_MODEL_PROVIDER`.

### Thinking Mode

**File:** `backend/app/ai/thinking.py`

`ThinkingAwareChatOpenAI` handles providers that return `reasoning_content` (Qwen, DeepSeek, Kimi):
- **Always captures** `reasoning_content` from API responses (streaming and non-streaming)
- **Auto-detects** thinking mode when `reasoning_content` first appears
- **Patches outgoing** assistant messages with captured `reasoning_content` for multi-turn replay

## Human-in-the-Loop (HITL)

### Architecture

Redis pub/sub-based interrupt lifecycle:

1. Agent creates interrupt via `ask_user` tool
2. Interrupt stored in Redis with TTL, streamed as SSE event to frontend
3. Frontend shows approval/decision/input dialog
4. User response published to Redis channel
5. Agent receives response and continues

### Interrupt Types

- **APPROVAL** — Approve/deny high-risk tool execution (120s timeout)
- **DECISION** — Choose between multiple options (300s timeout)
- **INPUT** — Free-form text input (300s timeout)

### Tool Risk Assessment

High-risk tools require user approval before execution. Users can "approve always" to auto-approve specific tools for the session.

## Safety Guardrails

Three scanners integrated at different points in the request lifecycle:

### Input Scanner
Scans user input before processing:
- Prompt injection detection via `llm-guard`
- Jailbreak pattern matching (regex-based)

### Output Scanner
Scans LLM responses before streaming:
- Toxicity detection
- PII detection with redaction
- Harmful content pattern matching

### Tool Scanner
Validates tool arguments before execution:
- URL validation (blocks `file://`, `localhost`, private IPs)
- Code safety (blocks `rm -rf /`, fork bombs, remote code execution)

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `GUARDRAILS_ENABLED` | `true` | Master toggle |
| `GUARDRAILS_INPUT_ENABLED` | `true` | Input scanning |
| `GUARDRAILS_OUTPUT_ENABLED` | `true` | Output scanning |
| `GUARDRAILS_TOOL_ENABLED` | `true` | Tool argument scanning |
| `GUARDRAILS_VIOLATION_ACTION` | `block` | Action: `block`, `warn`, `log` |
| `GUARDRAILS_TIMEOUT_MS` | `500` | Scan timeout |

## Sandbox System

### Providers

| | E2B | BoxLite |
|---|---|---|
| Type | Cloud | Local (Docker) |
| Requires | `E2B_API_KEY` | Docker |
| Code execution | Python, JS, TS, Bash | Python, JS, TS, Bash |
| Browser automation | E2B Desktop | Docker desktop image |
| App hosting | Cloud URLs | Local ports |

Configured via `SANDBOX_PROVIDER` env var.

### Sandbox Types

- **Code Executor** — Run code snippets with output capture
- **Desktop Executor** — Browser automation with screenshots and streaming
- **App Runtime** — Scaffold, build, and host web applications

## Event System

24 event types streamed via SSE:

**Lifecycle:** `stage`, `complete`, `error`
**Content:** `token`, `image`, `code_result`
**Tools:** `tool_call`, `tool_result`
**Research:** `source`, `routing`, `handoff`
**Sandbox:** `browser_stream`, `browser_action`, `workspace_update`, `terminal_command`, `terminal_output`, `terminal_error`, `terminal_complete`
**Skills:** `skill_output`, `plan_step`
**HITL:** `interrupt`, `interrupt_response`

## Context Compression

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `CONTEXT_COMPRESSION_ENABLED` | `true` | Enable/disable |
| `CONTEXT_COMPRESSION_TOKEN_THRESHOLD` | `60000` | Token count trigger |
| `CONTEXT_COMPRESSION_PRESERVE_RECENT` | `10` | Recent messages to keep |

### Process

1. Estimate token count before each LLM call
2. If above threshold, separate system/old/recent messages
3. Summarize old messages using FLASH-tier LLM
4. Inject summary as system context message
5. Preserve tool message pairs (AIMessage + ToolMessage)
6. Fall back to truncation if compression fails

## Backward Compatibility

Deprecated agent types are mapped to Task agent:
- IMAGE → Task + `image_generation` skill
- WRITING → Task (handled directly by LLM)
- CODE → Task + `code_generation` skill
- DATA → Task + `data_analysis` skill
- APP → Task + `app_builder` skill
- SLIDE → Task + `slide_generation` skill
