PYTHON ?= python3

.PHONY: test run up down obs demo

## Run every test: backend (pytest) + frontend (node:test, if node exists)
test:
	cd backend && $(PYTHON) -m pytest tests -q
	@if command -v node >/dev/null 2>&1; then \
		node --test "frontend/test/*.mjs"; \
	else \
		echo "node not found — skipping frontend tests"; \
	fi

## Run the backend locally on SQLite (no Docker needed)
run:
	cd backend && DATABASE_URL=sqlite:///./tablenow.db \
		$(PYTHON) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

## Full local stack (backend + frontend + PostgreSQL)
up:
	docker compose up --build

down:
	docker compose down

## Full stack plus observability (traces, metrics, alerts, responder agent)
obs:
	docker compose --profile observability up --build

## Build the single-container demo image (HF Spaces)
demo:
	docker build -f Dockerfile.demo -t tablenow-demo .
