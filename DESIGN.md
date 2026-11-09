# Design — AI Dev Tools Zoomcamp Final Project

Owner: Xinli Zhang. Course: DataTalksClub `ai-dev-tools-zoomcamp`, folder `project/`.
Grading: 12 criteria, 24 points, 10 to pass. Docs in English. ~20h scope, one app end to end.
Hard external requirement: **3 peer reviews of other students' projects** (Xinli does these herself; code cannot substitute).

## 1. What the course demands (from the official project page)

Specify before coding → build frontend + backend + database → unit, frontend and
integration tests → containerize → deploy to a public URL → CI/CD with a rollback
path → instrument a key user journey (metrics + traces + structured logs sharing a
trace ID, viewable in a UI) → an alert on real user impact → an alert trigger → a
responder (on-call) agent that wakes on the alert and fixes the issue.

## 2. The application: **TableNow** — restaurant waitlist & table manager

Why this idea: small, stateful, demo-friendly, and in a domain Xinli already knows
(her Jan–May 2026 personal project was a waitlist/table manager), so she can defend
every design choice in peer review. One app, taken all the way.

**Problem.** Small restaurants manage walk-in queues on paper or a whiteboard:
guests can't see their position, hosts can't estimate waits, no-shows stall tables.

**Core user journeys (the ones we instrument and alert on):**
1. Guest joins the waitlist (name, party size, phone optional) → gets position +
   estimated wait.
2. Host seats the next party → table state flips, queue advances, next guest's
   estimate updates in real time.
3. Guest leaves / no-show → entry removed, estimates recompute.

**Acceptance criteria (excerpt; full list in `docs/SPEC.md`, mirrored as GitHub Issues):**
- Join → entry appears in host dashboard within 2 s (live update, no refresh).
- Estimated wait = f(queue ahead, party-size/table match, avg seating cadence);
  unit-tested against fixed scenarios.
- Seating a party persists across restarts (database, not memory).
- Whole system starts locally with one command (`docker compose up`).
- An injected fault on the join journey (error rate > 5% for 1 min) fires an alert;
  the responder agent clears the fault and verifies recovery without human input.

## 3. Architecture

```
frontend (nginx, vanilla-JS SPA) ──REST + WebSocket──► backend (FastAPI)
                                                            │ SQLAlchemy
                                                            ▼
                                                      PostgreSQL 16
backend ──OTLP──► otel-collector ──► Jaeger (traces) / Prometheus (metrics)
backend ──structured JSON logs (trace_id)──► stdout / Grafana+Loki (compose profile)
Prometheus ──alert rule──► Alertmanager ──webhook──► responder-agent (Python)
responder-agent ──admin API──► backend (diagnose → fix → verify → incident report)
```

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic not required (create-all
  + seed on boot for course scope). Pydantic schemas; domain module `waitlist.py`
  holds pure logic (position, ETA) so it is unit-testable without HTTP/DB.
- **Frontend:** dependency-free JS SPA (no build step → one less failure mode),
  served by nginx which also proxies `/api` and `/ws`. Live updates via WebSocket.
- **Database:** PostgreSQL 16 in compose; SQLite file for the test suite and for
  the single-container public demo.
- **Responder agent:** separate small Python service. Playbook: on alert webhook →
  read backend `/admin/health/detail` → match known fault signatures (injected
  error/latency fault, stale WebSocket broadcaster, DB pool saturation flag) →
  apply the mapped fix via admin API → poll the journey SLO until green →
  append an incident report to `incidents/` and its own structured log.

## 4. Criteria map (target 22–24 / 24)

| Criterion | Max | How we earn it |
|---|---|---|
| Problem description | 2 | README: problem, users, journeys, expected behavior |
| Product specification | 2 | `docs/SPEC.md` + public GitHub Issues with acceptance criteria as the task tracker |
| Agent team specification | 2 | `docs/AGENT_TEAM.md`: roles (PM, backend, frontend, QA, SRE/on-call), handoffs, who does what |
| Context management | 2 | `AGENTS.md` at root pointing to modular docs (spec, team, runbooks, architecture) |
| Application | 2 | Full stack works end to end; one-command local run |
| Testing | 2 | pytest unit (domain logic) + integration (API + DB) + node:test for one frontend module; `make test` runs all |
| Containerization | 2 | Dockerfiles + compose for app + DB (+ observability profile) |
| Deployment | 2 | Public demo on Hugging Face Spaces (Docker, SQLite mode); deploy steps documented |
| CI/CD | 3 | GitHub Actions: tests on every PR; CD auto-deploys dev; manual `workflow_dispatch` deploy to prod; rollback = redeploy previous image tag (documented) |
| Observability | 2 | OTEL traces + Prometheus metrics + JSON logs, all sharing trace_id; Grafana dashboard in compose |
| Alerting on user impact | 1 | Prometheus rule on join-journey error rate / p95 latency (not CPU) |
| On-call agent | 2 | Responder service above; demo: inject fault → alert → agent fixes → incident report |

## 5. Repo layout

```
tablenow/
  README.md  AGENTS.md  Makefile  docker-compose.yml
  backend/   (FastAPI app, domain logic, tests/{unit,integration}, Dockerfile)
  frontend/  (SPA: index.html, app.js, lib/eta.js + test, nginx.conf, Dockerfile)
  agent/     (responder agent, playbooks, Dockerfile)
  infra/     (otel-collector.yaml, prometheus.yml, alerts.yml, alertmanager.yml, grafana/)
  docs/      (SPEC.md, AGENT_TEAM.md, ARCHITECTURE.md, RUNBOOK.md, DEPLOYMENT.md)
  .github/workflows/ (ci.yml, cd.yml)
  incidents/ (agent-written incident reports, git-ignored except samples)
```

## 6. Execution plan

1. Scaffold repo, AGENTS.md, spec + agent-team docs. ✅ design stage
2. Backend: domain logic + API + WebSocket + tests (unit first).
3. Frontend SPA wired to API/WS; frontend module test.
4. Compose: app + DB one-command boot; seed data; smoke test.
5. Observability: OTEL + Prometheus + Grafana dashboard; trace_id in logs.
6. Alerting + fault injection + responder agent; end-to-end chaos demo.
7. CI (tests on PR) + CD (dev auto, prod manual) workflows; rollback doc.
8. Deployment to a public URL (HF Spaces) — needs Xinli's HF account token.
9. Push everything to her GitHub — needs one-time GitHub sign-in (device code,
   done on her own phone/browser; NOT browser takeover).
10. Xinli: create/check GitHub Issues tracker + do 3 peer reviews herself.

## 7. Risks / decisions locked

- No build-step frontend (vanilla JS) — reliability over fashion; criteria don't
  require a framework.
- SQLite in the public demo container, Postgres locally — same SQLAlchemy models.
- Deployment and GitHub push are the only steps blocked on Xinli's accounts;
  everything else is buildable and testable locally first.
