"""
QUALISYS — Project API Router
Story: 1-9-project-creation-configuration
ACs: AC1–AC8

Endpoints:
  POST   /api/v1/projects                             — Create project (Owner/Admin) → 201
  GET    /api/v1/projects                             — List projects (all members, paginated)
  GET    /api/v1/projects/{project_id}                — Get project details (all members)
  PATCH  /api/v1/projects/{project_id}                — Update project settings (Owner/Admin)
  GET    /api/v1/projects/{project_id}/settings       — Get project settings including JSONB

Story: 1-11-project-management-archive-delete-list
  GET    /api/v1/projects (extended)                  — Paginated list with status/search/sort
  POST   /api/v1/projects/{project_id}/archive        — Archive project (Owner/Admin) → 200
  POST   /api/v1/projects/{project_id}/restore        — Restore archived project (Owner/Admin) → 200
  DELETE /api/v1/projects/{project_id}                — Hard-delete project (Owner/Admin) → 204

Rate limiting (AC8):
  Create:  10 per org per hour (key: rate:project_create:{tenant_id})
  Update:  30 per project per hour (key: rate:project_update:{project_id})
  Destroy: 10 per org per hour for archive/restore/delete (key: rate:project_destroy:{tenant_id})

RBAC (AC1, AC3):
  Create/Update/Archive/Restore/Delete: Owner/Admin only (require_project_role)
  Read: any active org member (require_project_role with no roles)

Audit (AC8):
  project.created          → async background task
  project.settings_updated → async background task
  project.archived         → async background task (Story 1.11)
  project.restored         → async background task (Story 1.11)
  project.deleted          → synchronous BEFORE deletion (Story 1.11, C3)
"""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from src.api.v1.projects.schemas import (
    CreateProjectRequest,
    PaginatedProjectsResponse,
    PaginationMeta,
    ProjectListItemResponse,
    ProjectResponse,
    ProjectSettingsResponse,
    UpdateProjectRequest,
)


class DeleteProjectRequest(BaseModel):
    confirm_name: str
from src.cache import get_redis_client
from src.db import AsyncSessionLocal, get_db
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.models.tenant import TenantUser
from src.models.user import User
from src.services.project_member_service import project_member_service
from src.services.project_service import (
    DuplicateSlugError,
    InvalidProjectDataError,
    ProjectAlreadyArchivedError,
    ProjectNotArchivedError,
    ProjectNotFoundError,
    ProjectServiceError,
    project_service,
)
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

# Include project members subrouter
from src.api.v1.projects.members import members_router  # noqa: E402
router.include_router(members_router)


# ---------------------------------------------------------------------------
# Rate limiting helpers (AC8)
# ---------------------------------------------------------------------------

# Atomic Lua script: INCR + conditional EXPIRE in one round-trip.
# Prevents permanent key lockout if connection drops after INCR but before EXPIRE.
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


async def _check_project_create_rate_limit(tenant_id: uuid.UUID, request: Request) -> None:
    """10 project creates per org per hour (AC8)."""
    redis = get_redis_client()
    key = f"rate:project_create:{tenant_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 10:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Project creation limit reached. Retry after {retry_after} seconds.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _check_project_update_rate_limit(project_id: uuid.UUID, request: Request) -> None:
    """30 project updates per project per hour (AC8)."""
    redis = get_redis_client()
    key = f"rate:project_update:{project_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 30:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Project update limit reached. Retry after {retry_after} seconds.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _check_project_destroy_rate_limit(tenant_id: uuid.UUID, request: Request) -> None:
    """10 archive/restore/delete operations per org per hour (Story 1.11, AC8, C9)."""
    redis = get_redis_client()
    key = f"rate:project_destroy:{tenant_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 10:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Project operation limit reached. Retry after {retry_after} seconds.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


# ---------------------------------------------------------------------------
# Audit log helper (AC8) — non-blocking background task
# ---------------------------------------------------------------------------

async def _audit_project(
    schema_name: str,
    tenant_id: uuid.UUID,
    action: str,
    actor_user_id: uuid.UUID,
    project_id: uuid.UUID,
    details: dict,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Insert project audit log entry into {tenant_schema}.audit_logs (Story 1.12)."""
    from src.services.audit_service import audit_service as _audit_svc
    await _audit_svc.log_action_async(
        schema_name=schema_name,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type="project",
        resource_id=project_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _get_schema_name() -> Optional[str]:
    """Return validated tenant schema name from ContextVar, or None."""
    slug = current_tenant_slug.get()
    if not slug:
        return None
    schema = slug_to_schema_name(slug)
    return schema if validate_safe_identifier(schema) else None


# ---------------------------------------------------------------------------
# GET /api/v1/projects — list projects (Story 1.11: paginated with status/search/sort)
# ---------------------------------------------------------------------------

from fastapi import Query as _Query


@router.get(
    "",
    response_model=PaginatedProjectsResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not a member of this organization"},
    },
)
async def list_projects(
    status_filter: Optional[str] = _Query(
        default="active",
        alias="status",
        pattern="^(active|archived|all)$",
        description="Filter by project status: active (default), archived, all",
    ),
    search: Optional[str] = _Query(
        default=None,
        max_length=255,
        description="Search by project name (case-insensitive)",
    ),
    sort: Optional[str] = _Query(
        default="created_at",
        pattern="^(name|created_at|status)$",
        description="Sort field: name, created_at (default), status",
    ),
    page: int = _Query(default=1, ge=1, description="Page number (1-based)"),
    per_page: int = _Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    auth: tuple = require_project_role(),  # any active org member
    db: AsyncSession = Depends(get_db),
) -> PaginatedProjectsResponse:
    """
    List projects accessible to the authenticated user. Story 1.11, AC1, AC2.

    - Owner/Admin: all projects in tenant (filtered by status)
    - Other roles: only projects explicitly assigned to them (project_members)
    - Supports search by name, sort, and pagination
    - URL param ?status=active|archived|all (default: active). AC2: filter persisted in URL.
    - Health indicator placeholder '—' for all projects (AC6)
    """
    user, membership = auth

    result = await project_service.list_projects(
        db=db,
        user_id=user.id,
        user_role=membership.role,
        tenant_id=membership.tenant_id,
        status=status_filter or "active",
        search=search,
        sort=sort or "created_at",
        page=page,
        per_page=per_page,
    )

    return PaginatedProjectsResponse(
        data=[ProjectListItemResponse.from_project_with_count(p) for p in result.data],
        pagination=PaginationMeta(
            page=result.page,
            per_page=result.per_page,
            total=result.total,
            total_pages=result.total_pages,
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/projects — AC1, AC2, AC5, AC6, AC7, AC8
# ---------------------------------------------------------------------------

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectResponse,
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        429: {"description": "Rate limit exceeded (10 creates/org/hour)"},
    },
)
async def create_project(
    payload: CreateProjectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Create a new project in the current tenant schema.

    AC1: Owner/Admin only (RBAC enforced via require_project_role).
    AC2: Creates record with auto-generated slug, tenant_id from context.
    AC5: created_by set from authenticated user.
    AC6: Duplicate slug handled with suffix (-1, -2).
    AC7: Server-side validation (name, URL formats).
    AC8: Rate limited 10/org/hour; audit logged.
    """
    user, membership = auth

    # Tenant context
    tenant_id: uuid.UUID = membership.tenant_id

    # AC8: rate limit
    await _check_project_create_rate_limit(tenant_id, request)

    try:
        project = await project_service.create_project(
            name=payload.name,
            description=payload.description,
            app_url=payload.app_url,
            github_repo_url=payload.github_repo_url,
            tenant_id=tenant_id,
            created_by=user.id,
            db=db,
        )
    except ProjectServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROJECT_CREATE_FAILED", "message": str(exc)}},
        ) from exc

    # AC8: audit log (background)
    schema_name = _get_schema_name()
    if schema_name:
        background_tasks.add_task(
            _audit_project,
            schema_name=schema_name,
            tenant_id=tenant_id,
            action="project.created",
            actor_user_id=user.id,
            project_id=project.id,
            details={"name": project.name, "slug": project.slug, "created_by": str(user.id)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id} — all org members
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not a member of this organization"},
        404: {"description": "Project not found"},
    },
)
async def get_project(
    project_id: uuid.UUID,
    auth: tuple = require_project_role(),  # any active member
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Retrieve project details.
    AC3: All authenticated org members can view project details.
    """
    try:
        project = await project_service.get_project(db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc

    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# PATCH /api/v1/projects/{project_id} — Owner/Admin only
# ---------------------------------------------------------------------------

@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        400: {"description": "Validation error"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        404: {"description": "Project not found"},
        429: {"description": "Rate limit exceeded (30 updates/project/hour)"},
    },
)
async def update_project(
    project_id: uuid.UUID,
    payload: UpdateProjectRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Update project settings.
    AC3: name/description/URLs editable (name change triggers slug regeneration).
    AC4: Advanced settings (default_environment, default_browser, tags) via JSONB merge.
    AC8: Rate limited 30/project/hour; audit logged with changed fields.
    """
    user, membership = auth

    # AC8: rate limit
    await _check_project_update_rate_limit(project_id, request)

    # Build updates dict from payload (only include provided fields)
    updates: dict = {}
    data = payload.model_dump(exclude_none=True)
    if "name" in data:
        updates["name"] = data["name"]
    if "description" in data:
        updates["description"] = data.get("description")
    if "app_url" in data:
        updates["app_url"] = data.get("app_url")
    if "github_repo_url" in data:
        updates["github_repo_url"] = data.get("github_repo_url")
    if "settings" in data:
        updates["settings"] = data["settings"]

    if not updates:
        # Nothing to update — return current project
        try:
            project = await project_service.get_project(db, project_id=project_id)
        except ProjectNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
            )
        return ProjectResponse.from_project(project)

    try:
        project = await project_service.update_project(
            project_id=project_id,
            updates=updates,
            db=db,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc
    except ProjectServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROJECT_UPDATE_FAILED", "message": str(exc)}},
        ) from exc

    # AC8: audit log (background)
    schema_name = _get_schema_name()
    if schema_name:
        background_tasks.add_task(
            _audit_project,
            schema_name=schema_name,
            tenant_id=membership.tenant_id,
            action="project.settings_updated",
            actor_user_id=user.id,
            project_id=project.id,
            details={"changed_fields": list(updates.keys())},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/settings — Owner/Admin only
# ---------------------------------------------------------------------------

@router.get(
    "/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        404: {"description": "Project not found"},
    },
)
async def get_project_settings(
    project_id: uuid.UUID,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> ProjectSettingsResponse:
    """
    Retrieve full project settings including advanced JSONB fields.
    AC3, AC4: Returns general + advanced settings for Owner/Admin.
    """
    try:
        project = await project_service.get_project(db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc

    return ProjectSettingsResponse.from_project(project)


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/archive — Story 1.11, AC3, AC7, AC8
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    responses={
        400: {"description": "Project already archived"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        404: {"description": "Project not found"},
        429: {"description": "Rate limit exceeded (10 ops/org/hour)"},
    },
)
async def archive_project(
    project_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Archive (soft-delete) a project. Story 1.11, AC3, AC7, AC8.

    Sets is_active=false and status='archived'. Data fully retained.
    Owner/Admin only. Rate-limited 10/org/hour. Audit logged.
    """
    user, membership = auth
    tenant_id: uuid.UUID = membership.tenant_id

    # AC8: rate limit (10 destructive ops per org per hour)
    await _check_project_destroy_rate_limit(tenant_id, request)

    try:
        project = await project_service.archive_project(project_id=project_id, db=db)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc
    except ProjectAlreadyArchivedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PROJECT_ALREADY_ARCHIVED", "message": str(exc)}},
        ) from exc
    except ProjectServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROJECT_ARCHIVE_FAILED", "message": str(exc)}},
        ) from exc

    # AC8: audit log (background — project still exists)
    schema_name = _get_schema_name()
    if schema_name:
        background_tasks.add_task(
            _audit_project,
            schema_name=schema_name,
            tenant_id=tenant_id,
            action="project.archived",
            actor_user_id=user.id,
            project_id=project.id,
            details={"project_name": project.name, "archived_by": str(user.id)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/restore — Story 1.11, AC4, AC7, AC8
# ---------------------------------------------------------------------------

@router.post(
    "/{project_id}/restore",
    response_model=ProjectResponse,
    responses={
        400: {"description": "Project is not archived"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        404: {"description": "Project not found"},
        429: {"description": "Rate limit exceeded (10 ops/org/hour)"},
    },
)
async def restore_project(
    project_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Restore an archived project. Story 1.11, AC4, AC7, AC8.

    Sets is_active=true and status='active'. All data intact.
    Owner/Admin only. Rate-limited 10/org/hour. Audit logged.
    """
    user, membership = auth
    tenant_id: uuid.UUID = membership.tenant_id

    # AC8: rate limit
    await _check_project_destroy_rate_limit(tenant_id, request)

    try:
        project = await project_service.restore_project(project_id=project_id, db=db)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc
    except ProjectNotArchivedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PROJECT_NOT_ARCHIVED", "message": str(exc)}},
        ) from exc
    except ProjectServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROJECT_RESTORE_FAILED", "message": str(exc)}},
        ) from exc

    # AC8: audit log (background)
    schema_name = _get_schema_name()
    if schema_name:
        background_tasks.add_task(
            _audit_project,
            schema_name=schema_name,
            tenant_id=tenant_id,
            action="project.restored",
            actor_user_id=user.id,
            project_id=project.id,
            details={"project_name": project.name, "restored_by": str(user.id)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    return ProjectResponse.from_project(project)


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id} — Story 1.11, AC5, AC7, AC8
# ---------------------------------------------------------------------------

@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"description": "Project name confirmation mismatch"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role (Owner/Admin required)"},
        404: {"description": "Project not found"},
        429: {"description": "Rate limit exceeded (10 ops/org/hour)"},
    },
)
async def delete_project(
    project_id: uuid.UUID,
    body: DeleteProjectRequest,
    request: Request,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a project. Story 1.11, AC5, AC7, AC8.

    Requires body.confirm_name to exactly match the project's name (server-side).
    Hard-delete with cascade: project_members → test_cases → test_executions → project.
    Audit entry written BEFORE deletion so project_id/name are preserved (C3).
    Owner/Admin only. Rate-limited 10/org/hour.
    """
    user, membership = auth
    tenant_id: uuid.UUID = membership.tenant_id

    # AC8: rate limit
    await _check_project_destroy_rate_limit(tenant_id, request)

    schema_name = _get_schema_name()

    # AC5: server-side name confirmation (prevents accidental deletion via API)
    try:
        project = await project_service.get_project(db, project_id=project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc

    if body.confirm_name != project.name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {
                "code": "CONFIRMATION_MISMATCH",
                "message": "Project name confirmation does not match.",
            }},
        )

    try:
        await project_service.delete_project(
            project_id=project_id,
            db=db,
            # C3: pass audit info so service can log BEFORE deletion
            audit_schema=schema_name,
            audit_tenant_id=tenant_id,
            audit_actor_id=user.id,
            audit_ip=request.client.host if request.client else None,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found."}},
        ) from exc
    except ProjectServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "PROJECT_DELETE_FAILED", "message": str(exc)}},
        ) from exc
