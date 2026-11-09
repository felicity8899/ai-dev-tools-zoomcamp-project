# Runbook

## Day-2 operations

- **Is it up?** `GET /health` → `{"status":"ok"}`. Deep status:
  `GET /admin/health/detail` (DB reachability, WebSocket clients, active
  faults, overall `ok|degraded`).
- **Is the journey healthy?** Grafana dashboard "TableNow — Join Journey"
  (http://localhost:3000) or Prometheus (http://localhost:9090): join error
  ratio, p95 latency, queue length.
- **Traces:** Jaeger UI (http://localhost:16686), service `tablenow-backend`.
  Any log line's `trace_id` can be pasted into Jaeger to find the request.
- **Logs:** backend stdout is one JSON object per line, always with
  `trace_id`. `docker compose logs backend | grep <trace_id>`.

## Alerts

| Alert | Meaning | First responder |
|---|---|---|
| `JoinWaitlistErrorRateHigh` | > 5% of joins failed for 1 min | Responder agent (automatic) |
| `JoinWaitlistLatencyHigh` | p95 join latency > 2 s for 2 min | Responder agent (automatic) |

The agent's playbook: read `/admin/health/detail` → if a known injected
fault is active, `POST /admin/faults/reset` → probe the journey (real join +
leave) until it succeeds (≤ 120 s) → write `incidents/incident-<time>-<alert>.md`.
If the diagnosis matches no known signature, the report says **unresolved**
and a human takes over — start from the incident report and the trace_id in
the backend logs around the alert time.

## Chaos demo (the on-call agent, end to end)

Requires the observability profile:

```bash
docker compose --profile observability up --build
# 1. Break the join journey:
curl -X POST localhost:8000/admin/faults -H 'Content-Type: application/json' \
     -d '{"error_rate": 1.0}'
# 2. Generate failing joins (or use the guest view at localhost:8080):
curl -X POST localhost:8000/api/waitlist -H 'Content-Type: application/json' \
     -d '{"name":"Demo","party_size":2}'   # -> 503
# 3. Wait ~1-2 min: Prometheus fires JoinWaitlistErrorRateHigh,
#    Alertmanager pages the agent, the agent resets the fault and verifies.
# 4. Confirm recovery + read the report:
curl localhost:8000/admin/health/detail     # -> "status": "ok"
ls incidents/                               # newest incident-*.md
```

Manual reset at any time: `curl -X POST localhost:8000/admin/faults/reset`.
Latency variant: inject `{"latency_ms": 3000}` instead and watch the p95
panel and `JoinWaitlistLatencyHigh`.

## Rollback

Production runs GHCR images tagged with the git SHA (plus `latest`).

1. Find the last good SHA: `git log --oneline` or the GHCR package history.
2. Redeploy that tag (same command the CD prod job runs):
   set the deployment's image to
   `ghcr.io/<owner>/tablenow-backend:<good-sha>` (and `tablenow-frontend`
   likewise), or re-run the CD workflow with that tag via
   `workflow_dispatch`.
3. Verify: `/health` ok, one manual join succeeds, Grafana error ratio back
   to zero.
4. Rollback is complete only when step 3 passes; note the bad SHA in the
   incident report so it is never re-promoted.

Database note: the schema is create-all with additive-only models, so image
rollback does not need a data migration for this project's scope.

## Common issues

- **Joins 503 with no alert:** check `/admin/faults` — a leftover injected
  fault from a demo is the usual cause; reset it.
- **Dashboard not updating:** the SPA reconnects automatically; check the
  connection badge (top right) and that nginx proxies `/ws` (see
  `frontend/nginx.conf`).
- **ETA looks wrong:** ETA is a simulation with a single average turnover
  (`AVG_TURNOVER_MINUTES`, default 45). It is an estimate by design; the
  rules are pinned by unit tests in `backend/tests/unit/test_waitlist.py`.
