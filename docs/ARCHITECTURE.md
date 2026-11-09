# Architecture

## System diagram

```
frontend (nginx, vanilla-JS SPA) ──REST + WebSocket──► backend (FastAPI)
                                                            │ SQLAlchemy
                                                            ▼
                                                      PostgreSQL 16
backend ──OTLP──► otel-collector ──► Jaeger (traces)
backend ──/metrics──► Prometheus ──alert rules──► Alertmanager
backend ──structured JSON logs (trace_id)──► stdout ──► Grafana (dashboards)
Alertmanager ──webhook──► responder-agent ──admin API──► backend
```

## Components

**Backend** (`backend/`, Python 3.12, FastAPI)
- `app/waitlist.py` — pure domain logic: position + ETA simulation. No I/O,
  fully unit-tested.
- `app/models.py` / `app/database.py` — SQLAlchemy 2 models that run
  unchanged on PostgreSQL 16 and SQLite (the `DATABASE_URL` env var is the
  only switch). Create-all + seed on boot (course scope; no Alembic).
- `app/main.py` — REST API (`/api/waitlist`, `/api/tables`), WebSocket `/ws`
  broadcasting a full queue snapshot after every mutation, `/health`,
  `/metrics`, and the `/admin/*` surface (health detail, fault injection).
- `app/faults.py` — in-process fault state for the chaos demo. Faults touch
  only the join journey.
- `app/observability.py` — JSON log formatter (every line carries
  `trace_id`), Prometheus metrics for the join journey, optional OTEL
  instrumentation (enabled when `OTEL_EXPORTER_OTLP_ENDPOINT` is set).

**Frontend** (`frontend/`) — dependency-free SPA, no build step. nginx serves
the static files and proxies `/api` and `/ws` to the backend. Host dashboard
(queue + tables, seat / no-show / left actions) and a guest join view.
`lib/eta.js` is the one shared, unit-tested module (ETA formatting).

**Responder agent** (`agent/`) — small FastAPI service. Alertmanager posts
firing alerts to `/alerts`; the playbook (diagnose → fix → verify → report)
runs in a thread and writes a markdown incident report to `incidents/`.
Backend calls use `trust_env=False` so sandbox/cluster proxies can't hijack
internal traffic.

**Observability stack** (`infra/`, compose profile `observability`)
- OTEL Collector receives OTLP traces, forwards to Jaeger.
- Prometheus scrapes the backend's `/metrics`; alert rules live in
  `infra/alerts.yml` and target *user impact* on the join journey (error
  ratio, p95 latency), never host CPU.
- Alertmanager routes pages to the agent webhook.
- Grafana is pre-provisioned (datasources + the "TableNow — Join Journey"
  dashboard: join rate by result, error ratio, latency p50/p95, queue gauge).

## Data flow of the key journey (guest joins)

1. `POST /api/waitlist` → row inserted → position/ETA computed by the pure
   domain module against current tables (`free_at` = turnover − elapsed for
   occupied tables).
2. Join counter + latency histogram recorded with `result=success|error`;
   log line emitted with the request's `trace_id`.
3. New queue snapshot broadcast over `/ws`; every open dashboard re-renders
   within milliseconds — well inside the 2 s acceptance bound.
4. Prometheus evaluates the error-ratio rule continuously; a sustained
   breach (> 5% for 1 min) fires `JoinWaitlistErrorRateHigh` →
   Alertmanager → agent webhook → playbook → incident report.

## Modes

| Mode | Command | DB | Notes |
|---|---|---|---|
| Local dev | `make run` | SQLite file | backend only, API docs at `/docs` |
| Full stack | `docker compose up` | PostgreSQL 16 | nginx SPA on :8080 |
| Full + observability | `docker compose --profile observability up` | PostgreSQL 16 | + Jaeger :16686, Prometheus :9090, Grafana :3000, Alertmanager :9093, agent :8090 |
| Public demo | `Dockerfile.demo` | SQLite | one container; backend serves the SPA (`STATIC_DIR`) |
