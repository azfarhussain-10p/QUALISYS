"""
Health Check Endpoints
Replaces: api/src/health.ts (TypeScript/Express) — Sprint Change Proposal 2026-02-20
Story: 0-11 Staging Auto-Deployment
AC: 4 - Readiness + liveness probes
AC: 5 - Rollback on failed health checks (Kubernetes uses probe responses)

/health  - Liveness probe: is the process alive?
/ready   - Readiness probe: is the service ready to accept traffic?

Usage:
    from src.health import router as health_router
    app.include_router(health_router)
"""

from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

# Pluggable dependency check callables — set at app startup via main.py
_check_database: Optional[Callable] = None
_check_redis: Optional[Callable] = None


def register_health_checks(
    check_database: Optional[Callable] = None,
    check_redis: Optional[Callable] = None,
) -> None:
    """Register dependency check callables for the readiness probe."""
    global _check_database, _check_redis
    _check_database = check_database
    _check_redis = check_redis


@router.get("/health")
async def liveness() -> JSONResponse:
    """Liveness probe: returns 200 if the process is running."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get("/ready")
async def readiness() -> JSONResponse:
    """Readiness probe: returns 200 only if all dependencies are reachable."""
    checks: dict[str, str] = {}

    try:
        if _check_database is not None:
            await _check_database()
            checks["database"] = "ok"

        if _check_redis is not None:
            await _check_redis()
            checks["redis"] = "ok"

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
            },
        )

    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
                "error": str(exc),
            },
        )
