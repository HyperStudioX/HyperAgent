# HyperAgent

AI-powered multi-agent platform with composable skills for chat, research, coding, data analysis, and more.

## What is HyperAgent?

HyperAgent is a **next-generation AI platform** that combines specialized agents with composable skills:

### 🤖 Multi-Agent System

**Chat Agent (Primary)** — Handles most tasks with intelligent skill invocation:
- Natural conversations with advanced LLMs
- AI image generation (Gemini/DALL-E)
- Content writing (emails, articles, documents)
- Code generation and review
- Quick web research
- And much more...

**Research Agent** — Deep research workflows:
- Comprehensive multi-source research
- In-depth analysis and synthesis
- Detailed reports with citations
- Academic-level research papers

**Data Agent** — Data analytics:
- CSV/JSON/Excel processing
- Statistical analysis
- Data visualization and charting
- Trend analysis and insights

**Computer Agent** — Browser automation:
- Visual website interaction
- Form filling and submission
- Automated web scraping
- Screenshot capture

### 🛠️ Skills System

Skills are composable LangGraph subgraphs that agents invoke as tools:

- **`image_generation`** - AI image generation
- **`simple_writing`** - Document/email/article creation
- **`code_generation`** - Generate code snippets
- **`code_review`** - Code analysis for bugs/style/security
- **`web_research`** - Focused research with summarization
- **`data_visualization`** - Generate visualization code

Any agent can invoke any skill, making the system highly composable and extensible.

### 🧠 Context Compression

Intelligent context management for long conversations:

- **LLM-based Summarization** - Older messages summarized to preserve meaning
- **Preserves Recent Context** - Keeps recent messages intact (configurable)
- **Automatic Triggering** - Compresses when token threshold reached
- **Fallback Safety** - Falls back to truncation if compression fails

### 🛡️ Safety Guardrails

Comprehensive safety scanning at multiple integration points:

- **Input Scanning** - Prompt injection and jailbreak detection
- **Output Scanning** - Toxicity, PII, and harmful content filtering
- **Tool Scanning** - URL validation and code safety checks

Powered by `llm-guard` with configurable violation actions (block, warn, log).

### 🧪 Evaluation Framework

Comprehensive testing framework for agent quality:

- **Routing Accuracy** - Validates correct agent selection (≥90% threshold)
- **Tool Selection** - Validates skill/tool usage (≥85% threshold)
- **Response Quality** - LLM-as-judge evaluation (≥0.7 threshold)

Mock LLMs enable deterministic testing. LangSmith integration for tracking.

## Architecture Highlights

- **Simplified Hybrid Architecture** - Chat agent handles 80%+ of requests using skills
- **Composable Skills** - Reusable LangGraph subgraphs for focused tasks
- **Specialized Agents** - Complex workflows handled by dedicated agents
- **Context Compression** - LLM-based summarization for long conversations
- **Safety Guardrails** - Multi-layer protection against harmful inputs/outputs
- **Event Streaming** - Real-time SSE streaming for all operations
- **Multi-Provider** - Supports Anthropic Claude, OpenAI GPT-4, Google Gemini

## Key Features

- ✅ Streaming responses with real-time updates
- ✅ Multi-provider LLM support (Anthropic, OpenAI, Google)
- ✅ Composable skills system for extensibility
- ✅ Context compression for long conversations
- ✅ Safety guardrails (prompt injection, toxicity, PII detection)
- ✅ Agent evaluation framework with mock LLMs
- ✅ File attachments with vision support
- ✅ Browser automation with E2B Desktop
- ✅ Code execution in secure sandboxes
- ✅ Human-in-the-loop for high-risk actions
- ✅ Source tracking and citations
- ✅ Clean, minimal interface
- ✅ Internationalization (English, 中文)

## Documentation

- **[Agent System Design](docs/Agent-System-Design.md)** — Multi-agent system and skills architecture
- **[Agent Evaluations](docs/Agent-Evals-Design.md)** — Evaluation framework and testing
- **[Development Guide](docs/Development.md)** — Setup, tech stack, and API reference
- **[Design Style Guide](docs/Design-Style-Guide.md)** — UI components, colors, and typography

## Quick Start

### Backend (Python/FastAPI)
```bash
cd backend
uv sync                    # Install dependencies
uv run alembic upgrade head # Run migrations
uv run uvicorn app.main:app --reload
```

### Frontend (Next.js)
```bash
cd web
npm install
npm run dev
```

Visit `http://localhost:3000` to start using HyperAgent.

## Tech Stack

**Backend:**
- FastAPI + LangGraph for multi-agent orchestration
- PostgreSQL for persistence
- Redis for caching, rate limiting, and HITL
- E2B for code execution and browser automation
- llm-guard for safety guardrails

**Frontend:**
- Next.js 16 (App Router)
- React 18 with TypeScript
- Zustand for state management
- Radix UI + Tailwind CSS

## License

MIT
