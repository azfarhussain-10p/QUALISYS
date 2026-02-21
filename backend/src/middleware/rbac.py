"""
QUALISYS — RBAC FastAPI Dependencies
Story: 1-2-organization-creation-setup, 1-5-login-session-management
AC: AC5 — @require_role('owner', 'admin') enforced on org settings endpoints (1.2)
AC: AC8 — role validation via public.tenants_users membership lookup (1.2)
AC: AC9 — RBAC on all org creation and settings endpoints (1.2)
AC: AC3 — get_current_user reads access_token cookie first, then Bearer header (1.5)

Usage in endpoint:
    @router.get("/settings")
    async def get_settings(
        org_id: uuid.UUID,
        user_and_role: tuple[User, TenantUser] = Depends(require_role("owner", "admin")),
        db: AsyncSession = Depends(get_db),
    ):
        user, membership = user_and_role
        ...

Per tech-spec-epic-1.md §6.2:
  RBAC: FastAPI Depends(require_role(...)) on all protected endpoints
  6 roles: owner, admin, pm-csm, qa-manual, qa-automation, developer, viewer
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.logger import logger
from src.models.user import User
from src.models.tenant import Tenant, TenantUser
from src.services.token_service import token_service

_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    """
    Extract JWT access token from httpOnly cookie first, then Authorization: Bearer header.
    Cookie takes precedence (Story 1.5 AC3 — cookie-based auth).
    Bearer header retained for backward compatibility (service-to-service, tests).
    """
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token
    if credentials:
        return credentials.credentials
    return None


# ---------------------------------------------------------------------------
# get_current_user dependency — decodes RS256 JWT, loads User from DB
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: decode RS256 JWT and return authenticated User.

    Token source priority:
      1. access_token httpOnly cookie (Story 1.5)
      2. Authorization: Bearer <token> header (backward compat)

    Raises 401 if token missing, invalid, or expired.
    """
    token = _extract_token(request, credentials)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NOT_AUTHENTICATED", "message": "Authentication required."}},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = token_service.validate_access_token(token)
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise JWTError("Missing sub claim")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token."}},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
        )
    return user


# ---------------------------------------------------------------------------
# require_role factory — validates tenant membership + role
# AC8: "Middleware validates tenant exists and user has membership"
# ---------------------------------------------------------------------------

def require_role(*allowed_roles: str):
    """
    Dependency factory: validates the authenticated user has one of `allowed_roles`
    in the tenant identified by the `org_id` path parameter.

    Returns (User, TenantUser) tuple for use in the endpoint.
    Raises 403 if user lacks the required role.

    Example:
        @router.patch("/{org_id}/settings")
        async def patch_settings(
            org_id: uuid.UUID,
            auth: tuple = Depends(require_role("owner", "admin")),
        ):
            user, membership = auth
    """
    async def _check_role(
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[User, TenantUser]:
        # Verify tenant exists
        result = await db.execute(select(Tenant).where(Tenant.id == org_id))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
            )

        # Verify membership + role (AC8)
        # AC5 (Story 1.4): also check is_active=true — removed members are denied
        result = await db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == org_id,
                TenantUser.user_id == current_user.id,
            )
        )
        membership = result.scalar_one_or_none()

        if membership is None or not membership.is_active:
            logger.warning(
                "RBAC: user not an active member of tenant",
                user_id=str(current_user.id),
                tenant_id=str(org_id),
                is_removed=membership is not None and not membership.is_active,
            )
            if membership is not None and not membership.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": {
                            "code": "ACCESS_REVOKED",
                            "message": "You no longer have access to this organization.",
                        }
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "You do not have access to this organization.",
                    }
                },
            )

        if membership.role not in allowed_roles:
            logger.warning(
                "RBAC: insufficient role",
                user_id=str(current_user.id),
                tenant_id=str(org_id),
                user_role=membership.role,
                required_roles=list(allowed_roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "INSUFFICIENT_ROLE",
                        "message": f"This action requires one of: {', '.join(allowed_roles)}.",
                    }
                },
            )

        return current_user, membership

    return Depends(_check_role)
