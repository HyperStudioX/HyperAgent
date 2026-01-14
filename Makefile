.PHONY: help install install-web install-api dev dev-web dev-api build build-web lint lint-web lint-api test test-api clean migrate migrate-down migrate-new migrate-status

# Colors
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

help: ## Show this help message
	@echo "$(CYAN)HyperAgent$(RESET) - AI Agent Platform"
	@echo ""
	@echo "$(GREEN)Usage:$(RESET)"
	@echo "  make $(YELLOW)<target>$(RESET)"
	@echo ""
	@echo "$(GREEN)Targets:$(RESET)"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  $(YELLOW)%-15s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# =============================================================================
# Installation
# =============================================================================

install: install-web install-api ## Install all dependencies

install-web: ## Install frontend dependencies
	@echo "$(CYAN)Installing frontend dependencies...$(RESET)"
	cd web && npm install

install-api: ## Install backend dependencies
	@echo "$(CYAN)Installing backend dependencies...$(RESET)"
	cd api && uv sync --all-extras

# =============================================================================
# Development
# =============================================================================

dev: ## Start both frontend and backend (requires tmux or run in separate terminals)
	@echo "$(CYAN)Starting development servers...$(RESET)"
	@echo "$(YELLOW)Run 'make dev-web' and 'make dev-api' in separate terminals$(RESET)"

dev-web: ## Start frontend development server
	@echo "$(CYAN)Starting frontend on http://localhost:5000$(RESET)"
	cd web && npm run dev -- -p 5000

dev-api: ## Start backend development server
	@echo "$(CYAN)Starting backend on http://localhost:8080$(RESET)"
	cd api && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

dev-all: ## Start all services concurrently (frontend, backend, databases)
	@echo "$(CYAN)Starting all services...$(RESET)"
	$(MAKE) db-up
	@sleep 2
	$(MAKE) dev-api &
	$(MAKE) dev-web

# =============================================================================
# Build
# =============================================================================

build: build-web ## Build all projects

build-web: ## Build frontend for production
	@echo "$(CYAN)Building frontend...$(RESET)"
	cd web && npm run build

# =============================================================================
# Linting & Testing
# =============================================================================

lint: lint-web lint-api ## Run all linters

lint-web: ## Lint frontend code
	@echo "$(CYAN)Linting frontend...$(RESET)"
	cd web && npm run lint

lint-api: ## Lint backend code
	@echo "$(CYAN)Linting backend...$(RESET)"
	cd api && uv run ruff check . && uv run ruff format --check .

format-api: ## Format backend code
	@echo "$(CYAN)Formatting backend...$(RESET)"
	cd api && uv run ruff format .

test: test-api ## Run all tests

test-api: ## Run backend tests
	@echo "$(CYAN)Running backend tests...$(RESET)"
	cd api && uv run pytest -v

# =============================================================================
# Migrations
# =============================================================================

migrate: ## Apply all pending database migrations
	@echo "$(CYAN)Applying database migrations...$(RESET)"
	cd api && uv run alembic upgrade head

migrate-down: ## Rollback last database migration
	@echo "$(CYAN)Rolling back last migration...$(RESET)"
	cd api && uv run alembic downgrade -1

migrate-new: ## Create new migration (usage: make migrate-new msg='description')
	@if [ -z "$(msg)" ]; then \
		echo "$(YELLOW)Usage: make migrate-new msg='migration description'$(RESET)"; \
		exit 1; \
	fi
	@echo "$(CYAN)Creating new migration: $(msg)$(RESET)"
	cd api && uv run alembic revision --autogenerate -m "$(msg)"

migrate-status: ## Show current migration status
	@echo "$(CYAN)Migration status:$(RESET)"
	cd api && uv run alembic current
	@echo ""
	@echo "$(CYAN)Migration history:$(RESET)"
	cd api && uv run alembic history

# =============================================================================
# Utilities
# =============================================================================

clean: ## Clean build artifacts and caches
	@echo "$(CYAN)Cleaning build artifacts...$(RESET)"
	rm -rf web/.next
	rm -rf web/node_modules/.cache
	rm -rf api/__pycache__
	rm -rf api/.pytest_cache
	rm -rf api/.ruff_cache
	find api -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

health: ## Check health of all services
	@echo "$(CYAN)Checking service health...$(RESET)"
	@echo -n "Backend API: "
	@curl -s http://localhost:8080/api/v1/health | jq -r '.status' 2>/dev/null || echo "$(YELLOW)Not running$(RESET)"
	@echo -n "Frontend: "
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 2>/dev/null && echo "$(GREEN)Running$(RESET)" || echo "$(YELLOW)Not running$(RESET)"

# Default target
.DEFAULT_GOAL := help
