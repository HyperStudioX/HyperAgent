# Skills + Agents: Simplified Hybrid Architecture

## Overview

HyperAgent uses a **simplified hybrid architecture**:
- **Chat Agent** - Primary agent that handles most tasks using skills
- **Research Agent** - Specialized for deep, comprehensive research workflows
- **Data Agent** - Specialized for data analytics and visualization
- **Computer Agent** - Specialized for browser automation and desktop control

## Core Philosophy

**Skills = Composable capabilities**
**Agents = Workflow orchestration**

The Chat agent with skills handles 80%+ of requests. Specialized agents are used only for complex workflows that require multi-step orchestration.

## Architecture Diagram

```
┌─────────────────────────────────────────┐
│           User Request                  │
└─────────────────┬───────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │   Supervisor    │
         │    (Router)     │
         └────────┬────────┘
                  │
      ┌───────────┴───────────┬────────────────┐
      │                       │                │
  Most Tasks         Deep Research      Data Analytics
      │                       │                │
      ▼                       ▼                ▼
┌──────────┐          ┌──────────┐      ┌──────────┐
│   CHAT   │          │ RESEARCH │      │   DATA   │
│  Agent   │          │  Agent   │      │  Agent   │
│          │          │          │      │          │
│ + Skills │          └──────────┘      └──────────┘
└────┬─────┘
     │
     │ invoke_skill
     ▼
┌──────────────────────────────┐
│      Skills System           │
├──────────────────────────────┤
│ • image_generation           │
│ • simple_writing             │
│ • code_generation            │
│ • code_review                │
│ • web_research               │
│ • data_visualization         │
└──────────────────────────────┘
```

## Agent Responsibilities

### 1. Chat Agent (Primary)

**Handles 80%+ of all requests:**
- General conversation and Q&A
- Image generation (via `image_generation` skill)
- Content writing (via `simple_writing` skill)
- Code generation (via `code_generation` skill)
- Code review (via `code_review` skill)
- Code execution (via `execute_code` tool)
- Quick web search (via `web_search` tool)
- Simple research (via `web_research` skill)

**Available Skills:**
- `image_generation` - AI image generation
- `simple_writing` - Document/email/article writing
- `code_generation` - Generate code snippets
- `code_review` - Review code for bugs/style/security
- `web_research` - Focused web research with summarization
- `data_visualization` - Generate visualization code

**Available Tools:**
- `web_search` - Search the web
- `execute_code` - Run code in sandbox
- `analyze_image` - Computer vision analysis
- `browser_*` - Browser automation tools
- `invoke_skill` - Invoke any skill
- `list_skills` - Discover available skills

### 2. Research Agent (Specialized)

**ONLY for deep research workflows:**
- Comprehensive multi-source research
- In-depth analysis and synthesis
- Detailed reports with citations
- Academic-level research papers
- Market research with multiple data points

**When to route here:**
- User explicitly asks for "research" or "comprehensive analysis"
- Requires synthesis from 10+ sources
- Needs structured report with sections
- Academic or professional research deliverables

### 3. Data Agent (Specialized)

**ONLY for data analytics:**
- CSV/JSON/Excel file processing
- Statistical analysis
- Data visualization and charting
- Trend analysis and insights
- Data transformation and cleaning

**When to route here:**
- User provides data files (CSV, JSON, etc.)
- Explicitly asks for "data analysis" or "analyze data"
- Requires statistical computations
- Needs data visualization/charts

### 4. Computer Agent (Specialized)

**ONLY for browser automation:**
- Visual website interaction
- Form filling and submission
- Clicking buttons and UI elements
- Taking screenshots of webpages
- Automated web scraping with interaction

**When to route here:**
- User asks to "go to [website]" and interact
- Requires clicking buttons or filling forms
- Needs to navigate multi-page workflows on websites
- Visual verification needed (screenshots)

## Routing Decision Tree

```
Is it browser automation?
  YES → COMPUTER Agent
  NO ↓

Is it data analytics (CSV/Excel)?
  YES → DATA Agent
  NO ↓

Is it comprehensive research (10+ sources, detailed report)?
  YES → RESEARCH Agent
  NO ↓

Everything else → CHAT Agent (uses skills)
```

## Examples: Task Routing

### Route to CHAT Agent

| User Request | Skill Used | Why Chat |
|-------------|------------|----------|
| "Generate an image of a sunset" | `image_generation` | Simple image request |
| "Write an email to my team" | `simple_writing` | Simple writing task |
| "Create a Python function to sort" | `code_generation` | Simple code generation |
| "Review this code for bugs" | `code_review` | Code review |
| "What are the latest AI trends?" | `web_search` tool | Quick search |
| "Write and run Python code" | `code_generation` + `execute_code` | Chat has both |
| "Quick research on topic X" | `web_research` | Simple research |

### Route to RESEARCH Agent

| User Request | Why Research |
|-------------|-------------|
| "Research and write a comprehensive report on quantum computing with 20+ sources" | Deep research workflow |
| "Create an academic paper on climate change" | Structured research deliverable |
| "Analyze market trends with detailed competitive analysis" | Multi-source synthesis |

### Route to DATA Agent

| User Request | Why Data |
|-------------|----------|
| "Analyze this CSV and create charts" | Data analytics |
| "Find trends in this sales data" | Statistical analysis |
| "Process this Excel file and visualize" | Data processing |

### Route to COMPUTER Agent

| User Request | Why Computer |
|-------------|-------------|
| "Go to amazon.com and find iPhone price" | Browser automation |
| "Fill out the contact form on example.com" | Form interaction |
| "Take a screenshot of google.com" | Visual browser task |

## Benefits of This Architecture

### 1. **Simplicity**
- One primary agent (Chat) for most tasks
- Clear specialization for complex workflows
- Fewer routing decisions to make

### 2. **Skills are Composable**
- Chat can combine multiple skills
- Example: `web_research` + `simple_writing` = quick report
- Example: `code_generation` + `execute_code` = tested code

### 3. **Scalability**
- Easy to add new skills
- Skills available to all agents
- No need to create agents for simple tasks

### 4. **Performance**
- Skills execute directly (no handoff)
- Faster response for simple tasks
- Specialized agents only for complex workflows

### 5. **Flexibility**
- Any agent can invoke any skill
- Research agent can use `image_generation`
- Data agent can use `simple_writing` for reports

## Context Compression

HyperAgent implements **LLM-based context compression** to manage long conversations efficiently while preserving semantic meaning.

### How It Works

When conversations exceed token limits, instead of simply dropping old messages, the system:

1. **Preserves Recent Messages**: Keeps the most recent messages intact (default: 10 messages)
2. **Summarizes Older Messages**: Uses a fast LLM (FLASH tier) to create a concise summary of older conversation history
3. **Injects Summary**: Adds the summary as context after system messages, maintaining conversation continuity
4. **Fallback Truncation**: If compression fails, falls back to message truncation as a safety measure

### Configuration

Context compression is configurable via settings:

- **`context_compression_enabled`**: Enable/disable compression (default: `true`)
- **`context_compression_token_threshold`**: Token count that triggers compression (default: 60k tokens = 60% of 100k budget)
- **`context_compression_preserve_recent`**: Number of recent messages to always keep intact (default: 10)
- **`max_summary_tokens`**: Maximum tokens for the summary itself (default: 2000)

### Benefits

- **Preserves Context**: Maintains conversation history without losing important information
- **Cost Efficient**: Uses fast FLASH tier LLM for summarization
- **Automatic**: Triggers automatically when token threshold is reached
- **Transparent**: Shows "context" stage in progress events when compression occurs

### Implementation

Context compression is integrated into the Chat agent's reasoning loop:
- Checks token count before each LLM call
- Compresses older messages if threshold exceeded
- Injects summary as a system context message
- Falls back to truncation if compression fails

## Human-in-the-Loop (HITL)

HyperAgent supports **Human-in-the-Loop** workflows, allowing agents to pause and request user input when needed.

### How It Works

Agents can use the `ask_user` tool to:

1. **Pause Execution**: Agent pauses and waits for user response
2. **Stream Interrupt**: Interrupt event is streamed to frontend via SSE
3. **User Responds**: Frontend shows dialog, user provides input
4. **Resume Execution**: Agent receives response and continues with the task

### Question Types

The `ask_user` tool supports three question types:

1. **Decision** - Multiple choice options
   ```python
   response = await ask_user(
       question="Which approach should I use?",
       question_type="decision",
       options=[
           {"label": "Option A", "value": "a", "description": "Details"},
           {"label": "Option B", "value": "b", "description": "Details"}
       ]
   )
   ```

2. **Input** - Free-form text input
   ```python
   response = await ask_user(
       question="What file name would you like?",
       question_type="input"
   )
   ```

3. **Confirmation** - Yes/No questions
   ```python
   response = await ask_user(
       question="Continue with this action?",
       question_type="confirmation"
   )
   ```

### Use Cases

Common scenarios where agents request user input:

- **Clarifying Ambiguous Requests**: When user intent is unclear
- **Choosing Between Options**: Multiple valid approaches available
- **Confirming Actions**: Before making significant changes
- **Gathering Information**: Additional details needed to proceed

### Implementation

HITL uses Redis pub/sub for real-time communication:

- **Storage**: Pending interrupts stored in Redis with TTL
- **Pub/Sub**: Real-time response delivery to waiting agents
- **Timeout**: Interrupts timeout after 120 seconds (configurable)
- **Recovery**: Interrupts persist in Redis for reconnection recovery

### Frontend Integration

The frontend displays interrupt dialogs with:
- Question text and optional context
- Input fields or option buttons
- Countdown timer showing remaining time
- Skip/cancel options

### State Management

HITL state is tracked in agent state:
- `pending_interrupt`: Current interrupt waiting for response
- `interrupt_response`: User's response to pending interrupt
- `interrupt_history`: History of interrupts in current session
- `auto_approve_tools`: Tools user has auto-approved
- `hitl_enabled`: Whether HITL is enabled for this request

## Backward Compatibility

The following agent types remain in the enum but are deprecated:

- **IMAGE** → Routed to Chat + `image_generation` skill
- **WRITING** → Routed to Chat + `simple_writing` skill
- **CODE** → Routed to Chat + `code_generation`/`code_review` skills

The routing logic automatically redirects these to Chat agent.

## Implementation Status

✅ **Completed:**
- 6 builtin skills implemented
- Skills system integrated into tool registry
- Skills API endpoints created
- Chat agent has access to all skills
- Routing logic updated to prefer Chat + Skills
- Frontend types and API client
- Context compression system implemented
- Human-in-the-Loop (HITL) system implemented
- Redis-based interrupt management

🔄 **Active:**
- All agents (Chat, Research, Data, Computer)
- Skills system fully functional
- Hybrid architecture operational
- Context compression active in Chat agent
- HITL available to all agents via `ask_user` tool

## Future Enhancements

1. **More Skills:**
   - Email composition skill
   - PDF generation skill
   - Translation skill
   - Summarization skill

2. **Skill Marketplace:**
   - Community-contributed skills
   - Skill discovery and installation
   - Skill versioning and updates

3. **Skill Composition:**
   - Skills invoking other skills
   - Workflow chains
   - Conditional skill execution

4. **Analytics:**
   - Skill usage tracking
   - Performance metrics
   - A/B testing of skill vs agent

## Summary

HyperAgent's simplified architecture provides:
- **Chat Agent** for 80%+ of tasks (with skills)
- **Research Agent** for deep research only
- **Data Agent** for data analytics only
- **Computer Agent** for browser automation only

This creates a clean, scalable system where **skills provide capabilities** and **agents provide orchestration** only when needed.
