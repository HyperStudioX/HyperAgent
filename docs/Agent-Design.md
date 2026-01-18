# Agent Design

This document describes the multi-agent system architecture used in HyperAgent.

## Architecture Overview

HyperAgent uses a **Supervisor/Orchestrator Pattern** built on LangGraph's StateGraph to create a hierarchical multi-agent system. A central supervisor routes queries to specialized subagents, which can collaborate via handoffs and share context through a shared memory system.

```
┌─────────────────────────────────────────────────────────────┐
│                     Entry Point                             │
│                   /api/v1/query                             │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Router Node                               │
│  • Explicit mode override OR                                │
│  • LLM-based routing (FLASH tier for speed)                 │
│  • JSON response: {agent, confidence, reason}               │
└─────────────────────┬───────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│               Conditional Edge (select_agent)               │
└───────┬───────┬───────┬───────┬───────┬─────────────────────┘
        ▼       ▼       ▼       ▼       ▼
     ┌─────┐ ┌────────┐ ┌────┐ ┌───────┐ ┌────┐
     │Chat │ │Research│ │Code│ │Writing│ │Data│
     └──┬──┘ └───┬────┘ └─┬──┘ └───┬───┘ └─┬──┘
        │        │        │        │        │
        └────────┴────────┴────────┴────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           Conditional Edge (check_for_handoff)              │
│  • If pending_handoff → back to router                      │
│  • If handoff_count >= MAX_HANDOFFS → END                   │
│  • Otherwise → END                                          │
└─────────────────────────────────────────────────────────────┘
```

## Agent Types

Five specialized subagents handle different types of tasks:

| Agent | Purpose | Use Cases |
|-------|---------|-----------|
| **Chat** | General conversation | Q&A, greetings, casual interactions |
| **Research** | In-depth analysis | Web search, comprehensive reports, 4 scenarios |
| **Code** | Programming tasks | Code generation, debugging, execution |
| **Writing** | Content creation | Articles, documentation, essays |
| **Data** | Data analysis | CSV/JSON processing, statistics, visualization |

Defined in `api/app/agents/state.py`:

```python
class AgentType(str, Enum):
    CHAT = "chat"
    RESEARCH = "research"
    CODE = "code"
    WRITING = "writing"
    DATA = "data"
```

## Routing System

### LLM-Based Routing

The router uses a FLASH tier model for fast, cost-efficient routing decisions.

**Location**: `api/app/agents/routing.py`

**Process**:
1. Check for explicit `mode` parameter (bypasses LLM)
2. Send query to LLM with routing prompt
3. Parse JSON response: `{agent, confidence, reason}`
4. Flag as low confidence if `confidence < 0.5`

**Response Structure**:
```python
@dataclass
class RoutingResult:
    agent: AgentType
    reason: str
    confidence: float = 1.0
    is_low_confidence: bool = False
```

### Routing Prompt

The router prompt provides examples for each agent type and requests JSON output:

```
Available agents:
1. chat - General conversation, simple Q&A
2. research - In-depth research, web search, reports
3. code - Code execution, scripts, debugging
4. writing - Long-form content, articles, documentation
5. data - Data analysis, CSV/JSON, visualization

Response format:
{"agent": "...", "confidence": 0.0-1.0, "reason": "..."}
```

## Handoff Mechanism

Agents can delegate tasks to other specialized agents using the handoff system.

**Location**: `api/app/agents/tools/handoff.py`

### Handoff Matrix

Defines which agents can delegate to which others:

```
CHAT    → [RESEARCH, CODE, WRITING, DATA]
RESEARCH → [CODE, DATA]
WRITING → [RESEARCH]
CODE    → [DATA]
DATA    → [CODE]
```

### Handoff Controls

| Control | Value | Purpose |
|---------|-------|---------|
| Max Handoffs | 3 | Prevents infinite loops |
| Back-and-forth Prevention | A→B→A blocked | Prevents ping-pong delegation |
| Matrix Validation | Required | Ensures valid handoff paths |

### HandoffInfo Structure

```python
class HandoffInfo(TypedDict, total=False):
    source_agent: str      # Agent that initiated the handoff
    target_agent: str      # Agent to transfer control to
    task_description: str  # What the target agent should do
    context: str           # Additional context for the handoff
```

### HandoffManager

Tracks handoff state and enforces limits:

```python
class HandoffManager:
    max_handoffs: int = 3
    handoff_count: int
    visited_agents: list[str]
    handoff_history: list[dict]

    def can_handoff(source, target) -> bool
    def record_handoff(source, target, task, context)
    def get_handoff_summary() -> str
```

### Creating Handoff Tools

Handoff tools are dynamically created per agent:

```python
def get_handoff_tools_for_agent(agent_type: str) -> list[BaseTool]:
    """Returns list of handoff_to_<target> tools for allowed targets."""
```

Tool names follow pattern: `handoff_to_<target_agent>`

## Shared Memory System

Cross-agent context is preserved via shared memory with priority-based truncation.

**Location**: `api/app/agents/supervisor.py`

### Memory Fields

```python
class SharedAgentMemory(TypedDict, total=False):
    # Research artifacts
    research_findings: str
    research_sources: list[dict]

    # Code artifacts
    generated_code: str
    code_language: str
    execution_results: str

    # Writing artifacts
    writing_outline: str
    writing_draft: str

    # Data analysis artifacts
    data_analysis_plan: str
    data_visualizations: list[dict]

    # General
    additional_context: str
```

### Priority-Based Truncation

Total budget: **8000 characters**

| Field | Priority | Description |
|-------|----------|-------------|
| research_findings | 3 | Core research output |
| generated_code | 3 | Code artifacts |
| writing_draft | 3 | Main content |
| research_sources | 2 | Supporting evidence |
| execution_results | 2 | Code results |
| writing_outline | 2 | Structure |
| data_analysis_plan | 2 | Analysis approach |
| additional_context | 2 | General context |
| code_language | 1 | Metadata |
| data_visualizations | 1 | Binary data |

Minimum allocation: **200 characters** per field

### Smart Truncation

Truncates at natural boundaries:
1. Paragraph boundary (if > 60% content preserved)
2. Sentence boundary (if > 50% content preserved)
3. Word boundary (if > 40% content preserved)
4. Hard truncate with `[...truncated]` indicator

## State Management

### SupervisorState (Base)

All subagent states extend this base:

```python
class SupervisorState(TypedDict, total=False):
    # Input
    query: str
    mode: str | None
    messages: list[dict]

    # Routing
    selected_agent: str
    routing_reason: str
    routing_confidence: float

    # Handoff support
    active_agent: str | None
    delegated_task: str | None
    handoff_context: str | None
    handoff_count: int
    handoff_history: list[HandoffInfo]
    pending_handoff: HandoffInfo | None
    shared_memory: SharedAgentMemory

    # Tool execution
    tool_iterations: int

    # Output
    response: str
    events: Annotated[list[dict], operator.add]

    # Metadata
    task_id: str | None
    user_id: str | None
    attachment_ids: list[str]
    image_attachments: list[dict]
    provider: LLMProvider
    model: str | None
    tier: ModelTier | None
```

### Specialized States

| State Class | Extended Fields |
|-------------|----------------|
| **ChatState** | `system_prompt`, `lc_messages` |
| **ResearchState** | `depth`, `scenario`, `sources`, `analysis`, `synthesis` |
| **CodeState** | `code`, `language`, `stdout`, `stderr`, `sandbox_id` |
| **WritingState** | `writing_type`, `tone`, `outline`, `draft`, `final_content` |
| **DataAnalysisState** | `data_source`, `data_type`, `analysis_plan`, `visualizations` |

## Event System

Type-safe events for real-time streaming to clients.

**Location**: `api/app/agents/events.py`

### Event Types

| Category | Types | Purpose |
|----------|-------|---------|
| Lifecycle | `stage`, `complete`, `error` | Process lifecycle |
| Content | `token`, `visualization` | Streaming content |
| Tools | `tool_call`, `tool_result` | Tool execution |
| Routing | `routing`, `handoff`, `config` | Agent coordination |
| Domain | `source`, `code_result` | Agent-specific data |

### Stage Events

```python
class StageEvent(BaseModel):
    type: Literal["stage"] = "stage"
    name: str           # e.g., "search", "analyze", "plan"
    description: str    # Human-readable description
    status: StageStatus # running, completed, failed
    timestamp: int      # Milliseconds
```

### Tool Events

Tool calls and results are matched by unique ID:

```python
class ToolCallEvent(BaseModel):
    type: Literal["tool_call"]
    tool: str
    args: dict
    id: str | None      # For matching with result
    timestamp: int

class ToolResultEvent(BaseModel):
    type: Literal["tool_result"]
    tool: str
    content: str        # May be truncated to 500 chars
    id: str | None      # Matches tool_call id
    timestamp: int
```

### Factory Functions

Convenience functions for event creation:

```python
from app.agents.events import stage, token, tool_call, tool_result, error, complete

# Example usage
events.append(stage("search", "Searching the web...", "running"))
events.append(tool_call("web_search", {"query": "..."}, tool_id="123"))
events.append(tool_result("web_search", "Results...", tool_id="123"))
events.append(stage("search", "Search complete", "completed"))
```

## Streaming Configuration

Controls which nodes stream tokens to clients:

```python
STREAMING_CONFIG = {
    "write": True,
    "finalize": True,
    "summarize": True,
    "agent": True,
    "generate": False,   # Code gen - internal, results shown via summarize
    "outline": False,    # Internal step
    "synthesize": True,
    "analyze": False,    # Internal, only show final
    "router": False,
    "tools": False,
    "search_agent": False,
    "search_tools": False,
}
```

## Frontend Progress Tracking

The frontend tracks agent progress for real-time UI updates.

**Location**: `web/lib/stores/agent-progress-store.ts`

### ActiveAgentProgress

```typescript
interface ActiveAgentProgress {
    conversationId: string | null;
    agentType: AgentType;
    events: TimestampedEvent[];
    sources: Source[];
    isStreaming: boolean;
    currentStage: string | null;
    currentStageIndex: number | null;
    startTime: Date;
}
```

### TimestampedEvent

Extends base events with timing and hierarchy:

```typescript
interface TimestampedEvent extends AgentEvent {
    timestamp: number;
    endTimestamp?: number;      // Marks completion
    parentStageIndex?: number;  // Links tools to parent stage
}
```

### Store Actions

| Action | Purpose |
|--------|---------|
| `startProgress(id, type)` | Initialize progress tracking |
| `addEvent(event)` | Add timestamped event |
| `updateStage(stage)` | Update current stage |
| `endProgress()` | Mark as complete |
| `clearProgress()` | Reset state |
| `togglePanel()` | Show/hide progress panel |

### Event Processing

The store processes events to:
1. Track stage running/completed with timestamps
2. Match `tool_result` to `tool_call` by ID
3. Link tool events to parent stages
4. Aggregate sources for research agents

## Subagent Graph Structures

Each subagent is a compiled LangGraph StateGraph.

### Research Subagent

```
init_config → search_agent ⇄ search_tools → analyze → synthesize → finalize
```

- ReAct loop for search decisions
- Tools: `web_search`, `generate_image`, `analyze_image`
- 4 scenarios: academic, market, technical, news

### Chat Subagent

```
agent ⇄ tools (max 5 iterations)
```

- Optional tool calling
- Tools: `web_search`, `generate_image`, `analyze_image`

### Code Subagent

```
generate_code → execute (E2B sandbox, max 3 iterations)
```

### Writing Subagent

```
analyze → outline → write → finalize
```

### Data Analytics Subagent

```
plan → generate → execute (E2B sandbox) → summarize
```

## API Integration

### Entry Point

`POST /api/v1/query`

### Request Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | User query |
| `mode` | string? | Explicit agent mode (bypasses routing) |
| `task_id` | string? | Task tracking ID |
| `messages` | list? | Chat history |
| `depth` | string? | Research depth (research only) |
| `scenario` | string? | Research scenario (research only) |

### Response

Server-Sent Events (SSE) stream with event types described above.

## Key Design Patterns

1. **LangGraph StateGraph**: Hierarchical graph structure for orchestration
2. **Conditional Edges**: Route based on routing decisions and handoff checks
3. **Tool Node Pattern**: Prebuilt ToolNode for tool execution
4. **ReAct Loop**: Agent → Tool Call → Tool Execution → Loop
5. **Memory Budget System**: Dynamic truncation for context windows
6. **Event Streaming**: Real-time progress updates via SSE
7. **Type Safety**: Pydantic models for all state and events

## File Reference

| File | Purpose |
|------|---------|
| `api/app/agents/supervisor.py` | Main supervisor graph |
| `api/app/agents/routing.py` | LLM-based routing |
| `api/app/agents/state.py` | State definitions |
| `api/app/agents/events.py` | Event schema |
| `api/app/agents/tools/handoff.py` | Handoff tools |
| `api/app/agents/subagents/` | Subagent implementations |
| `web/lib/stores/agent-progress-store.ts` | Frontend progress |
