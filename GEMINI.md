# HyperAgent - Gemini Context

## Project Overview
HyperAgent is an AI-powered platform designed for conversational chat and deep research. It features a modern web interface for interacting with advanced language models and a backend capability for conducting multi-step research tasks, synthesizing findings, and generating reports.

## Tech Stack

### Frontend (`web/`)
*   **Framework:** Next.js 14+ (App Router)
*   **Language:** TypeScript
*   **UI Library:** React 18, shadcn/ui, Radix UI primitives
*   **Styling:** Tailwind CSS
*   **State Management:** Zustand (with persistence)
*   **Internationalization:** next-intl

### Backend (`api/`)
*   **Framework:** FastAPI
*   **Language:** Python 3.11+
*   **Agent Framework:** LangGraph
*   **Package Manager:** uv
*   **Database:** PostgreSQL (SQLAlchemy + Alembic)
*   **Queue/Async:** Redis, ARQ
*   **Sandbox:** E2B

## Directory Structure

*   `web/` - Next.js frontend application.
    *   `app/` - App router pages and layouts.
    *   `components/` - React components (UI, Chat, Research).
    *   `lib/` - Utilities, stores (Zustand), and types.
*   `api/` - Python FastAPI backend.
    *   `app/` - Main application code.
        *   `agents/` - LangGraph agent definitions.
        *   `routers/` - API endpoints.
        *   `models/` - Pydantic schemas.
        *   `db/` - Database models and connection logic.
    *   `alembic/` - Database migrations.

## Development Workflow

The project uses a `Makefile` to orchestrate common tasks.

### Installation
*   **All Dependencies:** `make install`
*   **Frontend Only:** `make install-web`
*   **Backend Only:** `make install-api`

### Running Development Servers
*   **Frontend:** `make dev-web` (Runs on port 5000)
*   **Backend:** `make dev-api` (Runs on port 8080)
*   **Worker:** `make dev-worker` (Background task processing)
*   **All Services:** `make dev-all` (Requires separate terminal or background management)

### Database Migrations
*   **Apply Migrations:** `make migrate`
*   **Create Migration:** `make migrate-new msg="description"`

### Testing & Quality
*   **Lint All:** `make lint`
*   **Backend Tests:** `make test-api`
*   **Backend Formatting:** `make format-api`

## Code Conventions

### Frontend
*   **Components:** Functional components with TypeScript.
*   **State:** Use Zustand stores (`chat-store`, `task-store`) for global state. Check for `hasHydrated` before rendering store-dependent UI.
*   **Styling:** Use Tailwind utility classes.
*   **Theme:** Respect the system theme preference (Auto/Light/Dark).
*   **API:** Proxy requests through Next.js API routes (`/api/v1/*`) to avoid CORS issues.

### Backend
*   **Type Hinting:** Strictly use Python type hints.
*   **Async:** Utilize `async/await` for I/O bound operations (DB, API calls).
*   **Dependency Injection:** Use FastAPI's dependency injection system.
*   **Agents:** Define agent workflows using LangGraph nodes and edges.

## Key Configuration
*   **Frontend Env:** `web/.env` (Copy from `web/.env.example`)
*   **Backend Env:** `api/.env` (Copy from `api/.env.example`)
*   **Docker:** `docker-compose.yml` for local PostgreSQL and Redis.
