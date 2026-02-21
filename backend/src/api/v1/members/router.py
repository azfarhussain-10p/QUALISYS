"""
QUALISYS — Member Management API Router
Story: 1-4-user-management-remove-change-roles
ACs: AC1–AC8

Endpoints (all under /api/v1/orgs/{org_id}/members):
  GET    /api/v1/orgs/{org_id}/members                         — list active members (AC1)
  PATCH  /api/v1/orgs/{org_id}/members/{user_id}/role          — change role (AC2)
  DELETE /api/v1/orgs/{org_id}/members/{user_id}               — remove member (AC3)

Rate limiting (AC8):
  30 management operations per org per hour (key: rate:member:{org_id})

RBAC (AC2, AC3):
  GET: any authenticated member of the org
  PATCH/DELETE: Owner/Admin only
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.members.schemas import (
    ChangeRoleRequest,
    MemberResponse,
    PaginatedMembersResponse,
    RemoveMemberResponse,
)
from src.cache import get_redis_client
from src.db import AsyncSessionLocal, get_db
from src.logger import logger
from src.middleware.rbac import get_current_user, require_role
from src.models.tenant import Tenant, TenantUser
from src.models.user import User
from src.services.notification.notification_service import (
    send_role_changed_email,
    send_member_removed_email,
)
from src.services.user_management.user_management_service import (
    InvalidRoleError,
    LastAdminError,
    MemberAlreadyRemovedError,
    MemberNotFoundError,
    SelfActionError,
    UserManagementService,
)

router = APIRouter(prefix="/api/v1/orgs", tags=["members"])

_user_mgmt_svc = UserManagementService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _check_mgmt_rate_limit(org_id: uuid.UUID) -> None:
    """
    AC8: 30 management operations per org per hour.
    Key: rate:member:{org_id}
    """
    redis = get_redis_client()
    key = f"rate:member:{org_id}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    results = await pipe.execute()
    count, ttl = results[0], results[1]
    if ttl == -1:
        await redis.expire(key, 3600)
        ttl = 3600
    if count > 30:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many management operations. Please try again later.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


async def _audit_member_action(
    schema_name: str,
    action: str,
    actor_id: uuid.UUID,
    actor_email: str,
    target_user_id: uuid.UUID,
    details: dict,
    ip_address: Optional[str] = None,
) -> None:
    """Write a member management audit event to the tenant audit_logs. AC7."""
    try:
        async with AsyncSessionLocal() as audit_db:
            await audit_db.execute(
                text(
                    f'INSERT INTO "{schema_name}".audit_logs '
                    "(action, actor_id, actor_email, resource_type, resource_id, details, ip_address) "
                    "VALUES (:action, :actor_id, :actor_email, :resource_type, :resource_id, "
                    "        :details::jsonb, :ip_address)"
                ),
                {
                    "action": action,
                    "actor_id": str(actor_id),
                    "actor_email": actor_email,
                    "resource_type": "member",
                    "resource_id": str(target_user_id),
                    "details": json.dumps(details, default=str),
                    "ip_address": ip_address,
                },
            )
            await audit_db.commit()
    except Exception as exc:
        logger.error("Member audit log write failed", error=str(exc), action=action)


def _get_tenant_schema(tenant: Tenant) -> str:
    return f"tenant_{tenant.slug.replace('-', '_')}"


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/members — AC1
# RBAC: any authenticated member of the org
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/members",
    response_model=PaginatedMembersResponse,
    responses={
        403: {"description": "Not a member of this organization"},
    },
)
async def list_members(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(25, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Search by name or email"),
    auth: tuple = require_role("owner", "admin", "pm-csm", "qa-manual", "qa-automation", "developer", "viewer"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedMembersResponse:
    """
    List active members of the organization with optional search and pagination. AC1.
    Any authenticated member of the org can view the list.
    """
    result = await _user_mgmt_svc.get_active_members(
        db=db,
        tenant_id=org_id,
        page=page,
        per_page=per_page,
        search=q,
    )

    members = [
        MemberResponse(
            user_id=m.user_id,
            email=m.email,
            full_name=m.full_name,
            role=m.role,
            joined_at=m.joined_at,
            is_active=m.is_active,
        )
        for m in result.members
    ]

    return PaginatedMembersResponse(
        members=members,
        total=result.total,
        page=result.page,
        per_page=result.per_page,
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/orgs/{org_id}/members/{user_id}/role — AC2
# RBAC: Owner/Admin only
# ---------------------------------------------------------------------------

@router.patch(
    "/{org_id}/members/{user_id}/role",
    response_model=MemberResponse,
    responses={
        403: {"description": "Insufficient role or self-action"},
        404: {"description": "Member not found"},
        409: {"description": "Last Owner/Admin guard triggered"},
        422: {"description": "Invalid role"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def change_member_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: ChangeRoleRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> MemberResponse:
    """
    Change a member's role within the organization. AC2, AC7, AC8.
    Cannot change own role (AC2). Last Owner/Admin is protected (AC6).
    """
    actor, actor_membership = auth
    correlation_id = _correlation_id(request)
    ip = _client_ip(request)

    # AC8: rate limit before any business logic
    await _check_mgmt_rate_limit(org_id)

    # Load tenant for schema + email
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # Load target user for email notification
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
        )

    # AC7: capture old role BEFORE service call (service mutates membership.role in-place)
    result = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == org_id,
            TenantUser.user_id == user_id,
        )
    )
    target_membership_snapshot = result.scalar_one_or_none()
    old_role: Optional[str] = target_membership_snapshot.role if target_membership_snapshot else None

    try:
        membership = await _user_mgmt_svc.change_role(
            db=db,
            tenant_id=org_id,
            actor_id=actor.id,
            target_user_id=user_id,
            new_role=payload.role,
        )
    except SelfActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except LastAdminError as exc:
        # AC7: log blocked attempt
        background_tasks.add_task(
            _audit_member_action,
            _get_tenant_schema(tenant),
            "member.role_change_blocked",
            actor.id,
            actor.email,
            user_id,
            {
                "reason": "last_admin_guard",
                "requested_role": payload.role,
                "blocked_message": str(exc),
            },
            ip,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except InvalidRoleError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )

    # membership.role is already set to new_role by the service
    new_role = membership.role
    await db.commit()
    await db.refresh(membership)

    # AC4: send role-changed email asynchronously
    background_tasks.add_task(
        send_role_changed_email,
        recipient_email=target_user.email,
        full_name=target_user.full_name,
        org_name=tenant.name,
        old_role=old_role,
        new_role=new_role,
        correlation_id=correlation_id,
    )

    # AC7: audit log
    background_tasks.add_task(
        _audit_member_action,
        _get_tenant_schema(tenant),
        "member.role_changed",
        actor.id,
        actor.email,
        user_id,
        {
            "old_role": old_role,
            "new_role": new_role,
            "target_user_email": target_user.email,
            "org_name": tenant.name,
        },
        ip,
    )

    return MemberResponse(
        user_id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_role,
        joined_at=membership.joined_at,
        is_active=membership.is_active,
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/orgs/{org_id}/members/{user_id} — AC3, AC5
# RBAC: Owner/Admin only
# ---------------------------------------------------------------------------

@router.delete(
    "/{org_id}/members/{user_id}",
    response_model=RemoveMemberResponse,
    status_code=status.HTTP_200_OK,
    responses={
        403: {"description": "Insufficient role or self-removal"},
        404: {"description": "Member not found"},
        409: {"description": "Last Owner/Admin guard or already removed"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def remove_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> RemoveMemberResponse:
    """
    Soft-delete a member from the organization. AC3, AC5, AC7, AC8.
    Sets is_active=false, removed_at, removed_by. Invalidates Redis sessions (AC5).
    Cannot remove self (AC3). Last Owner/Admin is protected (AC6).
    """
    actor, actor_membership = auth
    correlation_id = _correlation_id(request)
    ip = _client_ip(request)

    # AC8: rate limit
    await _check_mgmt_rate_limit(org_id)

    # Load tenant for schema + email
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # Load target user for email notification
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
        )

    try:
        membership = await _user_mgmt_svc.remove_member(
            db=db,
            tenant_id=org_id,
            actor_id=actor.id,
            target_user_id=user_id,
        )
    except SelfActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except MemberAlreadyRemovedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )
    except LastAdminError as exc:
        # AC7: log blocked removal attempt
        background_tasks.add_task(
            _audit_member_action,
            _get_tenant_schema(tenant),
            "member.removal_blocked",
            actor.id,
            actor.email,
            user_id,
            {
                "reason": "last_admin_guard",
                "blocked_message": str(exc),
            },
            ip,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": exc.code, "message": str(exc)}},
        )

    removed_at = membership.removed_at or datetime.now(timezone.utc)
    await db.commit()

    # AC4: send member-removed email asynchronously
    background_tasks.add_task(
        send_member_removed_email,
        recipient_email=target_user.email,
        full_name=target_user.full_name,
        org_name=tenant.name,
        correlation_id=correlation_id,
    )

    # AC7: audit log
    background_tasks.add_task(
        _audit_member_action,
        _get_tenant_schema(tenant),
        "member.removed",
        actor.id,
        actor.email,
        user_id,
        {
            "target_user_email": target_user.email,
            "org_name": tenant.name,
        },
        ip,
    )

    return RemoveMemberResponse(
        message="Member removed successfully.",
        removed_at=removed_at,
    )
