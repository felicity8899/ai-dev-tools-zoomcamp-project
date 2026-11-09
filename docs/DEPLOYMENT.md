# Deployment

Two deployment shapes exist:

1. **Public demo (single container)** — Hugging Face Spaces, SQLite mode.
2. **Image-based deploys** — GHCR images from the CD workflow (dev automatic,
   prod manual), rolled back by redeploying a previous tag.

## 1. Hugging Face Spaces demo (Docker, SQLite)

The demo image (`Dockerfile.demo` at repo root) runs exactly one process:
uvicorn serving both the API and the SPA (the backend mounts `STATIC_DIR` at
`/`, so no nginx is needed) with state in a SQLite file. Same SQLAlchemy
models as the PostgreSQL stack — only `DATABASE_URL` differs.

Create the Space:

1. huggingface.co → **New Space** → SDK: **Docker** → name e.g. `tablenow`.
2. Push this repo to the Space (or add the Space as a git remote and push):
   the Space builds the root `Dockerfile` — so either rename
   `Dockerfile.demo` to `Dockerfile` in the Space repo, or set the Space to
   use it as its Dockerfile. Simplest: in the Space repo, commit
   `Dockerfile.demo` as `Dockerfile` (contents identical).
3. No secrets or env vars are required. Defaults already point at
   `sqlite:////tmp/tablenow.db` with seed data on first boot.
4. The app listens on port **7860** (the Spaces default). The Space is live
   when the build finishes; state resets when the Space restarts (SQLite in
   `/tmp` — acceptable for a demo; use the compose stack for persistence).

Local check of the exact demo image:

```bash
docker build -f Dockerfile.demo -t tablenow-demo .
docker run -p 7860:7860 tablenow-demo
# http://localhost:7860 — SPA + API in one container
```

Verified without Docker too: `STATIC_DIR=<frontend dir> DATABASE_URL=sqlite:////tmp/demo.db uvicorn app.main:app --port 7860` serves the same way.

## 2. GHCR images & environments (CD)

`.github/workflows/cd.yml`:

- **Push to `main`** → build + push `tablenow-backend` and `tablenow-frontend`
  images to GHCR tagged with the commit SHA and `latest` → this is the
  **dev** deploy artifact.
- **Prod** → manual `workflow_dispatch` with an image tag input, running in
  the GitHub `production` environment. Enable **required reviewers** on that
  environment (repo Settings → Environments → production) so a human approves
  every prod deploy. The workflow itself cannot self-approve.
- Targets beyond GHCR publication (a VM, a PaaS) pull the same tags; wire the
  deploy step for your host after the publish step — the image contract
  (ports, env vars) is: backend `:8000` with `DATABASE_URL`; frontend `:80`.

## Rollback

Redeploy the previous known-good tag — full procedure in
[docs/RUNBOOK.md](RUNBOOK.md#rollback). No database migration is involved at
this project's scope (additive schema, create-all on boot).

## Environment variables (backend)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./tablenow.db` | Postgres in compose, SQLite for tests/demo |
| `AVG_TURNOVER_MINUTES` | `45` | ETA simulation turnover |
| `STATIC_DIR` | unset | when set, serve SPA files at `/` (demo mode) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | e.g. `http://otel-collector:4317`; enables tracing |
| `OTEL_SERVICE_NAME` | `tablenow-backend` | service name in Jaeger |
