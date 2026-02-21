"""
Structured JSON Logger for QUALISYS
Replaces: api/src/logger/index.ts (TypeScript/Pino) — Sprint Change Proposal 2026-02-20
Story: 0-20 Log Aggregation
AC: 5  - Logs structured in JSON format
AC: 6  - Logs include timestamp, level, message, trace_id, tenant_id
AC: 12 - Cross-service trace correlation via trace_id

Schema matches Pino JSON output for Fluent Bit DaemonSet compatibility (Story 0-20).
PII policy: email addresses masked as u***@***.com via Fluent Bit Lua filter.
Never log raw passwords, tokens, or unmasked emails here.
"""

import logging
import os
import uuid
from contextvars import ContextVar
from typing import Any, Optional

from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# Context variables — per-request state (async-safe)
# ---------------------------------------------------------------------------
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="unknown")
_user_id_var: ContextVar[str] = ContextVar("user_id", default="")


# ---------------------------------------------------------------------------
# Custom JSON formatter — matches Pino schema (AC5, AC6)
# ---------------------------------------------------------------------------
class _QualisysJsonFormatter(jsonlogger.JsonFormatter):
    """Emits JSON log records with Pino-compatible field names."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        # Pino-compatible timestamp field
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Map Python level names to lowercase (matching Pino)
        log_record["level"] = record.levelname.lower()

        # Service metadata
        log_record["service"] = "qualisys-api"
        log_record["environment"] = os.getenv("ENVIRONMENT", "development")

        # Per-request context from ContextVars
        log_record["trace_id"] = _trace_id_var.get() or None
        log_record["tenant_id"] = _tenant_id_var.get() or None
        log_record["user_id"] = _user_id_var.get() or None

        # Remove redundant fields set by python-json-logger
        log_record.pop("color_message", None)


# ---------------------------------------------------------------------------
# Root logger setup
# ---------------------------------------------------------------------------
def _configure_root_logger() -> logging.Logger:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(
        _QualisysJsonFormatter(
            fmt="%(message)s %(levelname)s %(name)s",
            datefmt="%Y-%m-%dT%H:%M:%S.%fZ",
        )
    )

    root = logging.getLogger("qualisys")
    root.setLevel(getattr(logging, log_level, logging.INFO))
    if not root.handlers:
        root.addHandler(handler)
    root.propagate = False
    return root


_root_logger = _configure_root_logger()


# ---------------------------------------------------------------------------
# Logger class — contextual child loggers
# ---------------------------------------------------------------------------
class Logger:
    """
    Per-module/per-request logger with contextual fields.

    Usage:
        logger = get_logger(__name__)
        logger.info("User registered", extra={"user_id": str(user.id)})
    """

    def __init__(self, name: str = "qualisys") -> None:
        self._logger = logging.getLogger(f"qualisys.{name}") if name != "qualisys" else _root_logger

    def set_trace_id(self, trace_id: str) -> None:
        _trace_id_var.set(trace_id)

    def set_tenant_id(self, tenant_id: str) -> None:
        _tenant_id_var.set(tenant_id)

    def set_user_id(self, user_id: str) -> None:
        _user_id_var.set(user_id)

    def debug(self, message: str, **extra: Any) -> None:
        self._logger.debug(message, extra=extra)

    def info(self, message: str, **extra: Any) -> None:
        self._logger.info(message, extra=extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._logger.warning(message, extra=extra)

    def error(self, message: str, exc: Optional[Exception] = None, **extra: Any) -> None:
        if exc:
            extra["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        self._logger.error(message, extra=extra, exc_info=exc is not None)

    def child(self, name: str) -> "Logger":
        return Logger(name)


# Singleton for non-request contexts (startup, background jobs)
logger = Logger()


def get_logger(name: str) -> Logger:
    """Return a named child logger for module-level use."""
    return Logger(name)


# ---------------------------------------------------------------------------
# FastAPI middleware — attaches trace_id + tenant_id, logs requests (AC6, AC12)
# ---------------------------------------------------------------------------
class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Sets trace_id and tenant_id ContextVars for each request.
    Logs HTTP request on response finish with method, path, status, duration.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # AC12: trace_id from X-Request-ID header or generate new UUID
        trace_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        # AC6: tenant_id from auth middleware header (set by TenantMiddleware later)
        tenant_id = request.headers.get("x-tenant-id", "unknown")

        # Set context for this request's lifetime
        _trace_id_var.set(trace_id)
        _tenant_id_var.set(tenant_id)

        # Propagate trace_id downstream
        import time
        start = time.perf_counter()

        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = trace_id

        status_code = response.status_code
        level = "error" if status_code >= 500 else "warning" if status_code >= 400 else "info"

        req_logger = Logger("http")
        log_method = getattr(req_logger, level)
        log_method(
            "HTTP Request",
            method=request.method,
            path=str(request.url.path),
            status=status_code,
            duration_ms=duration_ms,
            user_agent=request.headers.get("user-agent"),
        )

        return response
