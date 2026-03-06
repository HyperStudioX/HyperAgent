# HyperAgent

> **Experimental** — This project is an exploration of multi-agent architectures, composable skill systems, and tool-calling workflows. It is under active development and not intended for production use. APIs, agent behaviors, and project structure may change without notice.

An experimental multi-agent platform built with LangGraph for exploring AI agent orchestration, composable skills, and multi-provider LLM integration.

## Architecture

### Agents

HyperAgent uses a hybrid architecture with two agents:

- **Task Agent** — General-purpose agent handling most requests via a ReAct loop with tool calling. Supports modes: chat, data analysis, app building, image generation, slide creation, and browser automation. Includes todo file persistence, anti-repetition detection, and optional CodeAct mode.
- **Research Agent** — Multi-step research with search, analysis, synthesis, and report writing. Used for deep research requiring 10+ sources.

A supervisor routes requests to the appropriate agent based on query intent. The Task agent handles ~80% of requests by invoking skills and tools directly.

### Skills

Skills are composable LangGraph subgraphs invoked as tools via `invoke_skill`:

`image_generation` · `code_generation` · `web_research` · `data_analysis` · `slide_generation` · `app_builder` · `task_planning` · `deep_research`

- **web_research** — Agentic search with query decomposition, parallel search, and evaluation (LITE/PRO/MAX tiers)
- **deep_research** — Multi-step deep research with source synthesis and report writing

### Tools

Organized by category: search, image, browser automation (7 tools), code execution, CodeAct (`execute_script`), file operations, app building, slide generation, skill invocation, and human-in-the-loop (`ask_user`).

### LLM Providers

Three built-in providers (Anthropic, OpenAI, Gemini) plus custom OpenAI-compatible providers (DeepSeek, Kimi, Qwen, MiniMax, Ollama, etc.) with three-tier model routing (MAX/PRO/LITE) and per-task auto-selection.

Includes `ThinkingAwareChatOpenAI` for providers with reasoning/thinking mode support — captures and replays `reasoning_content` for multi-turn tool-calling conversations.

### Sandbox

Dual sandbox providers for code execution, browser automation, and app hosting:

- **E2B** — Cloud sandboxes (requires `E2B_API_KEY`)
- **BoxLite** — Local Docker-based sandboxes (requires Docker)

Configured via `SANDBOX_PROVIDER` env var (`e2b` or `boxlite`). Unified Sandbox Manager provides a single shared instance per user+task. Persistent snapshots (R2/local) and handoff artifacts (max 10 files / 50MB) support session continuity.

### Other Systems

- **Context Compression** — LLM-based summarization when conversations exceed token thresholds (default 60k); KV-cache-friendly prompt construction
- **Safety Guardrails** — Input/output/tool scanning via `llm-guard` (prompt injection, toxicity, PII, unsafe URLs/code)
- **Human-in-the-Loop** — Redis pub/sub interrupts for user approval of high-risk actions (APPROVAL, DECISION, INPUT)
- **Agent Handoff** — Task agent can delegate to Research agent (max 3 handoffs per request)
- **MCP** — Model Context Protocol server support for external tool integration
- **Evaluation Framework** — Routing accuracy, tool selection, and response quality evals with mock LLMs

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (optional, for PostgreSQL, Redis, and BoxLite sandbox)

### 1. Clone and Setup Environment

```bash
cd HyperAgent
cp backend/.env.example backend/.env
cp web/.env.example web/.env
# Edit backend/.env and add your API keys (at least one LLM provider)
```

### 2. Start Database Services

Run PostgreSQL and Redis locally or via Docker. See [Development Guide](docs/Development.md) for setup.

### 3. Install Dependencies

```bash
make install
```

Or separately:

```bash
make install-web  # Frontend (npm)
make install-backend  # Backend (uv sync)
```

### 4. Start Backend

```bash
make migrate  # Apply database migrations (first time)
make dev-backend
```

### 5. Start Frontend

```bash
make dev-web
```

### 6. Start Worker (optional, for async tasks)

```bash
make dev-worker
```

Or start all services concurrently:

```bash
make dev-all
```

### 7. Open Application

Visit [http://localhost:5000](http://localhost:5000) (frontend) with backend at [http://localhost:8080](http://localhost:8080).

## Project Structure

```
HyperAgent/
├── web/                    # Next.js 16 frontend
│   ├── app/               # App Router pages
│   ├── components/        # React components (chat, computer, query, layout, etc.)
│   └── lib/               # Stores, hooks, types
├── backend/                # Python FastAPI backend
│   ├── app/
│   │   ├── routers/       # API endpoints
│   │   ├── agents/        # LangGraph agents, tools, skills
│   │   ├── sandbox/       # E2B, BoxLite, unified manager
│   │   ├── services/      # Business logic
│   │   └── models/        # Pydantic schemas
│   └── evals/             # Agent evaluation tests
├── docs/                   # Documentation
└── Makefile               # Development commands
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make dev-web` | Start frontend (port 5000) |
| `make dev-backend` | Start backend (port 8080) |
| `make dev-worker` | Start background worker |
| `make dev-all` | Start all services |
| `make migrate` | Apply database migrations |
| `make lint` | Run all linters |
| `make test` | Run all tests |
| `make health` | Check service health |
| `make eval` | Run agent evaluations |

Run `make help` for the full list.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, React 18, TypeScript, Tailwind CSS, Radix UI, Zustand, next-intl (en, zh-CN) |
| Backend | Python 3.11+, FastAPI, LangGraph, uv |
| Database | PostgreSQL, Redis |
| Storage | Cloudflare R2 (or local) |
| Sandbox | E2B, BoxLite |
| Safety | llm-guard |

## API Overview

| Category | Endpoints |
|----------|-----------|
| Core | `POST /api/v1/query`, `POST /api/v1/query/stream` |
| Conversations | `GET/POST /api/v1/conversations`, `GET /api/v1/conversations/:id` |
| Tasks | `GET/POST /api/v1/tasks`, `GET /api/v1/tasks/:id` |
| Projects | `GET/POST /api/v1/projects`, `GET /api/v1/projects/:id` |
| Files | `POST /api/v1/files/upload`, `GET /api/v1/files/download/:key` |
| Skills | `GET /api/v1/skills`, `GET /api/v1/skills/:id` |
| HITL | `POST /api/v1/hitl/respond/:threadId`, `GET /api/v1/hitl/pending/:threadId` |
| Providers | `GET /api/v1/providers` |
| Health | `GET /api/v1/health` |

## Documentation

- [Agent System Design](docs/Agent-System-Design.md) — Architecture, routing, skills, guardrails, HITL
- [Agent Evaluations](docs/Agent-Evals-Design.md) — Evaluation framework and testing
- [Development Guide](docs/Development.md) — Setup, environment variables, API reference
- [Design Style Guide](docs/design-style-guide.md) — UI components, colors, typography
- [Sandbox Session Management](docs/sandbox-session-management.md) — Sandbox lifecycle, snapshots

## License

MIT
