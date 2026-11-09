"""Fault injection state for the chaos demo (see docs/RUNBOOK.md).

Faults affect ONLY the join-waitlist journey, mirroring a real partial outage:
- ``error_rate``: fraction of join requests that fail with HTTP 503 (0.0-1.0).
- ``latency_ms``: artificial delay added to every join request.

State is in-process and process-local on purpose: the responder agent clears
it through the admin API, and a backend restart also clears it.
"""
from __future__ import annotations


class FaultState:
    def __init__(self) -> None:
        self.error_rate: float = 0.0
        self.latency_ms: int = 0

    def set(self, error_rate: float | None = None, latency_ms: int | None = None) -> None:
        if error_rate is not None:
            self.error_rate = min(1.0, max(0.0, float(error_rate)))
        if latency_ms is not None:
            self.latency_ms = max(0, int(latency_ms))

    def reset(self) -> None:
        self.error_rate = 0.0
        self.latency_ms = 0

    def active_faults(self) -> list[dict]:
        faults = []
        if self.error_rate > 0:
            faults.append({"type": "join_error_rate", "error_rate": self.error_rate})
        if self.latency_ms > 0:
            faults.append({"type": "join_latency", "latency_ms": self.latency_ms})
        return faults

    @property
    def healthy(self) -> bool:
        return self.error_rate == 0.0 and self.latency_ms == 0


FAULTS = FaultState()
