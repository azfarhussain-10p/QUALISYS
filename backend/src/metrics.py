"""
Application Metrics — Prometheus Integration
Replaces: api/src/metrics/prometheus.ts (TypeScript/prom-client) — Sprint Change Proposal 2026-02-20
Story: 0-19 Monitoring Infrastructure (Prometheus + Grafana)
AC: 3 - Prometheus scrapes application pod metrics via /metrics endpoint

Uses prometheus-fastapi-instrumentator for automatic HTTP metrics (equivalent to
prom-client metricsMiddleware in the TypeScript version) plus custom QUALISYS
business metrics matching the TypeScript Counter/Histogram/Gauge definitions.

Usage:
    from src.metrics import setup_metrics
    setup_metrics(app)       # Call once at app startup
    # /metrics endpoint is automatically mounted
"""

from typing import Optional

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ---------------------------------------------------------------------------
# Custom QUALISYS metrics — mirrors TypeScript prom-client definitions
# ---------------------------------------------------------------------------

# Total HTTP requests — labelled by method, route, status code
http_requests_total = Counter(
    name="http_requests_total",
    documentation="Total number of HTTP requests",
    labelnames=["method", "route", "status"],
)

# HTTP request duration histogram — standard SLO buckets
http_request_duration_seconds = Histogram(
    name="http_request_duration_seconds",
    documentation="Duration of HTTP requests in seconds",
    labelnames=["method", "route", "status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# In-flight requests gauge
http_requests_in_flight = Gauge(
    name="http_requests_in_flight",
    documentation="Number of HTTP requests currently being processed",
)

# ---------------------------------------------------------------------------
# Epic 1 — Auth business metrics (tech-spec-epic-1.md §6.4)
# ---------------------------------------------------------------------------

auth_login_total = Counter(
    name="auth_login_total",
    documentation="Total login attempts by status",
    labelnames=["status"],  # success | failure | mfa_required
)

org_schema_provision_duration_seconds = Histogram(
    name="org_schema_provision_duration_seconds",
    documentation="Duration of tenant schema provisioning in seconds",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

audit_log_write_total = Counter(
    name="audit_log_write_total",
    documentation="Total audit log writes by action type",
    labelnames=["action"],
)

# ---------------------------------------------------------------------------
# Instrumentator setup
# ---------------------------------------------------------------------------

_instrumentator: Optional[Instrumentator] = None


def setup_metrics(app: FastAPI) -> None:
    """
    Attach prometheus-fastapi-instrumentator to the FastAPI app.

    Mounts /metrics endpoint and instruments all routes automatically.
    Call once at application startup before the first request.
    """
    global _instrumentator

    _instrumentator = (
        Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=True,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health", "/ready"],
            inprogress_name="http_requests_in_flight",
            inprogress_labels=True,
        )
        .instrument(app)
        .expose(app, endpoint="/metrics", include_in_schema=False)
    )
