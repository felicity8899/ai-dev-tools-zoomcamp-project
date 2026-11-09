# Agent Team Specification

TableNow was built by one human (Xinli Zhang, product owner) directing a team
of AI agents with explicit roles, plus one automated agent that runs in
production (the responder). This document defines the roles, their inputs and
outputs, and the handoff rules — the same discipline the course asks human
teams to show.

## Roles

| Role | Who | Owns | Produces |
|---|---|---|---|
| Product Manager | Human + planning agent | Problem, scope, priorities | `docs/SPEC.md`, acceptance criteria, GitHub Issues |
| Backend Engineer | Coding agent | `backend/` | FastAPI app, domain logic, pytest suite |
| Frontend Engineer | Coding agent | `frontend/` | SPA, `lib/eta.js` + node tests |
| QA Engineer | Reviewing agent (separate session) | Test coverage vs SPEC | Gap list, failing-test reports; `make test` verdict |
| SRE / On-call | Responder agent (in production) + human | `infra/`, `agent/`, incidents | Alert rules, playbooks, incident reports |
| Release Manager | Human | `.github/workflows/` | Deploy approvals (prod is manual), rollback calls |

## Handoffs

- **PM → Engineers:** work starts only from SPEC acceptance criteria; every
  PR description names the criterion it satisfies.
- **Engineers → QA:** handoff = code + `make test` output. QA re-runs tests
  independently and checks criteria one by one; "works on my run" is not
  evidence.
- **Anyone → SRE:** changes to the join journey, metrics names, or `/admin/*`
  endpoints must be flagged — alert rules and the agent playbook depend on
  them (see AGENTS.md hard rules).
- **SRE agent → Human:** the responder agent fixes only known fault
  signatures (injected error/latency faults). Anything else is written up as
  *unresolved* in the incident report for the human on-call; the agent never
  improvises fixes.
- **Release:** CI green is required to merge; prod deploy is a manual,
  human-approved `workflow_dispatch` (see docs/DEPLOYMENT.md).

## Working agreements

- Spec before code; design decisions recorded in `docs/DESIGN.md`.
- Small, verifiable steps: build → test → live-verify → report, in that
  order, with real outputs (test counts, curl transcripts) — never claims
  without a run behind them.
- Docs live with the code and are updated in the same change as the behavior
  they describe.
