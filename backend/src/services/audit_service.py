"""
QUALISYS — Audit Service
Story: 1-12-usage-analytics-audit-logs-basic
AC: #3 — AuditService.log_action(), log_user_action(), log_project_action(), log_org_action()
AC: #7 — @audit_action decorator, action catalog, non-blocking pattern

Design:
  - log_action()       — synchronous within an existing DB session (for in-transaction use,
                         e.g., audit BEFORE hard-delete so project data is still available)
  - log_action_async() — opens its own session; fire-and-forget via BackgroundTasks or
                         asyncio.create_task().  MUST NOT fail the main request.
  - Convenience wrappers pre-fill resource_type for common domains.
  - @audit_action decorator auto-logs endpoints that receive `request` and `auth` kwargs.

Column mapping (matches migration 011_create_audit_logs.py):
  id, tenant_id, actor_user_id, action, resource_type, resource_id,
  details (JSONB), ip_address, user_agent, created_at

Security (C1, C2):
  - All queries use SQLAlchemy text() with named :params.
  - schema_name validated by caller (validate_safe_identifier) before passing here.
  - No f-string interpolation on user-supplied data.
"""

import asyncio
import functools
import json
import uuid
from typing import Any, Callable, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------

class AuditService:
    """
    Central audit logging service.

    Provides both synchronous (in-transaction) and asynchronous (background)
    audit log insertion.  Failures are always non-fatal — the audit layer must
    never block or fail the main request path.
    """

    # ------------------------------------------------------------------
    # Core: synchronous insert within an existing session
    # ------------------------------------------------------------------

    async def log_action(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Insert an audit log entry using the provided DB session.

        Use this when the audit MUST happen within an existing transaction
        (e.g., audit before hard-delete so data is still available for logging).
        Failures are caught and logged but never re-raised.

        Args:
            db:             Existing AsyncSession (shared with caller's transaction).
            schema_name:    Tenant schema name, already validated (e.g., 'tenant_acme').
            tenant_id:      Tenant UUID (stored in audit row for visibility).
            actor_user_id:  UUID of the user performing the action.
            action:         Dot-notation action string, e.g., 'project.deleted'.
            resource_type:  Resource domain, e.g., 'project', 'user', 'organization'.
            resource_id:    Optional UUID of the affected resource.
            details:        Optional JSONB dict (old/new values, contextual info).
            ip_address:     Optional IPv4/IPv6 address (max 45 chars).
            user_agent:     Optional HTTP User-Agent string.
        """
        try:
            await db.execute(
                text(
                    f'INSERT INTO "{schema_name}".audit_logs '
                    "(tenant_id, actor_user_id, action, resource_type, resource_id, "
                    " details, ip_address, user_agent) "
                    "VALUES (:tenant_id, :actor_user_id, :action, :resource_type, "
                    "        :resource_id, :details::jsonb, :ip_address, :user_agent)"
                ),
                {
                    "tenant_id": str(tenant_id),
                    "actor_user_id": str(actor_user_id),
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id) if resource_id else None,
                    "details": json.dumps(details or {}, default=str),
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
            )
        except Exception as exc:
            # Non-fatal: log the error but don't propagate (AC3, AC7 — must not fail request)
            logger.error(
                "Audit log write failed (in-transaction)",
                action=action,
                resource_type=resource_type,
                exc=str(exc),
            )

    # ------------------------------------------------------------------
    # Core: non-blocking async (opens own session)
    # ------------------------------------------------------------------

    async def log_action_async(
        self,
        schema_name: str,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Non-blocking audit log insert.  Opens its own DB session and commits.

        Designed for use as a BackgroundTasks callback or asyncio.create_task target.
        Any exception is caught and logged; the audit failure MUST NOT propagate to
        the caller (AC3: audit logging must not slow down the main request).

        Args: same as log_action() except no `db` (opens its own session).
        """
        from src.db import AsyncSessionLocal
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    text(
                        f'INSERT INTO "{schema_name}".audit_logs '
                        "(tenant_id, actor_user_id, action, resource_type, resource_id, "
                        " details, ip_address, user_agent) "
                        "VALUES (:tenant_id, :actor_user_id, :action, :resource_type, "
                        "        :resource_id, :details::jsonb, :ip_address, :user_agent)"
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "actor_user_id": str(actor_user_id),
                        "action": action,
                        "resource_type": resource_type,
                        "resource_id": str(resource_id) if resource_id else None,
                        "details": json.dumps(details or {}, default=str),
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                    },
                )
                await db.commit()
        except Exception as exc:
            logger.error(
                "Audit log write failed (async background)",
                action=action,
                resource_type=resource_type,
                exc=str(exc),
            )

    # ------------------------------------------------------------------
    # Convenience: domain-scoped wrappers (pre-fill resource_type)
    # ------------------------------------------------------------------

    async def log_project_action(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Convenience wrapper — resource_type='project'."""
        await self.log_action(
            db=db,
            schema_name=schema_name,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="project",
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_user_action(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Convenience wrapper — resource_type='user'."""
        await self.log_action(
            db=db,
            schema_name=schema_name,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="user",
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_org_action(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        action: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Convenience wrapper — resource_type='organization'."""
        await self.log_action(
            db=db,
            schema_name=schema_name,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="organization",
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )


# ---------------------------------------------------------------------------
# @audit_action decorator
# AC: #7 — auto-logging decorator for FastAPI endpoint functions
# ---------------------------------------------------------------------------

def audit_action(action: str, resource_type: str, resource_id_attr: Optional[str] = None) -> Callable:
    """
    Endpoint decorator: automatically logs an audit entry after the endpoint
    handler returns successfully.

    Requires the decorated endpoint to accept:
      - `request: Request`  — used for IP address and User-Agent
      - `auth: tuple`       — (User, TenantUser) from require_project_role()

    Args:
        action:           Dot-notation action string, e.g. 'project.created'.
        resource_type:    Resource domain, e.g. 'project', 'user'.
        resource_id_attr: Optional kwarg name whose value is the resource UUID,
                          OR name of an attribute on the return value.
                          Falls back to `result.id` if the handler returns an
                          object with an `id` attribute.

    Usage:
        @router.post("/some-endpoint")
        @audit_action('resource.verb', 'resource', resource_id_attr='project_id')
        async def my_endpoint(project_id: uuid.UUID, request: Request, auth: tuple = ...):
            ...

    If audit logging fails the exception is suppressed — the main response
    is never affected (AC3, AC7).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            # Fire-and-forget audit after successful response
            try:
                from fastapi import Request as _Request
                from src.middleware.tenant_context import current_tenant_slug
                from src.services.tenant_provisioning import (
                    slug_to_schema_name,
                    validate_safe_identifier,
                )

                request: Optional[_Request] = kwargs.get("request")
                auth = kwargs.get("auth")

                if request is not None and auth is not None:
                    user, membership = auth
                    slug = current_tenant_slug.get()
                    if slug:
                        schema = slug_to_schema_name(slug)
                        if validate_safe_identifier(schema):
                            # Resolve resource_id from kwarg or result
                            resource_id = None
                            if resource_id_attr:
                                raw = kwargs.get(resource_id_attr)
                                if raw is not None:
                                    resource_id = getattr(raw, "id", None) or raw
                            if resource_id is None and result is not None and hasattr(result, "id"):
                                resource_id = result.id

                            asyncio.create_task(
                                audit_service.log_action_async(
                                    schema_name=schema,
                                    tenant_id=membership.tenant_id,
                                    actor_user_id=user.id,
                                    action=action,
                                    resource_type=resource_type,
                                    resource_id=resource_id,
                                    ip_address=(
                                        request.client.host if request.client else None
                                    ),
                                    user_agent=request.headers.get("user-agent"),
                                )
                            )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "@audit_action decorator failed (non-fatal)",
                    action=action,
                    exc=str(exc),
                )

            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

audit_service = AuditService()


# ---------------------------------------------------------------------------
# Audit Action Catalog
# AC: #7 — standardised action names used across all Epic 1 stories
# ---------------------------------------------------------------------------
#
# Format: {resource_type}.{verb}
#
# | Action                    | resource_type  | Source Story |
# |---------------------------|----------------|--------------|
# | org.created               | organization   | 1.2          |
# | org.settings_updated      | organization   | 1.2          |
# | user.created              | user           | 1.1          |
# | user.invited              | invitation     | 1.3          |
# | user.invitation_accepted  | invitation     | 1.3          |
# | user.invitation_revoked   | invitation     | 1.3          |
# | user.role_changed         | user           | 1.4          |
# | user.removed              | user           | 1.4          |
# | user.login                | session        | 1.5          |
# | user.password_reset       | user           | 1.6          |
# | user.mfa_enabled          | user           | 1.7          |
# | user.mfa_disabled         | user           | 1.7          |
# | user.profile_updated      | user           | 1.8          |
# | user.password_changed     | user           | 1.8          |
# | project.created           | project        | 1.9          |
# | project.updated           | project        | 1.9          |
# | project.archived          | project        | 1.11         |
# | project.restored          | project        | 1.11         |
# | project.deleted           | project        | 1.11         |
# | member.added              | project_member | 1.10         |
# | member.removed            | project_member | 1.10         |
