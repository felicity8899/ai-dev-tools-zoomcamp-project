# TableNow — Product Specification

## Problem

Small restaurants manage walk-in queues on paper or a whiteboard. Guests
cannot see their position or expected wait; hosts cannot estimate waits;
no-shows silently stall tables that could seat someone else.

## Users

- **Guest** — walks in, joins the waitlist from their phone, watches their
  position and estimated wait.
- **Host** — works the door: seats parties, frees tables, clears no-shows.

## User journeys

1. **Join** — guest submits name + party size (+ optional phone) and
   immediately sees their position and estimated wait.
2. **Seat** — host seats a waiting party at a free table that fits it; the
   queue advances and all estimates update in real time.
3. **Leave / no-show** — host removes the entry; estimates recompute.

## Functional requirements

- Waitlist entries: name, party size (1–20), optional phone, status
  (`waiting`, `seated`, `no_show`, `left`), join timestamp.
- Tables: name, capacity, status (`free`, `occupied`); CRUD-lite (create,
  update; freeing a table closes out its seated party).
- Position: 1-based, in arrival order among waiting parties.
- Estimated wait: a simulation over the queue ahead — each party takes the
  earliest-freeing table that fits it (smallest fitting capacity on ties);
  seating consumes one average turnover (default 45 min, configurable via
  `AVG_TURNOVER_MINUTES`). A party larger than every table shows
  "no table fits".
- Live updates: any queue/table change is pushed to all connected dashboards
  over WebSocket.
- Persistence: all state in the database (PostgreSQL in compose, SQLite in
  tests/demo) — seating survives restarts.
- Seed data on first boot: 5 tables (2/2/4/4/6 seats), 2 waiting parties.

## Key journey SLO (the alerted one)

Journey: `POST /api/waitlist` (guest joins).

- **Error budget:** < 5% of joins fail (5xx) over any 2-minute window.
- **Latency:** p95 join latency < 2 s over 5 minutes.
- Breach of either pages the responder agent via Prometheus → Alertmanager.

## Acceptance criteria

- [ ] Joining shows the new entry on an open host dashboard within 2 s,
      without a page refresh (WebSocket push).
- [ ] Position and ETA follow the simulation rules above and are unit-tested
      against fixed scenarios (one table, busy table, oversized party,
      big-party/small-table preference).
- [ ] Seating a party persists across a backend restart.
- [ ] The whole system starts locally with one command: `docker compose up`.
- [ ] `make test` runs backend unit + integration tests and the frontend
      module test, all green.
- [ ] Metrics for the join journey are exposed at `/metrics`
      (`tablenow_join_requests_total{result}`, `tablenow_join_latency_seconds`,
      `tablenow_queue_length`), and logs/traces share a `trace_id`.
- [ ] Injecting an error fault (`POST /admin/faults {"error_rate": 1.0}`)
      makes `/admin/health/detail` report `degraded` and joins return 503.
- [ ] On the resulting alert, the responder agent clears the fault and
      verifies recovery (probe join succeeds) with no human input, and writes
      a markdown incident report to `incidents/`.
- [ ] CI runs all tests on push/PR; CD publishes images to GHCR; a rollback
      path (redeploy previous tag) is documented.

## Out of scope

Reservations, SMS notifications, payments, multi-restaurant tenancy,
authentication for the demo admin endpoints.
