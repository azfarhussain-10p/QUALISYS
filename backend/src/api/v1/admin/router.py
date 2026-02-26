"""
QUALISYS — Admin API Router
Story: 1-12-usage-analytics-audit-logs-basic
AC: #1 — GET  /api/v1/admin/analytics         — dashboard metrics (Owner/Admin)
AC: #4,#5 — GET /api/v1/admin/audit-logs      — paginated audit log with filters
AC: #6 — POST /api/v1/admin/audit-logs/export — streaming CSV download
AC: #8 — 400 on invalid filter params; RBAC via require_project_role("owner","admin")

Rate limiting:
  GET  analytics:        No per-endpoint limit (Redis cache keeps DB load low)
  GET  audit-logs:       No per-endpoint limit
  POST audit-logs/export: 5 exports per user per hour

RBAC: Owner/Admin only on all admin endpoints (read via require_project_role).
Tenant isolation: schema_name always derived from JWT-seeded ContextVar.

Security (C1, C2):
  - All SQL params passed as named :params (no f-string interpolation on user data).
  - Date range validated: from ≤ to; max range 366 days.
  - action filter validated against ALLOWED_ACTIONS set.
  - actor_user_id validated as UUID.
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache import get_redis_client
from src.db import get_db
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.analytics_service import analytics_service
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_schema_name() -> Optional[str]:
    """Return validated tenant schema from ContextVar, or None."""
    slug = current_tenant_slug.get()
    if not slug:
        return None
    schema = slug_to_schema_name(slug)
    return schema if validate_safe_identifier(schema) else None


# Atomic Lua script: INCR + conditional EXPIRE in one round-trip.
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


async def _check_export_rate_limit(user_id: uuid.UUID) -> None:
    """5 CSV exports per user per hour (AC6)."""
    redis = get_redis_client()
    key = f"rate:audit_export:{user_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 5:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Export limit reached. Retry after {retry_after} seconds.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


# Allowed action filter values (AC8: invalid action type → 400)
_ALLOWED_ACTIONS: set[str] = {
    "org.created", "org.settings_updated",
    "user.created", "user.invited", "user.invitation_accepted",
    "user.invitation_revoked", "user.role_changed", "user.removed",
    "user.login", "user.password_reset", "user.mfa_enabled",
    "user.mfa_disabled", "user.profile_updated", "user.password_changed",
    "project.created", "project.updated", "project.archived",
    "project.restored", "project.deleted",
    "member.added", "member.removed",
}

# Groupings for the "User Actions", "Project Actions", "Organization Actions" filter values
_ACTION_GROUPS: dict[str, set[str]] = {
    "user_actions": {
        "user.created", "user.invited", "user.invitation_accepted",
        "user.invitation_revoked", "user.role_changed", "user.removed",
        "user.login", "user.password_reset", "user.mfa_enabled",
        "user.mfa_disabled", "user.profile_updated", "user.password_changed",
    },
    "project_actions": {
        "project.created", "project.updated", "project.archived",
        "project.restored", "project.deleted", "member.added", "member.removed",
    },
    "org_actions": {"org.created", "org.settings_updated"},
}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DashboardMetricsResponse(BaseModel):
    active_users: int
    active_projects: int
    test_runs: int
    storage_consumed: str


class AuditLogEntry(BaseModel):
    id: str
    tenant_id: str
    actor_user_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[Any]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedAuditLogsResponse(BaseModel):
    data: list[AuditLogEntry]
    pagination: PaginationMeta


# ---------------------------------------------------------------------------
# GET /api/v1/admin/analytics — AC1
# ---------------------------------------------------------------------------

@router.get(
    "/analytics",
    response_model=DashboardMetricsResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin role required"},
    },
)
async def get_dashboard_metrics(
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> DashboardMetricsResponse:
    """
    Return basic usage metrics for the admin dashboard. AC1.

    - active_users: COUNT of active org members
    - active_projects: COUNT of active projects in tenant schema
    - test_runs: 0 (placeholder — Epic 2-4)
    - storage_consumed: "—" (placeholder — Epic 2)

    Results cached in Redis for 5 minutes to avoid repeated DB queries.
    """
    user, membership = auth
    schema_name = _get_schema_name()

    if not schema_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "TENANT_CONTEXT_MISSING", "message": "Tenant context not set."}},
        )

    metrics = await analytics_service.get_dashboard_metrics(
        schema_name=schema_name,
        tenant_id=membership.tenant_id,
        db=db,
    )
    return DashboardMetricsResponse(**metrics)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/audit-logs — AC4, AC5, AC8
# ---------------------------------------------------------------------------

@router.get(
    "/audit-logs",
    response_model=PaginatedAuditLogsResponse,
    responses={
        400: {"description": "Invalid filter parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin role required"},
    },
)
async def list_audit_logs(
    date_from: Optional[str] = Query(
        default=None,
        description="ISO 8601 date-time, e.g. 2026-01-01T00:00:00Z",
    ),
    date_to: Optional[str] = Query(
        default=None,
        description="ISO 8601 date-time — must be >= date_from",
    ),
    action: Optional[str] = Query(
        default=None,
        description=(
            "Exact action string (e.g., 'project.deleted') or group: "
            "'user_actions', 'project_actions', 'org_actions'"
        ),
    ),
    actor_user_id: Optional[str] = Query(
        default=None,
        description="Filter by actor UUID",
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAuditLogsResponse:
    """
    List audit log entries for the authenticated tenant. AC4, AC5.

    Filters (all optional, combined with AND):
      - date_from / date_to — ISO 8601 date-time range (max 366 days span)
      - action              — exact action string OR group alias
      - actor_user_id       — filter by UUID of the acting user

    Results are returned in reverse chronological order (AC4).
    Pagination default: 50 per page (AC4).
    Active filters should be shown as removable chips in the UI (AC5).
    """
    user, membership = auth
    schema_name = _get_schema_name()

    if not schema_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "TENANT_CONTEXT_MISSING", "message": "Tenant context not set."}},
        )

    # --- Validate date range ---
    dt_from: Optional[datetime] = None
    dt_to: Optional[datetime] = None

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_DATE_FROM", "message": "date_from must be ISO 8601."}},
            )

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_DATE_TO", "message": "date_to must be ISO 8601."}},
            )

    if dt_from and dt_to and dt_from > dt_to:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_DATE_RANGE", "message": "date_from must be before date_to."}},
        )

    if dt_from and dt_to:
        span_days = (dt_to - dt_from).days
        if span_days > 366:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "DATE_RANGE_TOO_LARGE", "message": "Maximum date range is 366 days."}},
            )

    # --- Validate action filter ---
    action_values: Optional[list[str]] = None
    if action:
        if action in _ACTION_GROUPS:
            action_values = list(_ACTION_GROUPS[action])
        elif action in _ALLOWED_ACTIONS:
            action_values = [action]
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_ACTION", "message": f"Unknown action filter: {action!r}."}},
            )

    # --- Validate actor_user_id ---
    actor_uuid: Optional[uuid.UUID] = None
    if actor_user_id:
        try:
            actor_uuid = uuid.UUID(actor_user_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_ACTOR_ID", "message": "actor_user_id must be a valid UUID."}},
            )

    # --- Build query ---
    where_clauses = ["tenant_id = :tenant_id"]
    params: dict = {"tenant_id": str(membership.tenant_id)}

    if dt_from:
        where_clauses.append("created_at >= :date_from")
        params["date_from"] = dt_from.isoformat()

    if dt_to:
        where_clauses.append("created_at <= :date_to")
        params["date_to"] = dt_to.isoformat()

    if action_values:
        placeholders = ", ".join(f":action_{i}" for i in range(len(action_values)))
        where_clauses.append(f"action IN ({placeholders})")
        for i, av in enumerate(action_values):
            params[f"action_{i}"] = av

    if actor_uuid:
        where_clauses.append("actor_user_id = :actor_user_id")
        params["actor_user_id"] = str(actor_uuid)

    where_sql = " AND ".join(where_clauses)
    offset = (page - 1) * per_page

    count_sql = text(
        f'SELECT COUNT(*) FROM "{schema_name}".audit_logs WHERE {where_sql}'
    )
    data_sql = text(
        f'SELECT * FROM "{schema_name}".audit_logs '
        f"WHERE {where_sql} "
        f"ORDER BY created_at DESC "
        f"LIMIT :limit OFFSET :offset"
    )
    params["limit"] = per_page
    params["offset"] = offset

    total_result = await db.execute(count_sql, params)
    total: int = total_result.scalar() or 0

    rows_result = await db.execute(data_sql, params)
    rows = rows_result.mappings().fetchall()

    entries = [
        AuditLogEntry(
            id=str(row["id"]),
            tenant_id=str(row["tenant_id"]),
            actor_user_id=str(row["actor_user_id"]),
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=str(row["resource_id"]) if row.get("resource_id") else None,
            details=row.get("details"),
            ip_address=row.get("ip_address"),
            user_agent=row.get("user_agent"),
            created_at=row["created_at"].isoformat() if row.get("created_at") else "",
        )
        for row in rows
    ]

    total_pages = max(1, -(-total // per_page))  # ceiling division

    return PaginatedAuditLogsResponse(
        data=entries,
        pagination=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/audit-logs/export — AC6
# ---------------------------------------------------------------------------

@router.post(
    "/audit-logs/export",
    responses={
        200: {"content": {"text/csv": {}}, "description": "CSV file download"},
        400: {"description": "Invalid filter parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin role required"},
        429: {"description": "Rate limit exceeded (5 exports/user/hour)"},
    },
)
async def export_audit_logs(
    request: Request,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    actor_user_id: Optional[str] = Query(default=None),
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export audit log entries as CSV. AC6.

    Same filter parameters as GET /audit-logs.
    Returns streaming CSV to avoid loading entire result set into memory.
    Rate-limited: 5 exports per user per hour.

    CSV columns: timestamp, actor_user_id, action, resource_type,
                 resource_id, details, ip_address, user_agent
    """
    user, membership = auth

    # AC6: rate limit — 5 exports per user per hour
    await _check_export_rate_limit(user.id)

    schema_name = _get_schema_name()
    if not schema_name:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "TENANT_CONTEXT_MISSING", "message": "Tenant context not set."}},
        )

    # --- Validate date filters ---
    dt_from: Optional[datetime] = None
    dt_to: Optional[datetime] = None

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_DATE_FROM", "message": "date_from must be ISO 8601."}},
            )

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_DATE_TO", "message": "date_to must be ISO 8601."}},
            )

    if dt_from and dt_to and dt_from > dt_to:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "INVALID_DATE_RANGE", "message": "date_from must be before date_to."}},
        )

    # --- Validate action filter ---
    action_values: Optional[list[str]] = None
    if action:
        if action in _ACTION_GROUPS:
            action_values = list(_ACTION_GROUPS[action])
        elif action in _ALLOWED_ACTIONS:
            action_values = [action]
        else:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_ACTION", "message": f"Unknown action filter: {action!r}."}},
            )

    # --- Validate actor_user_id ---
    actor_uuid: Optional[uuid.UUID] = None
    if actor_user_id:
        try:
            actor_uuid = uuid.UUID(actor_user_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"error": {"code": "INVALID_ACTOR_ID", "message": "actor_user_id must be a valid UUID."}},
            )

    # --- Build query ---
    where_clauses = ["tenant_id = :tenant_id"]
    params: dict = {"tenant_id": str(membership.tenant_id)}

    if dt_from:
        where_clauses.append("created_at >= :date_from")
        params["date_from"] = dt_from.isoformat()
    if dt_to:
        where_clauses.append("created_at <= :date_to")
        params["date_to"] = dt_to.isoformat()
    if action_values:
        placeholders = ", ".join(f":action_{i}" for i in range(len(action_values)))
        where_clauses.append(f"action IN ({placeholders})")
        for i, av in enumerate(action_values):
            params[f"action_{i}"] = av
    if actor_uuid:
        where_clauses.append("actor_user_id = :actor_user_id")
        params["actor_user_id"] = str(actor_uuid)

    where_sql = " AND ".join(where_clauses)

    # Qualify all filter columns with "al." to avoid ambiguity with the JOIN to public.users
    # (public.users also has created_at and other columns).
    _QUALIFY_COLS = ("tenant_id", "created_at", "action", "actor_user_id")
    where_sql_qualified = where_sql
    for _col in _QUALIFY_COLS:
        where_sql_qualified = where_sql_qualified.replace(f"{_col} ", f"al.{_col} ")

    # --- Row count guard: reject exports > 50,000 rows to avoid OOM ---
    _MAX_EXPORT_ROWS = 50_000
    count_sql_export = text(
        f'SELECT COUNT(*) FROM "{schema_name}".audit_logs WHERE {where_sql}'
    )
    count_result = await db.execute(count_sql_export, params)
    total_count: int = count_result.scalar() or 0
    if total_count > _MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail={"error": {
                "code": "EXPORT_TOO_LARGE",
                "message": f"Export exceeds {_MAX_EXPORT_ROWS:,} rows. Reduce date range or add filters.",
            }},
        )

    data_sql = text(
        f'SELECT al.created_at, '
        f'       u.email AS actor_email, '
        f'       COALESCE(u.full_name, u.email) AS actor_name, '
        f'       al.action, al.resource_type, al.resource_id, '
        f'       al.details, al.ip_address, al.user_agent '
        f'FROM "{schema_name}".audit_logs al '
        f'LEFT JOIN public.users u ON al.actor_user_id = u.id '
        f"WHERE {where_sql_qualified} "
        f"ORDER BY al.created_at DESC"
    )

    rows_result = await db.execute(data_sql, params)
    rows = rows_result.mappings().fetchall()

    # --- Stream CSV ---
    def _generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        # Header row (AC6) — includes actor_email and actor_name
        writer.writerow([
            "timestamp", "actor_email", "actor_name", "action", "resource_type",
            "resource_id", "details", "ip_address", "user_agent",
        ])
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        for row in rows:
            writer.writerow([
                row["created_at"].isoformat() if row.get("created_at") else "",
                row.get("actor_email") or "",
                row.get("actor_name") or "",
                row["action"],
                row["resource_type"],
                str(row["resource_id"]) if row.get("resource_id") else "",
                json.dumps(row["details"], default=str) if row.get("details") else "",
                row.get("ip_address") or "",
                row.get("user_agent") or "",
            ])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

    logger.info(
        "Audit log CSV exported",
        tenant_id=str(membership.tenant_id),
        actor=str(user.id),
        rows=len(rows),
    )

    return StreamingResponse(
        _generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-logs.csv"},
    )
