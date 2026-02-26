"""
QUALISYS — Project Members API Router
Story: 1-10-project-team-assignment
ACs: #1 (list), #2 (add/bulk), #4 (remove), #7 (validation), #8 (rate limit, audit)

Endpoints (mounted under /api/v1/projects):
  POST   /api/v1/projects/{project_id}/members        — add member (Owner/Admin) → 201
  POST   /api/v1/projects/{project_id}/members/bulk   — bulk add (Owner/Admin) → 201
  GET    /api/v1/projects/{project_id}/members        — list members (project members only)
  DELETE /api/v1/projects/{project_id}/members/{user_id} — remove member (Owner/Admin) → 204

Rate limiting (AC#8): 30 member operations per project per hour
  Key: rate:proj_member:{project_id}

RBAC:
  Add/Remove: require_project_role("owner", "admin")
  List: check_project_access (Owner/Admin OR explicit project member)

Audit (AC#8): All add/remove operations logged to tenant audit_logs.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.project_access import check_project_access
from src.cache import get_redis_client
from src.db import AsyncSessionLocal, get_db
from src.services.project_service import ProjectNotFoundError, project_service
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.notification.notification_service import send_project_assignment_email
from src.services.notification_preferences_service import get_preferences, should_notify
from src.services.project_member_service import (
    AlreadyMemberError,
    MemberNotFoundError,
    ProjectMemberError,
    UserNotInOrgError,
    project_member_service,
)
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier

members_router = APIRouter(tags=["project-members"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AddMemberRequest(BaseModel):
    user_id: uuid.UUID = Field(..., description="UUID of the org member to add to this project")


class AddMembersBulkRequest(BaseModel):
    user_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=50)


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    added_by: Optional[uuid.UUID]
    tenant_id: uuid.UUID
    created_at: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    org_role: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rate limiting — 30 member ops per project per hour (AC#8)
# ---------------------------------------------------------------------------

# Atomic Lua script: INCR + conditional EXPIRE in one round-trip.
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


async def _check_member_rate_limit(project_id: uuid.UUID) -> None:
    """AC#8: 30 member operations per project per hour."""
    redis = get_redis_client()
    key = f"rate:proj_member:{project_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 30:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many member operations. Please try again later.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


# ---------------------------------------------------------------------------
# Audit log helper (AC#8)
# ---------------------------------------------------------------------------

async def _audit_member_op(
    schema_name: str,
    action: str,
    actor_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    details: dict,
    ip_address: Optional[str] = None,
) -> None:
    """Write project member audit event to tenant audit_logs. AC#8."""
    from src.services.audit_service import audit_service as _audit_svc
    await _audit_svc.log_action_async(
        schema_name=schema_name,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action=action,
        resource_type="project_member",
        resource_id=project_id,
        details=details,
        ip_address=ip_address,
    )


def _get_schema_name() -> Optional[str]:
    slug = current_tenant_slug.get()
    if not slug:
        return None
    schema = slug_to_schema_name(slug)
    return schema if validate_safe_identifier(schema) else None


# ---------------------------------------------------------------------------
# Background helper — check preferences and send assignment email (AC#5)
# ---------------------------------------------------------------------------

async def _send_assignment_email_if_enabled(
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    added_by_name: str,
    project_name: str,
    project_slug: str,
) -> None:
    """
    Load user prefs, check email_team_changes, send assignment email. AC#5.
    Runs as a background task — does not block the API response.
    """
    from sqlalchemy import text as _text
    try:
        async with AsyncSessionLocal() as db:
            # Load user
            user_result = await db.execute(
                _text("SELECT email, full_name FROM public.users WHERE id = :user_id"),
                {"user_id": str(user_id)},
            )
            user_row = user_result.mappings().fetchone()
            if not user_row:
                return

            # Check notification preferences (AC#5)
            prefs = await get_preferences(db=db, user_id=user_id)
            if not should_notify(prefs, "team_changes"):
                logger.debug(
                    "Project assignment email skipped (preference disabled)",
                    user_id=str(user_id),
                )
                return

            await send_project_assignment_email(
                recipient_email=user_row["email"],
                full_name=user_row["full_name"] or user_row["email"],
                added_by_name=added_by_name,
                project_name=project_name,
                project_slug=project_slug,
                correlation_id=str(uuid.uuid4()),
            )
    except Exception as exc:
        logger.error(
            "Project assignment email send failed",
            user_id=str(user_id),
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/members — AC#2 (single add)
# ---------------------------------------------------------------------------

@members_router.post(
    "/{project_id}/members",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin required"},
        404: {"description": "Project or user not found"},
        409: {"description": "User already a member"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def add_project_member(
    project_id: uuid.UUID,
    payload: AddMemberRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Add a single user to a project. AC#2, AC#7, AC#8.
    Returns 409 if already a member, 404 if user not in org.
    """
    actor, membership = auth

    await _check_member_rate_limit(project_id)

    try:
        member = await project_member_service.add_member(
            project_id=project_id,
            user_id=payload.user_id,
            added_by=actor.id,
            tenant_id=membership.tenant_id,
            db=db,
        )
    except AlreadyMemberError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_MEMBER", "message": "User is already a member of this project."}},
        )
    except UserNotInOrgError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_IN_ORG", "message": str(exc)}},
        )
    except ProjectMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "MEMBER_ADD_FAILED", "message": str(exc)}},
        )

    # AC#5: send assignment email (respects notification preferences)
    # Load project name/slug for the email before queuing the background task
    try:
        _project = await project_service.get_project(db, project_id=project_id)
        _project_name = _project.name
        _project_slug = _project.slug
    except ProjectNotFoundError:
        _project_name = str(project_id)
        _project_slug = str(project_id)

    background_tasks.add_task(
        _send_assignment_email_if_enabled,
        user_id=payload.user_id,
        project_id=project_id,
        added_by_name=actor.full_name or actor.email,
        project_name=_project_name,
        project_slug=_project_slug,
    )

    # AC#8: audit log
    schema = _get_schema_name()
    if schema:
        background_tasks.add_task(
            _audit_member_op,
            schema_name=schema,
            action="project_member.added",
            actor_id=actor.id,
            tenant_id=membership.tenant_id,
            project_id=project_id,
            details={"user_id": str(payload.user_id), "added_by": str(actor.id)},
            ip_address=request.client.host if request.client else None,
        )

    return member.to_dict()


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/members/bulk — AC#2 (bulk)
# ---------------------------------------------------------------------------

@members_router.post(
    "/{project_id}/members/bulk",
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin required"},
        404: {"description": "User not in org"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def add_project_members_bulk(
    project_id: uuid.UUID,
    payload: AddMembersBulkRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Add multiple users to a project in one request. AC#2.
    Already-members are silently skipped (idempotent).
    """
    actor, membership = auth

    await _check_member_rate_limit(project_id)

    try:
        members = await project_member_service.add_members_bulk(
            project_id=project_id,
            user_ids=payload.user_ids,
            added_by=actor.id,
            tenant_id=membership.tenant_id,
            db=db,
        )
    except UserNotInOrgError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_IN_ORG", "message": str(exc)}},
        )
    except ProjectMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "MEMBER_ADD_FAILED", "message": str(exc)}},
        )

    # AC#5: email notifications for newly added members (background)
    # Load project name/slug for emails
    try:
        _project = await project_service.get_project(db, project_id=project_id)
        _project_name = _project.name
        _project_slug = _project.slug
    except ProjectNotFoundError:
        _project_name = str(project_id)
        _project_slug = str(project_id)

    for m in members:
        background_tasks.add_task(
            _send_assignment_email_if_enabled,
            user_id=m.user_id,
            project_id=project_id,
            added_by_name=actor.full_name or actor.email,
            project_name=_project_name,
            project_slug=_project_slug,
        )

    # AC#8: audit log
    schema = _get_schema_name()
    if schema:
        background_tasks.add_task(
            _audit_member_op,
            schema_name=schema,
            action="project_member.bulk_added",
            actor_id=actor.id,
            tenant_id=membership.tenant_id,
            project_id=project_id,
            details={
                "user_ids": [str(uid) for uid in payload.user_ids],
                "added_count": len(members),
                "added_by": str(actor.id),
            },
            ip_address=request.client.host if request.client else None,
        )

    return {"added": [m.to_dict() for m in members], "count": len(members)}


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/members — AC#1, #3
# ---------------------------------------------------------------------------

@members_router.get(
    "/{project_id}/members",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not a project member or insufficient role"},
    },
)
async def list_project_members(
    project_id: uuid.UUID,
    auth: tuple = Depends(check_project_access),   # Owner/Admin OR explicit member
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List all project members with profile data. AC#1.
    Accessible to Owner/Admin and any explicitly assigned project member.
    """
    _, membership = auth

    members = await project_member_service.list_members(
        project_id=project_id,
        tenant_id=membership.tenant_id,
        db=db,
    )

    return {"members": [m.to_dict() for m in members], "count": len(members)}


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}/members/{user_id} — AC#4
# ---------------------------------------------------------------------------

@members_router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner/Admin required"},
        404: {"description": "Member not found in project"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def remove_project_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_project_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a user from a project. AC#4, AC#8.
    Returns 204 on success. Owner/Admin users retain implicit access even if removed.
    """
    actor, membership = auth

    await _check_member_rate_limit(project_id)

    try:
        await project_member_service.remove_member(
            project_id=project_id,
            user_id=user_id,
            removed_by=actor.id,
            tenant_id=membership.tenant_id,
            db=db,
        )
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "MEMBER_NOT_FOUND", "message": str(exc)}},
        )
    except ProjectMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "MEMBER_REMOVE_FAILED", "message": str(exc)}},
        )

    # AC#8: audit log
    schema = _get_schema_name()
    if schema:
        background_tasks.add_task(
            _audit_member_op,
            schema_name=schema,
            action="project_member.removed",
            actor_id=actor.id,
            tenant_id=membership.tenant_id,
            project_id=project_id,
            details={"user_id": str(user_id), "removed_by": str(actor.id)},
            ip_address=request.client.host if request.client else None,
        )
