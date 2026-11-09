# TableNow — Restaurant Waitlist & Table Manager

A small, complete, production-shaped web app: guests join a restaurant
waitlist and see their position and estimated wait live; hosts seat parties,
mark no-shows, and watch the queue advance in real time. The project is built
end to end — spec, tests, containers, CI/CD, observability, alerting, and an
automated on-call responder agent — for the DataTalksClub **AI Dev Tools
Zoomcamp** final project.

> Provenance: TableNow is a fresh, production-grade implementation written for
> this course. An earlier prototype of the same idea by the same author exists
> at [github.com/felicity8899/restaurant-waitlist-manager](https://github.com/felicity8899/restaurant-waitlist-manager)
> (FastAPI/React); no code was copied from it.

## The problem

Small restaurants manage walk-in queues on paper or a whiteboard: guests
can't see their position, hosts can't estimate waits, and no-shows silently
stall tables. TableNow fixes the three pains with one screen for the host and
one for the guest.

**Users:** guests (join, see position + estimated wait), hosts (seat the next
party, free tables, clear no-shows).

**Core journeys** (these are the ones instrumented and alerted on):

1. Guest joins the waitlist (name, party size, optional phone) → position +
   estimated wait.
2. Host seats a party → table flips to occupied, queue advances, every
   remaining guest's estimate updates live (WebSocket, no refresh).
3. Guest leaves / no-shows → entry removed, estimates recompute.

## Quick start

```bash
docker compose up            # backend + frontend + PostgreSQL 16
# open http://localhost:8080  (API on http://localhost:8000)

docker compose --profile observability up   # + traces/metrics/alerts/agent
make test                    # all tests, no Docker needed
```

Seed data (5 tables, 2 waiting parties) loads automatically on first boot.

No Docker handy? `make run` starts the backend on SQLite; open the API docs
at http://localhost:8000/docs.

## What's inside

| Area | Where |
|---|---|
| Backend (FastAPI, SQLAlchemy — Postgres or SQLite) | `backend/` |
| Frontend (dependency-free SPA, nginx) | `frontend/` |
| Pure domain logic (position + ETA) | `backend/app/waitlist.py` |
| Tests (pytest unit + integration, node:test) | `backend/tests/`, `frontend/test/` |
| Observability (OTEL, Prometheus, Grafana, Jaeger) | `infra/` |
| Alert rules on the join journey | `infra/alerts.yml` |
| Responder (on-call) agent | `agent/` |
| CI/CD (GitHub Actions) | `.github/workflows/` |
| Docs: spec, agent team, architecture, runbook, deployment | `docs/` |

## Observability & the on-call agent

The join journey emits Prometheus metrics (`tablenow_join_requests_total`,
`tablenow_join_latency_seconds`), OTEL traces, and structured JSON logs — all
sharing one `trace_id`. Prometheus alerts on **user impact** (join error rate
> 5%, p95 latency > 2 s), Alertmanager pages the responder agent, and the
agent diagnoses the backend, applies the fix, verifies recovery with a probe
join, and writes an incident report (`incidents/`). Try it: the full chaos
demo is scripted in [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Project criteria map (course grading)

| Criterion | Evidence |
|---|---|
| Problem description | This README |
| Product specification | [docs/SPEC.md](docs/SPEC.md) (+ GitHub Issues mirror the acceptance criteria) |
| Agent team specification | [docs/AGENT_TEAM.md](docs/AGENT_TEAM.md) |
| Context management | [AGENTS.md](AGENTS.md) → modular docs in `docs/` |
| Application | `docker compose up` runs the full stack |
| Testing | `make test` — 23 pytest + 6 node tests |
| Containerization | `backend/Dockerfile`, `frontend/Dockerfile`, `agent/Dockerfile`, `docker-compose.yml` |
| Deployment | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — Hugging Face Spaces, single-container SQLite demo (`Dockerfile.demo`) |
| CI/CD | `.github/workflows/ci.yml` (tests on push/PR), `cd.yml` (GHCR images, manual prod, rollback = redeploy previous tag) |
| Observability | OTEL traces + Prometheus metrics + JSON logs, shared trace_id; Grafana dashboard in `infra/grafana/` |
| Alerting on user impact | `infra/alerts.yml` — join error-rate / latency rules |
| On-call agent | `agent/responder.py` + sample report `incidents/sample-incident-join-error-rate.md` |

Design rationale lives in [docs/DESIGN.md](docs/DESIGN.md).
