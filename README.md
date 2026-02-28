# HyperAgent

> **Experimental** — This project is an exploration of multi-agent architectures, composable skill systems, and tool-calling workflows. It is under active development and not intended for production use. APIs, agent behaviors, and project structure may change without notice.

An experimental multi-agent platform built with LangGraph for exploring AI agent orchestration, composable skills, and multi-provider LLM integration.

## Architecture

### Agents

HyperAgent uses a hybrid architecture with two agents:

- **Task Agent** — General-purpose agent handling most requests via a ReAct loop with tool calling. Supports modes: chat, data analysis, app building, image generation, slide creation, and browser automation.
- **Research Agent** — Multi-step research with search, analysis, synthesis, and report writing. Used only for deep research requiring 10+ sources.

A supervisor routes requests to the appropriate agent based on query intent. The Task agent handles ~80% of requests by invoking skills and tools directly.

### Skills

Skills are composable LangGraph subgraphs invoked as tools via `invoke_skill`:

`image_generation` · `code_generation` · `web_research` · `data_analysis` · `slide_generation` · `app_builder` · `task_planning`

### Tools

Organized by category: search, image, browser automation (7 tools), code execution, file operations, app building, slide generation, skill invocation, and human-in-the-loop (`ask_user`).

### LLM Providers

Three built-in providers (Anthropic, OpenAI, Gemini) plus custom OpenAI-compatible providers (DeepSeek, Kimi, Qwen, MiniMax, Ollama, etc.) with three-tier model routing (MAX/PRO/FLASH) and per-task auto-selection.

Includes `ThinkingAwareChatOpenAI` for providers with reasoning/thinking mode support — captures and replays `reasoning_content` for multi-turn tool-calling conversations.

### Sandbox

Dual sandbox providers for code execution, browser automation, and app hosting:
- **E2B** — Cloud sandboxes (requires API key)
- **BoxLite** — Local Docker-based sandboxes

### Other Systems

- **Context Compression** — LLM-based summarization when conversations exceed token thresholds
- **Safety Guardrails** — Input/output/tool scanning via `llm-guard` (prompt injection, toxicity, PII, unsafe URLs/code)
- **Human-in-the-Loop** — Redis pub/sub interrupts for user approval of high-risk actions
- **Agent Handoff** — Task agent can delegate to Research agent (max 3 handoffs per request)
- **Evaluation Framework** — Routing accuracy, tool selection, and response quality evals with mock LLMs

## Quick Start

### Backend (Python/FastAPI)
```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend (Next.js)
```bash
cd web
npm install
npm run dev
```

Visit `http://localhost:5000` (frontend) with backend at `http://localhost:8080`.

## Tech Stack

**Backend:** FastAPI, LangGraph, PostgreSQL, Redis, E2B/BoxLite sandboxes, llm-guard

**Frontend:** Next.js 16 (App Router), React 18, TypeScript, Zustand, Radix UI, Tailwind CSS, next-intl (en, zh-CN)

## Documentation

- [Agent System Design](docs/Agent-System-Design.md) — Architecture, routing, skills, guardrails, HITL
- [Agent Evaluations](docs/Agent-Evals-Design.md) — Evaluation framework and testing
- [Development Guide](docs/Development.md) — Setup, environment variables, API reference
- [Design Style Guide](docs/Design-Style-Guide.md) — UI components, colors, typography

## License

MIT
