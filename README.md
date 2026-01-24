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

## Architecture Highlights

- **Simplified Hybrid Architecture** - Chat agent handles 80%+ of requests using skills
- **Composable Skills** - Reusable LangGraph subgraphs for focused tasks
- **Specialized Agents** - Complex workflows handled by dedicated agents
- **Event Streaming** - Real-time SSE streaming for all operations
- **Multi-Provider** - Supports Anthropic Claude, OpenAI GPT-4, Google Gemini

## Key Features

- ✅ Streaming responses with real-time updates
- ✅ Multi-provider LLM support (Anthropic, OpenAI, Google)
- ✅ Composable skills system for extensibility
- ✅ File attachments with vision support
- ✅ Browser automation with E2B Desktop
- ✅ Code execution in secure sandboxes
- ✅ Source tracking and citations
- ✅ Clean, minimal interface
- ✅ Internationalization (English, 中文)

## Documentation

- **[Agent System Design](docs/Agent-System-Design.md)** — Multi-agent system and skills architecture
- **[Development Guide](docs/Development.md)** — Setup, tech stack, and API reference
- **[Design Style Guide](docs/Design-Style-Guide.md)** — UI components, colors, and typography

## Quick Start

### Backend (Python/FastAPI)
```bash
cd api
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
- Redis for caching and rate limiting
- E2B for code execution and browser automation

**Frontend:**
- Next.js 16 (App Router)
- React 18 with TypeScript
- Zustand for state management
- Radix UI + Tailwind CSS

## License

MIT
