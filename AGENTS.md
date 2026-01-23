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

## Known Issues
- Image agent tasks in the frontend can render text multiple times and fail to render images.

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/feihe/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/feihe/.codex/skills/.system/skill-installer/SKILL.md)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  3) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  4) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
