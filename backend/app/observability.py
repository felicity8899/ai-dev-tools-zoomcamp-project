"""Observability wiring: structured JSON logs, Prometheus metrics, OTEL traces.

Logs, metrics and traces all share the OpenTelemetry trace_id so one user
action can be followed across all three (see docs/ARCHITECTURE.md). Tracing is
optional: without OTEL_EXPORTER_OTLP_ENDPOINT the app still runs and logs a
per-request generated trace_id.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from prometheus_client import Counter, Gauge, Histogram

# --- Prometheus metrics -------------------------------------------------------
# The join journey is THE instrumented user journey (alerts are defined on it).
JOIN_REQUESTS = Counter(
    "tablenow_join_requests_total",
    "Waitlist join requests by outcome",
    ["result"],  # success | error
)
JOIN_LATENCY = Histogram(
    "tablenow_join_latency_seconds",
    "Waitlist join request latency in seconds",
    ["result"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)
QUEUE_LENGTH = Gauge("tablenow_queue_length", "Parties currently waiting")


def current_trace_id() -> str:
    """Trace id of the active OTEL span, else a fresh id (keeps logs joinable)."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx and ctx.is_valid:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return uuid.uuid4().hex


class JsonLogFormatter(logging.Formatter):
    """One JSON object per log line, always carrying trace_id."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": getattr(record, "trace_id", None) or current_trace_id(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def setup_tracing(app) -> bool:
    """Instrument FastAPI with OpenTelemetry if configured. Never fatal."""
    from . import config

    if not config.OTEL_EXPORTER_OTLP_ENDPOINT:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": config.OTEL_SERVICE_NAME})
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=config.OTEL_EXPORTER_OTLP_ENDPOINT)
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        return True
    except Exception:  # observability must never take the app down
        get_logger(__name__).exception("OTEL setup failed; continuing without traces")
        return False
