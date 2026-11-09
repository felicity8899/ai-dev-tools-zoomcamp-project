# AGENTS.md — TableNow context map

This file is the entry point for any AI agent (or human) working on TableNow.
Read the linked module docs for the area you are touching; they are the
source of truth, this file only routes you.

## What this project is

TableNow: restaurant waitlist & table manager (FastAPI + vanilla-JS SPA +
PostgreSQL/SQLite), built for the DataTalksClub AI Dev Tools Zoomcamp final
project. Full design rationale: [docs/DESIGN.md](docs/DESIGN.md).

## Read before you change…

| You are changing | Read first |
|---|---|
| Product behavior, scope, acceptance criteria | [docs/SPEC.md](docs/SPEC.md) |
| Who does what, handoffs, review rules | [docs/AGENT_TEAM.md](docs/AGENT_TEAM.md) |
| System design, data flow, observability wiring | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Operations: chaos demo, incidents, rollback | [docs/RUNBOOK.md](docs/RUNBOOK.md) |
| Deploying (HF Spaces demo, GHCR images) | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |

## Hard rules

- **Domain logic stays pure.** `backend/app/waitlist.py` has no HTTP/DB/clock
  dependencies; position and ETA changes must keep its unit tests meaningful.
- **Same models on Postgres and SQLite.** No database-specific column types.
- **The join journey is sacred.** It carries the metrics, the alert rules and
  the agent playbook. Don't rename `tablenow_join_*` metrics or the
  `/admin/*` endpoints without updating `infra/` and `agent/` in the same PR.
- **Fault injection only touches the join journey** (`backend/app/faults.py`),
  and admin endpoints are demo-surface, not public API.
- **Frontend has no build step and no dependencies.** Vanilla JS + one
  testable module (`frontend/lib/eta.js`). Keep it that way.
- **Tests before claims.** `make test` must pass before any "done" report.

## Commands

```bash
make test     # pytest (unit + integration) + node:test frontend tests
make run      # backend locally on SQLite, http://localhost:8000
docker compose up                                  # full stack, :8080
docker compose --profile observability up          # + Grafana :3000, Jaeger :16686, Prometheus :9090
```
