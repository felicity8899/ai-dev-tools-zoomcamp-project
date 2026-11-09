"""Runtime configuration, all from environment variables.

The single switch that matters most: DATABASE_URL. PostgreSQL in Docker
Compose, SQLite for the test suite and the single-container demo — the same
SQLAlchemy models run on both.
"""
from __future__ import annotations

import os

DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./tablenow.db")

# Average minutes a seated party keeps a table; drives ETA estimation.
AVG_TURNOVER_MINUTES: float = float(os.environ.get("AVG_TURNOVER_MINUTES", "45"))

# Optional directory of static frontend files to serve at "/" (demo mode).
STATIC_DIR: str | None = os.environ.get("STATIC_DIR") or None

# OTLP endpoint for OpenTelemetry traces, e.g. http://otel-collector:4317.
# Empty = tracing disabled (local runs, tests).
OTEL_EXPORTER_OTLP_ENDPOINT: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_SERVICE_NAME: str = os.environ.get("OTEL_SERVICE_NAME", "tablenow-backend")
