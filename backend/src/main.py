"""
QUALISYS API — FastAPI Application Entry Point
Sprint Change Proposal 2026-02-20: Python/FastAPI scaffold replacing TypeScript/Express

Story: Epic 1 Foundation & Administration
Tech Spec: docs/tech-specs/tech-spec-epic-1.md
"""

import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.health import register_health_checks, router as health_router
from src.logger import LoggingMiddleware, logger
from src.metrics import setup_metrics
from src.middleware.tenant_context import TenantContextMiddleware

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="QUALISYS API",
    description="AI-Powered Testing Platform — Backend API",
    version="0.1.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT", "development") != "production" else None,
    redoc_url=None,
)

# ---------------------------------------------------------------------------
# Middleware (order matters: outermost → innermost)
# ---------------------------------------------------------------------------

# CORS — frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured JSON request logging + trace_id propagation
app.add_middleware(LoggingMiddleware)

# Tenant context — extracts user_id from JWT, sets ContextVar (Story 1.2 AC8)
app.add_middleware(TenantContextMiddleware)

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

setup_metrics(app)

# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convert 422 Pydantic validation errors to AC8 structured error format.

    AC8 requires all error responses to use {error: {code, message}}.
    FastAPI's default 422 handler returns {detail: [...]} — this overrides it.
    """
    errors = exc.errors()
    if errors:
        first = errors[0]
        loc_parts = [str(p) for p in first.get("loc", []) if p != "body"]
        field = " → ".join(loc_parts) if loc_parts else ""
        msg = first.get("msg", "Validation error")
        message = f"{field}: {msg}" if field else msg
    else:
        message = "Request validation failed"

    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": message}},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router)

# Story 1.1 — Auth (register, Google OAuth, email verification)
from src.api.v1.auth.router import router as auth_router  # noqa: E402
app.include_router(auth_router)

# Story 1.7 — MFA (TOTP setup, verify, backup codes, disable, regenerate, status)
from src.api.v1.auth.mfa_router import mfa_router  # noqa: E402
app.include_router(mfa_router)

# Story 1.2 — Org management (create, settings, logo upload)
from src.api.v1.orgs.router import router as org_router  # noqa: E402
app.include_router(org_router)

# Story 1.3 — Team member invitations (admin + public accept endpoints)
from src.api.v1.invitations.router import router_admin as invitation_admin_router  # noqa: E402
from src.api.v1.invitations.router import router_public as invitation_public_router  # noqa: E402
app.include_router(invitation_admin_router)
app.include_router(invitation_public_router)

# Story 1.4 — Member management (list, change role, remove)
from src.api.v1.members.router import router as members_router  # noqa: E402
app.include_router(members_router)

# Story 1.8 — User profile, avatar, notifications, change-password
from src.api.v1.users.router import router as users_router  # noqa: E402
app.include_router(users_router)

# Story 1.9 — Project creation & configuration
from src.api.v1.projects.router import router as projects_router  # noqa: E402
app.include_router(projects_router)

# Story 1.12 — Admin analytics + audit log viewer
from src.api.v1.admin.router import router as admin_router  # noqa: E402
app.include_router(admin_router)

# Story 1.13 — Data export & org deletion
from src.api.v1.orgs.export_router import router as export_deletion_router  # noqa: E402
app.include_router(export_deletion_router)

# Story 2.1 — Document upload, parsing
from src.api.v1.documents.router import router as documents_router  # noqa: E402
app.include_router(documents_router)

# Story 2.3 — GitHub repository connection
from src.api.v1.github.router import router as github_router  # noqa: E402
app.include_router(github_router)

# Story 2.5 — Application DOM crawling
from src.api.v1.crawls.router import router as crawls_router  # noqa: E402
app.include_router(crawls_router)

# Story 2.6 — AI agent selection (catalog + project-scoped runs)
from src.api.v1.agent_runs.router import agents_catalog_router, router as agent_runs_router  # noqa: E402
app.include_router(agents_catalog_router)
app.include_router(agent_runs_router)

# Story 2.9 — Real-time agent progress tracking (SSE endpoint)
from src.api.v1.events.router import router as events_router  # noqa: E402
app.include_router(events_router)

# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("QUALISYS API starting", environment=os.getenv("ENVIRONMENT", "development"))

    # Wire health checks (Story 1.1 — DB + Redis now available)
    from src.db import check_database
    from src.cache import check_redis
    register_health_checks(check_database=check_database, check_redis=check_redis)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("QUALISYS API shutting down")
