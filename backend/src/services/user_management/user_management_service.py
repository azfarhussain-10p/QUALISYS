"""
QUALISYS — UserManagementService
Story: 1-4-user-management-remove-change-roles
ACs: AC2, AC3, AC5, AC6, AC7, AC8

Handles:
  - change_role()          — validate + update tenants_users.role (AC2)
  - remove_member()        — soft delete + Redis session invalidation (AC3, AC5)
  - get_active_members()   — paginated list with search (AC1)
  - check_last_admin()     — ownership safety guard with FOR UPDATE (AC6)

Error classes follow the same pattern as InvitationService.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.models.tenant import TenantUser
from src.models.user import User

# ---------------------------------------------------------------------------
# Allowed roles (tech-spec-epic-1 §RBAC Permission Matrix)
# ---------------------------------------------------------------------------

ALLOWED_ROLES = {
    "owner",
    "admin",
    "pm-csm",
    "qa-manual",
    "qa-automation",
    "developer",
    "viewer",
}

ADMIN_ROLES = {"owner", "admin"}


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class UserManagementError(Exception):
    code: str = "USER_MANAGEMENT_ERROR"


class InvalidRoleError(UserManagementError):
    code = "INVALID_ROLE"


class SelfActionError(UserManagementError):
    code = "SELF_ACTION_NOT_ALLOWED"


class LastAdminError(UserManagementError):
    code = "LAST_ADMIN"


class MemberNotFoundError(UserManagementError):
    code = "MEMBER_NOT_FOUND"


class MemberAlreadyRemovedError(UserManagementError):
    code = "MEMBER_ALREADY_REMOVED"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class MemberRecord:
    """Denormalized member record for API responses."""
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    joined_at: datetime
    is_active: bool


@dataclass
class PaginatedMembers:
    members: list[MemberRecord]
    total: int
    page: int
    per_page: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class UserManagementService:
    """
    Stateless service — all methods accept an AsyncSession parameter.
    Callers are responsible for commit/rollback.
    """

    # ------------------------------------------------------------------
    # 2.5 get_active_members (AC1)
    # ------------------------------------------------------------------

    async def get_active_members(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        page: int = 1,
        per_page: int = 25,
        search: Optional[str] = None,
    ) -> PaginatedMembers:
        """
        Return paginated active members for the tenant.
        Optionally filters by name or email (case-insensitive ILIKE).
        Only is_active=true members returned. (AC1)
        """
        # Base join: tenants_users → users
        base_stmt = (
            select(TenantUser, User)
            .join(User, TenantUser.user_id == User.id)
            .where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active == True,  # noqa: E712
            )
        )

        if search:
            pattern = f"%{search}%"
            base_stmt = base_stmt.where(
                or_(
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )

        # Total count (without pagination)
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginated results ordered by joined_at ASC
        offset = (page - 1) * per_page
        paged_stmt = base_stmt.order_by(TenantUser.joined_at.asc()).offset(offset).limit(per_page)
        rows = await db.execute(paged_stmt)

        members = []
        for tenant_user, user in rows.all():
            members.append(
                MemberRecord(
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=tenant_user.role,
                    joined_at=tenant_user.joined_at,
                    is_active=tenant_user.is_active,
                )
            )

        return PaginatedMembers(members=members, total=total, page=page, per_page=per_page)

    # ------------------------------------------------------------------
    # 2.4 check_last_admin (AC6) — atomic, uses SELECT FOR UPDATE
    # ------------------------------------------------------------------

    async def check_last_admin(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        exclude_user_id: uuid.UUID,
    ) -> bool:
        """
        Return True if removing/changing the role of exclude_user_id would leave
        zero active Owner/Admin members.

        Uses SELECT ... FOR UPDATE to prevent race conditions where two admins
        simultaneously attempt to demote each other (AC6).
        """
        stmt = (
            select(func.count())
            .select_from(TenantUser)
            .where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active == True,  # noqa: E712
                TenantUser.role.in_(ADMIN_ROLES),
                TenantUser.user_id != exclude_user_id,
            )
            .with_for_update()
        )
        result = await db.execute(stmt)
        remaining_admins = result.scalar_one()
        return remaining_admins == 0

    # ------------------------------------------------------------------
    # 2.2 change_role (AC2)
    # ------------------------------------------------------------------

    async def change_role(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        target_user_id: uuid.UUID,
        new_role: str,
    ) -> TenantUser:
        """
        Change the role of a member within a tenant.

        Validates:
          - new_role is in ALLOWED_ROLES (AC2)
          - actor is not changing own role (AC2)
          - at least one Owner/Admin remains after change (AC6)
          - target member exists and is active (AC2)

        Returns the updated TenantUser row.
        """
        # Role validation
        if new_role not in ALLOWED_ROLES:
            raise InvalidRoleError(
                f"Role '{new_role}' is not valid. Allowed: {', '.join(sorted(ALLOWED_ROLES))}"
            )

        # Self-action prevention
        if actor_id == target_user_id:
            raise SelfActionError("You cannot change your own role.")

        # Load target membership
        result = await db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.user_id == target_user_id,
                TenantUser.is_active == True,  # noqa: E712
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise MemberNotFoundError("Member not found in this organization.")

        # Last-admin guard (only relevant if current role is admin/owner)
        if membership.role in ADMIN_ROLES and new_role not in ADMIN_ROLES:
            is_last = await self.check_last_admin(
                db=db,
                tenant_id=tenant_id,
                exclude_user_id=target_user_id,
            )
            if is_last:
                raise LastAdminError(
                    "Cannot change role: this is the last Owner/Admin. Transfer ownership first."
                )

        old_role = membership.role
        membership.role = new_role

        logger.info(
            "Member role changed",
            tenant_id=str(tenant_id),
            actor_id=str(actor_id),
            target_user_id=str(target_user_id),
            old_role=old_role,
            new_role=new_role,
        )
        return membership

    # ------------------------------------------------------------------
    # 2.3 remove_member (AC3, AC5)
    # ------------------------------------------------------------------

    async def remove_member(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> TenantUser:
        """
        Soft-delete a member from the tenant.

        Sets is_active=false, removed_at=now(), removed_by=actor_id.
        Invalidates Redis sessions for (user_id, tenant_id). (AC5)

        Validates:
          - actor is not removing themselves (AC3)
          - at least one Owner/Admin remains (AC6)
          - target member exists and is active
        """
        # Self-action prevention
        if actor_id == target_user_id:
            raise SelfActionError("You cannot remove yourself from the organization.")

        # Load target membership
        result = await db.execute(
            select(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.user_id == target_user_id,
            )
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise MemberNotFoundError("Member not found in this organization.")
        if not membership.is_active:
            raise MemberAlreadyRemovedError("This member has already been removed.")

        # Last-admin guard
        if membership.role in ADMIN_ROLES:
            is_last = await self.check_last_admin(
                db=db,
                tenant_id=tenant_id,
                exclude_user_id=target_user_id,
            )
            if is_last:
                raise LastAdminError(
                    "Cannot remove: this is the last Owner/Admin. Transfer ownership first."
                )

        # Soft delete (AC3)
        membership.is_active = False
        membership.removed_at = datetime.now(timezone.utc)
        membership.removed_by = actor_id

        logger.info(
            "Member removed (soft delete)",
            tenant_id=str(tenant_id),
            actor_id=str(actor_id),
            target_user_id=str(target_user_id),
        )

        # AC5: Redis session invalidation
        await self._invalidate_sessions(tenant_id=tenant_id, user_id=target_user_id)

        return membership

    # ------------------------------------------------------------------
    # AC5 — Redis session invalidation
    # ------------------------------------------------------------------

    async def _invalidate_sessions(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """
        Delete all Redis session keys for the given user+tenant pair. (AC5)

        Session key contract (Story 1.5 MUST follow this format):
            sessions:{user_id}:{tenant_id}:{token_suffix}
        Example: sessions:abc-123:org-456:a1b2c3d4e5f6

        Story 1.5 must store session keys in this format so that this scan
        pattern (sessions:{user_id}:{tenant_id}:*) correctly finds and deletes
        all sessions for the removed user scoped to this tenant only.
        Per-tenant scoping is intentional: a user removed from org A must NOT
        lose sessions in org B.

        If no sessions exist or Redis is unavailable, log warning and continue.
        Defense-in-depth: the rbac.py is_active check blocks access even if
        Redis invalidation fails.
        """
        try:
            from src.cache import get_redis_client
            redis = get_redis_client()
            pattern = f"sessions:{user_id}:{tenant_id}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            logger.info(
                "Session invalidation on member removal",
                user_id=str(user_id),
                tenant_id=str(tenant_id),
                sessions_deleted=deleted,
            )
        except Exception as exc:
            # Non-fatal: middleware membership check provides defense-in-depth
            logger.warning(
                "Redis session invalidation failed (non-fatal — middleware will block access)",
                user_id=str(user_id),
                tenant_id=str(tenant_id),
                error=str(exc),
            )
