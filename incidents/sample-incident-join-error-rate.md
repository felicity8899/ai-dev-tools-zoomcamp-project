# Incident — JoinWaitlistErrorRateHigh

- **Started (UTC):** 2026-11-09T17:03:24.848679+00:00
- **Journey affected:** join waitlist (`POST /api/waitlist`)
- **Backend health at diagnosis:** `{"status": "degraded", "db_ok": true, "websocket_clients": 0, "active_faults": [{"type": "join_error_rate", "error_rate": 1.0}], "journey": "join_waitlist"}`
- **Fix applied by agent:** reset injected fault(s): join_error_rate
- **Recovery verified:** yes — probe join succeeded
- **Responder:** tablenow responder-agent (automated playbook)
