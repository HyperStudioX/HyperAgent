# Agent Memory System

## Overview

HyperAgent includes a persistent memory system that allows the agent to remember information about users across conversations. Memories are automatically extracted after each conversation and injected into the agent's context at the start of every new request.

The system operates in two directions:

1. **Loading** — Memories are fetched from storage and injected as a system message before the LLM reasons.
2. **Extraction** — After a conversation completes, an LLM extracts notable information and persists it for future use.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Settings UI                         │
│              (memory toggle + CRUD manager)              │
└──────────────────────┬──────────────────────────────────┘
                       │ memory_enabled flag
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Query API Layer                        │
│  POST /api/v1/query/stream  →  UnifiedQueryRequest      │
└──────────────────────┬──────────────────────────────────┘
                       │ kwargs
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     Supervisor                           │
│  • Passes memory_enabled into agent state               │
│  • After completion: fires background extraction task    │
└──────┬───────────────────────────────────┬──────────────┘
       │                                   │
       ▼                                   ▼
┌──────────────┐                 ┌─────────────────────┐
│  Task Agent  │                 │  Memory Extraction   │
│  (loading)   │                 │  (background task)   │
└──────┬───────┘                 └──────────┬──────────┘
       │                                    │
       ▼                                    ▼
┌─────────────────────────────────────────────────────────┐
│               PersistentMemoryStore                      │
│  • PostgreSQL (primary)                                  │
│  • InMemoryStore (fallback for dev/testing)              │
└─────────────────────────────────────────────────────────┘
```

## Memory Types

| Type | Description | Examples |
|------|-------------|----------|
| `preference` | User preferences for style, tools, language | "Prefers Python with type hints", "Uses dark theme" |
| `fact` | Facts about the user | "Senior engineer at Acme Corp", "Works on ML pipelines" |
| `episodic` | Notable past interactions and outcomes | "Built a dashboard using app_builder, completed in 45s" |
| `procedural` | Workflows and procedures the user follows | "For data analysis: upload CSV → pandas → chart" |

## Memory Loading (Injection)

**File:** `backend/app/agents/subagents/task.py` — `_build_initial_messages()`

When the task agent starts a ReAct loop, it builds the LLM message list. If `memory_enabled` is true and a `user_id` is present, memories are fetched and injected:

```python
user_id = state.get("user_id")
memory_enabled = state.get("memory_enabled", True)
if user_id and memory_enabled:
    memory_text = await get_memory_store().format_memories_for_prompt_async(user_id)
    if memory_text:
        lc_messages.append(SystemMessage(content=memory_text))
```

### Message Structure

The resulting LLM context looks like:

```
[SystemMessage: system_prompt]        ← base agent instructions
[SystemMessage: user_memories]        ← injected memories (see format below)
[...conversation history...]          ← prior user/assistant messages
[HumanMessage: current query]         ← the user's new message
```

### Memory Prompt Format

Memories are formatted as an XML block grouped by type:

```xml
<user_memories>
Remembered from previous conversations:
<preferences>
<!-- Apply these preferences to tailor your responses (language, style, tools). -->
- Prefers Python with type hints
- Likes concise explanations
</preferences>
<facts>
<!-- Use these facts as context. Do not re-ask questions already answered here. -->
- Works at Acme Corp as a senior engineer
- Primary project is a data pipeline in Python
</facts>
<past_experiences>
<!-- Reference relevant past experiences. Reuse successful approaches; avoid repeating failures. -->
- Built a dashboard app using app_builder (tools: app_builder; outcome: completed; took 45s)
</past_experiences>
<procedures>
<!-- Follow these known procedures/tool sequences when the task matches. -->
- For data analysis: upload CSV → run pandas script → generate chart
</procedures>
Use these to personalize responses. Do not mention them unless asked.
</user_memories>
```

Each section includes a guidance comment that instructs the LLM on how to use those memories.

## Memory Extraction (Saving)

**File:** `backend/app/agents/supervisor.py` — after `run()` completes

After every conversation, the supervisor fires a background task to extract memories:

```python
memory_enabled = initial_state.get("memory_enabled", True)
if user_id and messages and memory_enabled:
    episodic_context = {
        "task_description": query[:500],
        "mode": original_mode,
        "tools_used": _tools_used,
        "outcome": "completed",
        "duration_seconds": _duration_s,
    }
    asyncio.create_task(self._extract_memories(...))
```

### Extraction Process

**File:** `backend/app/services/memory_service.py` — `extract_memories_from_conversation()`

1. Takes the **last 20 messages** from the conversation.
2. Builds an extraction prompt with the conversation text and episodic context (tools used, duration, outcome).
3. Sends it to a **LITE-tier LLM** — fast and cheap, since extraction doesn't need deep reasoning.
4. The LLM returns a JSON array of `{type, content}` objects.
5. Each extracted memory goes through:
   - **Safety check** — `_is_unsafe_instruction()` scans for prompt injection patterns (jailbreak, bypass guardrail, etc.). Unsafe memories are quarantined.
   - **Deduplication** — If identical content (case-insensitive) already exists, the existing entry's `access_count` is bumped instead of creating a duplicate.
   - **Persistence** — Stored via `PersistentMemoryStore.add_memory_async()` to PostgreSQL.

### Safety Patterns

The following patterns cause a memory to be quarantined (`trust_level: "quarantined"`):

- `ignore instruction/policy/rule/safety`
- `override safety/policy/guardrail`
- `system prompt`, `developer message`
- `tool without approval`
- `exfiltrate`, `leak`, `secret`
- `jailbreak`, `bypass guardrail`

Quarantined memories are never rendered into the agent's prompt.

Additionally, when rendering memories for the prompt, content is sanitized:
- Lines starting with `important:`, `instruction:`, `system:` are stripped
- Lines starting with `you must ...` are stripped
- Angle brackets (`<`, `>`) are removed to prevent XML injection

## Storage

### PersistentMemoryStore

**File:** `backend/app/services/memory_service.py`

A dual-layer store:

| Layer | When Used | Persistence |
|-------|-----------|-------------|
| PostgreSQL (via `app.db.models.Memory`) | Production, when DB is available | Durable across restarts |
| InMemoryStore (fallback) | Dev/testing, or if DB connection fails | Lost on restart |

The store automatically falls back to in-memory if the database is unavailable. All public methods have both sync and async variants (e.g., `get_memories()` / `get_memories_async()`).

### Data Model

Each memory entry contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `user_id` | string | Owner |
| `memory_type` | string | One of: preference, fact, episodic, procedural |
| `content` | string | The memory text |
| `metadata` | dict | Source info, safety flags, episodic context |
| `source_conversation_id` | string | Which conversation it was extracted from |
| `created_at` | timestamp | When created |
| `last_accessed` | timestamp | Last time loaded into a prompt |
| `access_count` | int | How many times loaded |

## Enable/Disable Toggle

The memory system can be toggled on/off per user via the Settings UI.

### Data Flow

```
Settings toggle (UI)
  → useSettingsStore.memoryEnabled (persisted to localStorage)
    → memory_enabled field in POST /api/v1/query/stream request body
      → UnifiedQueryRequest.memory_enabled (backend schema)
        → supervisor kwargs → initial_state["memory_enabled"]
          → task agent: skip injection if false
          → supervisor: skip extraction if false
```

Default is **true**. When disabled:
- No memories are loaded into the agent context
- No new memories are extracted after conversations
- Existing memories are preserved (not deleted)

## API Endpoints

### Memory CRUD

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/memory` | List all memories for the current user |
| `POST` | `/api/v1/memory` | Add a memory manually |
| `PUT` | `/api/v1/memory/:id` | Update a memory's content |
| `DELETE` | `/api/v1/memory/:id` | Delete a memory |

### Request/Response Examples

**List memories:**
```json
GET /api/v1/memory

Response:
{
  "memories": [
    {
      "id": "abc-123",
      "type": "preference",
      "content": "Prefers Python with type hints",
      "metadata": {},
      "created_at": 1709740800,
      "access_count": 5
    }
  ]
}
```

**Add a memory:**
```json
POST /api/v1/memory
{
  "type": "fact",
  "content": "Works on the HyperAgent project"
}
```

## Key Files

| File | Role |
|------|------|
| `backend/app/services/memory_service.py` | Core memory store, formatting, extraction logic |
| `backend/app/agents/subagents/task.py` | Memory injection into agent context |
| `backend/app/agents/supervisor.py` | Post-conversation memory extraction trigger |
| `backend/app/api/memory.py` | REST API endpoints for memory CRUD |
| `backend/app/models/schemas.py` | `UnifiedQueryRequest.memory_enabled` field |
| `web/components/settings/memory-section.tsx` | Settings UI for managing memories |
| `web/lib/stores/settings-store.ts` | `memoryEnabled` state persisted to localStorage |
