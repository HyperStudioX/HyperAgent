# HyperAgent

AI Agent Platform for Chat and Deep Research - Built with Next.js, FastAPI, and LangGraph.

## Features

- **AI Chat**: Conversational interface with streaming responses
- **Deep Research**: Multi-step research with source tracking
- **Multi-Provider LLM Support**: Anthropic Claude and OpenAI GPT-4
- **Modern UI**: Dark theme inspired by Cursor and Notion

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React 18, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python 3.11+, FastAPI, LangGraph |
| Database | PostgreSQL, Redis |
| Storage | Cloudflare R2 |
| Sandbox | E2B |

## Quick Start

### Prerequisites

- Node.js 20+
- Python 3.11+
- Docker (optional, for PostgreSQL and Redis)

### 1. Clone and Setup Environment

```bash
cd HyperAgent
cp api/.env.example api/.env
cp web/.env.example web/.env
# Edit api/.env and add your API keys
```

### 2. Start Database Services (Docker)

```bash
docker-compose up -d postgres redis
```

Or run PostgreSQL and Redis locally.

### 3. Start Backend

```bash
cd api
uv sync --all-extras
uv run uvicorn app.main:app --reload --port 8080
```

### 4. Start Frontend

```bash
cd web
npm install
npm run dev -- -p 5000
```

### 5. Open Application

Visit [http://localhost:5000](http://localhost:5000)

## Project Structure

```
HyperAgent/
├── web/                    # Next.js frontend
│   ├── app/               # App router pages
│   ├── components/        # React components
│   │   ├── ui/           # shadcn/ui components
│   │   ├── chat/         # Chat components
│   │   ├── research/     # Research components
│   │   └── layout/       # Layout components
│   └── lib/              # Utilities, stores, types
│
├── api/                    # Python backend
│   ├── app/
│   │   ├── routers/      # API endpoints
│   │   ├── agents/       # LangGraph agents
│   │   ├── services/     # Business logic
│   │   └── models/       # Pydantic schemas
│   └── pyproject.toml
│
├── docker-compose.yml      # Docker services
└── .env.example           # Environment template
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/chat/send` | POST | Send chat message |
| `/api/v1/chat/stream` | POST | Stream chat response |
| `/api/v1/research/start` | POST | Start research task |
| `/api/v1/research/stream/{id}` | GET | Stream research progress |

## Environment Variables

### API (`api/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `ANTHROPIC_API_KEY` | Anthropic API key | Yes* |
| `OPENAI_API_KEY` | OpenAI API key | Yes* |
| `DATABASE_URL` | PostgreSQL connection | No |
| `REDIS_URL` | Redis connection | No |
| `E2B_API_KEY` | E2B sandbox API key | No |
| `CORS_ORIGINS` | Allowed origins | No |

*At least one LLM provider key is required.

### Web (`web/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | No |

## Development

### Frontend Development

```bash
cd web
npm run dev     # Start dev server
npm run build   # Production build
npm run lint    # Run ESLint
```

### Backend Development

```bash
cd api
uv run uvicorn app.main:app --reload --port 8080  # Start with hot reload
uv run pytest                                      # Run tests
uv run ruff check .                               # Lint code
```

## License

MIT
