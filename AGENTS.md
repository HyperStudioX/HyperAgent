# Repository Guidelines

## Project Structure & Module Organization
- `web/` contains the Next.js 16 frontend (App Router in `web/app/`, UI in `web/components/`, shared helpers in `web/lib/`).
- `api/` contains the FastAPI backend (`api/app/routers/`, `api/app/services/`, `api/app/agents/`, `api/app/models/`).
- `docs/` holds developer and design references; `public/`/`web/public/` store static assets.

## Build, Test, and Development Commands
- Frontend: `cd web && npm run dev` (local dev), `npm run build` (production build), `npm run lint` (ESLint).
- Backend: `cd api && uv run uvicorn app.main:app --reload --port 8080` (API with reload), `uv run pytest` (tests), `uv run ruff check .` (lint).
- Services: `docker-compose up -d postgres redis` for local Postgres/Redis.

## Coding Style & Naming Conventions
- Frontend: TypeScript + React; lint via ESLint (`web/eslint.config.mjs`). Prefer kebab-case filenames (e.g., `message-bubble.tsx`) and PascalCase component names.
- Backend: Python 3.11; lint via Ruff with line length 100 (`api/pyproject.toml`). Use snake_case for modules/functions.
- Keep edits aligned with existing patterns in each folder; avoid introducing new formatting tools.

## Testing Guidelines
- Backend tests use `pytest`; follow `test_*.py` naming (see `api/test_worker.py`).
- No dedicated frontend test runner is configured; add tests only if you introduce a framework and document how to run it.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, etc.) based on recent history.
- PRs should include a concise summary, testing notes (commands + results), and screenshots or clips for UI changes; link related issues if applicable.

## Configuration & Secrets
- Copy `.env` templates: `cp api/.env.example api/.env` and `cp web/.env.example web/.env`, then set provider keys.
- Never commit real API keys or local credentials.
