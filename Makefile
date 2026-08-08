# ============================================================
# Makefile — Reactive Agent
# ============================================================

ifeq ($(OS),Windows_NT)
    PYTHON := .venv\Scripts\python
else
    PYTHON := .venv/bin/python
endif

.DEFAULT_GOAL := help

# ── Setup ────────────────────────────────────────────────────

.PHONY: install
install: ## Create the venv and install dependencies
	uv venv && uv pip install -r requirements.txt
	@test -f .env || cp .env.example .env && echo ".env created — fill in GROQ_API_KEY"

# ── Dev ──────────────────────────────────────────────────────

.PHONY: dev
dev: ## Start PostgreSQL + backend (hot-reload)
	docker compose up -d db
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: stop
stop: ## Stop PostgreSQL
	docker compose down

.PHONY: logs
logs: ## PostgreSQL logs
	docker compose logs -f db

# ── Database ─────────────────────────────────────────────────

.PHONY: db-reset
db-reset: ## ⚠ Reset the database (deletes all data)
	docker compose down -v && docker compose up -d db

.PHONY: db-shell
db-shell: ## psql shell
	docker compose exec db psql -U postgres -d agent_db

.PHONY: db-memory
db-memory: ## Show long-term memory (agent_memory)
	docker compose exec db psql -U postgres -d agent_db \
		-c "SELECT user_id, jsonb_pretty(memory_data), updated_at FROM agent_memory ORDER BY updated_at DESC;"

# ── Quality ──────────────────────────────────────────────────

.PHONY: test
test: ## Run tests
	$(PYTHON) -m pytest tests/ -v

.PHONY: lint
lint: ## Check and format the code
	$(PYTHON) -m ruff check app/ --fix && $(PYTHON) -m ruff format app/

# ── Prod ─────────────────────────────────────────────────────

.PHONY: build
build: ## Build Docker prod image
	docker build --target prod -t react-agent-backend:latest .

# ── Help ─────────────────────────────────────────────────────

.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'