"""
QUALISYS — Project Member Service
Story: 1-10-project-team-assignment
AC: #2 — add_member, add_members_bulk, auto_assign_creator
AC: #3 — check_access (Owner/Admin bypass + project_members lookup)
AC: #4 — remove_member (returns 404 if not explicitly assigned)
AC: #5 — email notification triggered by members.py router
AC: #6 — auto_assign_creator called from ProjectService.create_project()
AC: #7 — AlreadyMemberError (409), UserNotInOrgError (404)

Pattern: Raw SQL with double-quoted schema name — same as project_service.py.
  Schema derived from current_tenant_slug ContextVar (JWT-backed).
  All queries use SQLAlchemy text() with named :params (no f-string on data).

Security (C1, C2):
  - Schema name from ContextVar (JWT claim — trusted), validated before use
  - All user data via :named params, never interpolated into SQL
  - tenant_id always from JWT context, never from request body
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.middleware.tenant_context import current_tenant_slug
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ProjectMemberError(Exception):
    """Base for all project member service errors."""
    code: str = "PROJECT_MEMBER_ERROR"


class AlreadyMemberError(ProjectMemberError):
    """User is already a member of this project."""
    code = "ALREADY_MEMBER"


class UserNotInOrgError(ProjectMemberError):
    """User does not belong to this organization."""
    code = "USER_NOT_IN_ORG"


class MemberNotFoundError(ProjectMemberError):
    """User is not explicitly assigned to this project."""
    code = "MEMBER_NOT_FOUND"


# ---------------------------------------------------------------------------
# Member dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProjectMember:
    id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    added_by: Optional[uuid.UUID]
    tenant_id: uuid.UUID
    created_at: datetime
    # Profile fields populated by list_members() JOIN
    full_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    org_role: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "user_id": str(self.user_id),
            "added_by": str(self.added_by) if self.added_by else None,
            "tenant_id": str(self.tenant_id),
            "created_at": self.created_at.isoformat(),
            "full_name": self.full_name,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "org_role": self.org_role,
        }


# ---------------------------------------------------------------------------
# ProjectMemberService
# ---------------------------------------------------------------------------

class ProjectMemberService:
    """
    Raw SQL service for project membership operations.
    All queries target {tenant_schema}.project_members with parameterized statements.
    Schema derived from ContextVar — never from user input.
    """

    def _get_schema(self) -> str:
        """Derive and validate tenant schema from ContextVar."""
        tenant_slug = current_tenant_slug.get()
        if not tenant_slug:
            raise ProjectMemberError("No tenant context — cannot access project members.")
        schema_name = slug_to_schema_name(tenant_slug)
        if not validate_safe_identifier(schema_name):
            raise ProjectMemberError(f"Invalid tenant schema: {schema_name}")
        return schema_name

    # ------------------------------------------------------------------
    # AC#2 — add_member
    # ------------------------------------------------------------------

    async def add_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        added_by: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> "ProjectMember":
        """
        Add a single user to a project. AC#2, AC#7.

        Validates:
          - User is an active org member (public.tenants_users)
          - User is not already in project_members

        Raises:
          - UserNotInOrgError: user not in org → 404
          - AlreadyMemberError: duplicate → 409
        """
        schema = self._get_schema()

        # Validate org membership (security: user must be active in this tenant)
        org_check = await db.execute(
            text(
                "SELECT 1 FROM public.tenants_users "
                "WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_active = true"
            ),
            {"tenant_id": str(tenant_id), "user_id": str(user_id)},
        )
        if org_check.fetchone() is None:
            raise UserNotInOrgError(
                f"User {user_id} is not an active member of this organization."
            )

        # Check not already a member (prevent 409)
        dup_check = await db.execute(
            text(
                f'SELECT 1 FROM "{schema}".project_members '
                "WHERE project_id = :project_id AND user_id = :user_id"
            ),
            {"project_id": str(project_id), "user_id": str(user_id)},
        )
        if dup_check.fetchone() is not None:
            raise AlreadyMemberError("User is already a member of this project.")

        # Insert membership record
        result = await db.execute(
            text(
                f'INSERT INTO "{schema}".project_members '
                "(project_id, user_id, added_by, tenant_id) "
                "VALUES (:project_id, :user_id, :added_by, :tenant_id) "
                "RETURNING *"
            ),
            {
                "project_id": str(project_id),
                "user_id": str(user_id),
                "added_by": str(added_by),
                "tenant_id": str(tenant_id),
            },
        )
        row = result.mappings().fetchone()
        await db.commit()

        logger.info(
            "Project member added",
            project_id=str(project_id),
            user_id=str(user_id),
            added_by=str(added_by),
        )
        return self._row_to_member(row)

    # ------------------------------------------------------------------
    # AC#2 — add_members_bulk
    # ------------------------------------------------------------------

    async def add_members_bulk(
        self,
        project_id: uuid.UUID,
        user_ids: list[uuid.UUID],
        added_by: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> list["ProjectMember"]:
        """
        Add multiple users to a project in batch. AC#2.
        Validates all user_ids before inserting.
        Skips users already in the project (idempotent bulk add).
        Raises UserNotInOrgError if any user_id is not an org member.
        """
        if not user_ids:
            return []

        schema = self._get_schema()
        members: list[ProjectMember] = []

        for user_id in user_ids:
            # Validate org membership
            org_check = await db.execute(
                text(
                    "SELECT 1 FROM public.tenants_users "
                    "WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_active = true"
                ),
                {"tenant_id": str(tenant_id), "user_id": str(user_id)},
            )
            if org_check.fetchone() is None:
                raise UserNotInOrgError(
                    f"User {user_id} is not an active member of this organization."
                )

            # Skip already-members (idempotent)
            dup_check = await db.execute(
                text(
                    f'SELECT 1 FROM "{schema}".project_members '
                    "WHERE project_id = :project_id AND user_id = :user_id"
                ),
                {"project_id": str(project_id), "user_id": str(user_id)},
            )
            if dup_check.fetchone() is not None:
                continue

            result = await db.execute(
                text(
                    f'INSERT INTO "{schema}".project_members '
                    "(project_id, user_id, added_by, tenant_id) "
                    "VALUES (:project_id, :user_id, :added_by, :tenant_id) "
                    "RETURNING *"
                ),
                {
                    "project_id": str(project_id),
                    "user_id": str(user_id),
                    "added_by": str(added_by),
                    "tenant_id": str(tenant_id),
                },
            )
            row = result.mappings().fetchone()
            if row:
                members.append(self._row_to_member(row))

        await db.commit()
        logger.info(
            "Project members bulk added",
            project_id=str(project_id),
            count=len(members),
            added_by=str(added_by),
        )
        return members

    # ------------------------------------------------------------------
    # AC#4 — remove_member
    # ------------------------------------------------------------------

    async def remove_member(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        removed_by: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """
        Remove a user from a project. AC#4.

        AC#4: Owner/Admin note — they still have implicit project access even if removed
        from project_members (check_access returns True for Owner/Admin regardless).
        Raises MemberNotFoundError if user is not explicitly in project_members.
        """
        schema = self._get_schema()

        # Verify member exists
        existing = await db.execute(
            text(
                f'SELECT id FROM "{schema}".project_members '
                "WHERE project_id = :project_id AND user_id = :user_id"
            ),
            {"project_id": str(project_id), "user_id": str(user_id)},
        )
        if existing.fetchone() is None:
            raise MemberNotFoundError(
                f"User {user_id} is not explicitly assigned to this project."
            )

        await db.execute(
            text(
                f'DELETE FROM "{schema}".project_members '
                "WHERE project_id = :project_id AND user_id = :user_id"
            ),
            {"project_id": str(project_id), "user_id": str(user_id)},
        )
        await db.commit()
        logger.info(
            "Project member removed",
            project_id=str(project_id),
            user_id=str(user_id),
            removed_by=str(removed_by),
        )

    # ------------------------------------------------------------------
    # AC#1, #3 — list_members
    # ------------------------------------------------------------------

    async def list_members(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> list["ProjectMember"]:
        """
        List project members with profile data. AC#1, #3.
        JOINs public.users and public.tenants_users for name, email, avatar, org role.
        """
        schema = self._get_schema()

        result = await db.execute(
            text(
                f'SELECT pm.id, pm.project_id, pm.user_id, pm.added_by, '
                f'       pm.tenant_id, pm.created_at, '
                f'       u.full_name, u.email, u.avatar_url, '
                f'       tu.role AS org_role '
                f'FROM "{schema}".project_members pm '
                f'JOIN public.users u  ON u.id  = pm.user_id '
                f'JOIN public.tenants_users tu '
                f'     ON tu.user_id = pm.user_id AND tu.tenant_id = pm.tenant_id '
                f'WHERE pm.project_id = :project_id '
                f'ORDER BY pm.created_at ASC'
            ),
            {"project_id": str(project_id)},
        )
        rows = result.mappings().fetchall()
        return [self._row_to_member(row, with_profile=True) for row in rows]

    # ------------------------------------------------------------------
    # AC#3 — check_access
    # ------------------------------------------------------------------

    async def check_access(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        user_org_role: str,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> bool:
        """
        Return True if user may access this project. AC#3.

        Algorithm:
          1. Owner/Admin → always True (implicit access to ALL projects in org)
          2. Check project_members for explicit membership → True if found
          3. Else → False (403 in router)
        """
        # AC#3: Owner/Admin have implicit access — bypass membership check
        if user_org_role in ("owner", "admin"):
            return True

        schema = self._get_schema()
        result = await db.execute(
            text(
                f'SELECT 1 FROM "{schema}".project_members '
                "WHERE project_id = :project_id AND user_id = :user_id"
            ),
            {"project_id": str(project_id), "user_id": str(user_id)},
        )
        return result.fetchone() is not None

    # ------------------------------------------------------------------
    # AC#6 — auto_assign_creator
    # ------------------------------------------------------------------

    async def auto_assign_creator(
        self,
        project_id: uuid.UUID,
        creator_id: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """
        Add project creator to project_members. AC#6.
        Called by ProjectService.create_project() after project creation.
        Idempotent: no-ops if already a member.
        NOTE: Does NOT call db.commit() — caller owns the transaction.
        """
        schema = self._get_schema()

        # Idempotency check
        existing = await db.execute(
            text(
                f'SELECT 1 FROM "{schema}".project_members '
                "WHERE project_id = :project_id AND user_id = :user_id"
            ),
            {"project_id": str(project_id), "user_id": str(creator_id)},
        )
        if existing.fetchone() is not None:
            return

        await db.execute(
            text(
                f'INSERT INTO "{schema}".project_members '
                "(project_id, user_id, added_by, tenant_id) "
                "VALUES (:project_id, :user_id, :added_by, :tenant_id)"
            ),
            {
                "project_id": str(project_id),
                "user_id": str(creator_id),
                "added_by": str(creator_id),
                "tenant_id": str(tenant_id),
            },
        )
        logger.info(
            "Project creator auto-assigned to project_members",
            project_id=str(project_id),
            creator_id=str(creator_id),
        )

    # ------------------------------------------------------------------
    # AC#3 — list_member_project_ids (for GET /projects filtering)
    # ------------------------------------------------------------------

    async def list_member_project_ids(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> list[uuid.UUID]:
        """
        Return list of project IDs the user is explicitly a member of.
        Used by GET /api/v1/projects to filter results for non-Admin users.
        """
        schema = self._get_schema()

        result = await db.execute(
            text(
                f'SELECT project_id FROM "{schema}".project_members '
                "WHERE user_id = :user_id AND tenant_id = :tenant_id"
            ),
            {"user_id": str(user_id), "tenant_id": str(tenant_id)},
        )
        rows = result.fetchall()
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _row_to_member(self, row, with_profile: bool = False) -> "ProjectMember":
        return ProjectMember(
            id=row["id"],
            project_id=row["project_id"],
            user_id=row["user_id"],
            added_by=row.get("added_by"),
            tenant_id=row["tenant_id"],
            created_at=row["created_at"],
            full_name=row.get("full_name") if with_profile else None,
            email=row.get("email") if with_profile else None,
            avatar_url=row.get("avatar_url") if with_profile else None,
            org_role=row.get("org_role") if with_profile else None,
        )


# Module-level singleton
project_member_service = ProjectMemberService()
