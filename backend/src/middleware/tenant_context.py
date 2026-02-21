"""
QUALISYS — Tenant Context Middleware
Story: 1-2-organization-creation-setup, 1-5-login-session-management
AC: AC8 — middleware extracts tenant from JWT (1.2)
AC: AC8 — sets PostgreSQL search_path via ContextVar (immutable per request) (1.2)
AC: AC3 — reads access_token from httpOnly cookie (1.5)

Per architecture.md §ADR-001 / §Security-Threat-Model:
  ContextVar prevents RLS race condition because:
    - Set ONCE per request in middleware
    - Cannot be changed after set (token is stored)
    - Each asyncio Task has its own ContextVar copy (no cross-request leakage)

NOTE: search_path SET LOCAL is applied in `get_tenant_db()` (see db.py) which uses
  the ContextVar value when a session is acquired. Story 1.3+ uses get_tenant_db()
  for tenant-scoped queries. Story 1.2 org endpoints use public schema → regular get_db().
"""

from contextvars import ContextVar
from typing import Optional

from fastapi import Request, Response
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.logger import logger

# ---------------------------------------------------------------------------
# ContextVar — current tenant slug (immutable per request)
# AC8: "Tenant context stored in Python ContextVar (immutable per request)"
# ---------------------------------------------------------------------------

#: The slug of the tenant currently serving this request.
#: None = request is not within a tenant context (public endpoints, auth, etc.)
current_tenant_slug: ContextVar[Optional[str]] = ContextVar(
    "current_tenant_slug", default=None
)

#: The user_id of the authenticated user for this request.
#: Set by TenantContextMiddleware after JWT validation.
current_user_id: ContextVar[Optional[str]] = ContextVar(
    "current_user_id", default=None
)


# ---------------------------------------------------------------------------
# Paths that bypass tenant context validation
# ---------------------------------------------------------------------------

_PUBLIC_PATH_PREFIXES = (
    "/api/v1/auth/",
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
)


def _is_public_path(path: str) -> bool:
    return any(path.startswith(p) for p in _PUBLIC_PATH_PREFIXES)


def _extract_token(request: Request) -> Optional[str]:
    """
    Extract JWT from httpOnly cookie (priority) or Authorization: Bearer header.
    Story 1.5: cookie-based auth is primary; Bearer header for backward compat.
    """
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


# ---------------------------------------------------------------------------
# TenantContextMiddleware
# AC8: Extracts tenant from JWT, sets ContextVars (no DB queries)
# ---------------------------------------------------------------------------

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    FastAPI/Starlette middleware that:
      1. Skips public endpoints (auth, health, metrics)
      2. Decodes RS256 JWT to extract user_id and tenant_slug
      3. Sets current_user_id and current_tenant_slug ContextVars

    Token is read from httpOnly cookie first (Story 1.5), then Bearer header.
    tenant_slug is embedded in the JWT claim (set at login time) to avoid
    a DB lookup on every request.

    Membership validation and 403 enforcement is done in require_role()
    (endpoint level) because it needs the org_id path param.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if _is_public_path(request.url.path):
            return await call_next(request)

        token = _extract_token(request)
        if token:
            try:
                from src.services.token_service import token_service
                payload = token_service.validate_access_token(token)
                if payload.get("type") == "access":
                    user_id = payload.get("sub")
                    tenant_slug = payload.get("tenant_slug")
                    if user_id:
                        current_user_id.set(user_id)
                    if tenant_slug:
                        current_tenant_slug.set(tenant_slug)
                        logger.debug(
                            "Tenant context set",
                            user_id=user_id,
                            tenant_slug=tenant_slug,
                            path=request.url.path,
                        )
            except (JWTError, Exception):
                # Invalid/expired token — let endpoint dependency handle 401
                pass

        return await call_next(request)
