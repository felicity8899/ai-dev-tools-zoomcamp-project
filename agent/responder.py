"""TableNow responder (on-call) agent.

Wakes on an Alertmanager webhook, runs a fixed playbook against the backend
admin API, and writes an incident report — no human in the loop for the known
fault signatures:

  1. Diagnose: GET {BACKEND_URL}/admin/health/detail
  2. Identify: read active_faults (injected error-rate / latency signatures)
  3. Fix:      POST {BACKEND_URL}/admin/faults/reset
  4. Verify:   probe the real journey (join -> leave) until it succeeds,
               polling with a timeout
  5. Report:   append a markdown incident report to INCIDENTS_DIR

Unknown problems are reported as "unresolved" for a human instead of being
guessed at.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Request

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
INCIDENTS_DIR = Path(os.environ.get("INCIDENTS_DIR", "incidents"))
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "5"))
VERIFY_TIMEOUT_S = float(os.environ.get("VERIFY_TIMEOUT_S", "120"))

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("responder-agent")


def _log(event: str, **fields) -> None:
    log.info(json.dumps({"event": event, **fields}))


app = FastAPI(title="TableNow Responder Agent")


def diagnose(client: httpx.Client) -> dict:
    resp = client.get(f"{BACKEND_URL}/admin/health/detail")
    resp.raise_for_status()
    return resp.json()


def apply_fix(client: httpx.Client, health: dict) -> str:
    """Map the diagnosed fault signature to its fix. Returns a description."""
    faults = health.get("active_faults", [])
    if faults:
        client.post(f"{BACKEND_URL}/admin/faults/reset").raise_for_status()
        names = ", ".join(f["type"] for f in faults)
        return f"reset injected fault(s): {names}"
    if not health.get("db_ok", True):
        return "none (database unreachable — needs a human)"
    return "none (no known fault signature present)"


def verify_journey(client: httpx.Client) -> bool:
    """Probe the actual user journey: a guest can join (and then leave)."""
    resp = client.post(
        f"{BACKEND_URL}/api/waitlist",
        json={"name": "__responder_probe__", "party_size": 2},
    )
    if resp.status_code != 201:
        return False
    entry_id = resp.json()["id"]
    client.post(f"{BACKEND_URL}/api/waitlist/{entry_id}/left")
    return True


def run_playbook(alert: dict) -> None:
    started = datetime.now(timezone.utc)
    alert_name = alert.get("labels", {}).get("alertname", "unknown")
    _log("playbook_started", alert=alert_name)
    fix_applied = "not attempted"
    recovered = False
    detail: dict = {}
    try:
        # trust_env=False: an internal service client must not route through
        # HTTP(S)_PROXY env vars (breaks localhost / cluster-internal calls).
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            detail = diagnose(client)
            _log("diagnosed", status=detail.get("status"), faults=detail.get("active_faults"))
            fix_applied = apply_fix(client, detail)
            _log("fix_applied", fix=fix_applied)
            deadline = time.monotonic() + VERIFY_TIMEOUT_S
            while time.monotonic() < deadline:
                if verify_journey(client):
                    recovered = True
                    break
                time.sleep(POLL_INTERVAL_S)
    except Exception as exc:  # keep the report truthful even on agent errors
        fix_applied = f"agent error: {exc!r}"
    _log("playbook_finished", alert=alert_name, recovered=recovered)
    write_report(alert_name, started, detail, fix_applied, recovered)


def write_report(alert_name, started, detail, fix_applied, recovered) -> Path:
    INCIDENTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    path = INCIDENTS_DIR / f"incident-{stamp}-{alert_name}.md"
    path.write_text(
        f"# Incident — {alert_name}\n\n"
        f"- **Started (UTC):** {started.isoformat()}\n"
        f"- **Journey affected:** join waitlist (`POST /api/waitlist`)\n"
        f"- **Backend health at diagnosis:** `{json.dumps(detail)}`\n"
        f"- **Fix applied by agent:** {fix_applied}\n"
        f"- **Recovery verified:** {'yes — probe join succeeded' if recovered else 'NO — unresolved, human follow-up required'}\n"
        f"- **Responder:** tablenow responder-agent (automated playbook)\n"
    )
    _log("incident_report_written", path=str(path))
    return path


@app.get("/health")
def health():
    return {"status": "ok", "backend": BACKEND_URL}


@app.post("/alerts")
async def receive_alert(request: Request):
    """Alertmanager webhook receiver. Handles each firing alert in a thread
    so Alertmanager gets a fast 200 and retries don't block the playbook."""
    payload = await request.json()
    for alert in payload.get("alerts", []):
        if alert.get("status") == "firing":
            threading.Thread(target=run_playbook, args=(alert,), daemon=True).start()
            _log("alert_received", alert=alert.get("labels", {}).get("alertname"))
    return {"received": len(payload.get("alerts", []))}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)
