"""
QUALISYS — Project Service
Story: 1-9-project-creation-configuration
AC: AC2 — create_project() with slug, tenant-scoped, created_by from auth context
AC: AC3 — get_project() and update_project() with slug regeneration
AC: AC5 — created_by set from authenticated user
AC: AC6 — generate_slug() with collision handling (slug-1, slug-2 suffix pattern)
AC: AC7 — server-side validation errors

Story: 1-11-project-management-archive-delete-list
AC: AC1, AC2 — list_projects() with status filter, search, sort, pagination, member count
AC: AC3 — archive_project(): set is_active=false, status='archived'
AC: AC4 — restore_project(): set is_active=true, status='active'
AC: AC5 — delete_project(): hard-delete with cascade, audit BEFORE deletion
AC: AC7 — ProjectAlreadyArchivedError (400), ProjectNotArchivedError (400)

Pattern: raw SQL with double-quoted schema name (same as _audit_log in orgs/router.py).
  Schema is derived from current_tenant_slug ContextVar — set by TenantContextMiddleware
  from JWT claims.  Schema name validated by validate_safe_identifier() before use.

Security (C1, C2):
  - All queries use SQLAlchemy text() with named :params (no f-string interpolation on data)
  - Schema name derived from JWT claim (trusted), validated, double-quoted for DDL safety
  - tenant_id always taken from JWT context, never from request body
  - delete_project audits BEFORE DELETE so project_id/name available for audit record (C3)
"""

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.middleware.tenant_context import current_tenant_slug
from src.services.tenant_provisioning import validate_safe_identifier, slug_to_schema_name


# ---------------------------------------------------------------------------
# Internal project dataclass (mirrors DB row)
# ---------------------------------------------------------------------------

class Project:
    """Lightweight project record returned by service methods."""

    __slots__ = (
        "id", "name", "slug", "description", "app_url", "github_repo_url",
        "status", "settings", "is_active", "created_by", "tenant_id",
        "organization_id", "created_at", "updated_at",
    )

    def __init__(self, row: Any) -> None:
        self.id: uuid.UUID = row["id"]
        self.name: str = row["name"]
        self.slug: str = row["slug"]
        self.description: Optional[str] = row["description"]
        self.app_url: Optional[str] = row["app_url"]
        self.github_repo_url: Optional[str] = row["github_repo_url"]
        self.status: str = row["status"]
        self.settings: dict = row["settings"] if row["settings"] else {}
        self.is_active: bool = row["is_active"]
        self.created_by: Optional[uuid.UUID] = row["created_by"]
        self.tenant_id: uuid.UUID = row["tenant_id"]
        self.organization_id: Optional[uuid.UUID] = row["organization_id"]
        self.created_at: datetime = row["created_at"]
        self.updated_at: datetime = row["updated_at"]

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "app_url": self.app_url,
            "github_repo_url": self.github_repo_url,
            "status": self.status,
            "settings": self.settings,
            "is_active": self.is_active,
            "created_by": str(self.created_by) if self.created_by else None,
            "tenant_id": str(self.tenant_id),
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# ProjectServiceError hierarchy
# ---------------------------------------------------------------------------

class ProjectServiceError(Exception):
    """Base for all project service errors."""


class ProjectNotFoundError(ProjectServiceError):
    pass


class DuplicateSlugError(ProjectServiceError):
    pass


class InvalidProjectDataError(ProjectServiceError):
    pass


class ProjectAlreadyArchivedError(ProjectServiceError):
    """Raised when archiving a project that is already archived (AC7, Story 1.11)."""


class ProjectNotArchivedError(ProjectServiceError):
    """Raised when restoring a project that is not archived (AC7, Story 1.11)."""


# ---------------------------------------------------------------------------
# ProjectWithMemberCount — used by list_projects (Story 1.11, AC1)
# ---------------------------------------------------------------------------

@dataclass
class ProjectWithMemberCount:
    """Project record with member_count and health placeholder (AC1, AC6)."""
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    app_url: Optional[str]
    github_repo_url: Optional[str]
    status: str
    settings: dict
    is_active: bool
    created_by: Optional[uuid.UUID]
    tenant_id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    health: str = "—"  # AC6: placeholder for Epic 1

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "app_url": self.app_url,
            "github_repo_url": self.github_repo_url,
            "status": self.status,
            "settings": self.settings,
            "is_active": self.is_active,
            "created_by": str(self.created_by) if self.created_by else None,
            "tenant_id": str(self.tenant_id),
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "member_count": self.member_count,
            "health": self.health,
        }


# ---------------------------------------------------------------------------
# PaginatedResult — generic pagination wrapper (Story 1.11, AC1)
# ---------------------------------------------------------------------------

@dataclass
class PaginatedResult:
    """Paginated list of projects with pagination metadata."""
    data: list
    page: int
    per_page: int
    total: int
    total_pages: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_schema(slug: Optional[str] = None) -> str:
    """
    Derive and validate the tenant schema name from the current request's
    tenant slug ContextVar (set by TenantContextMiddleware).

    Security (C1): All project queries are strictly scoped to the tenant schema.
    Schema name is derived from a JWT claim (trusted source) and validated
    by validate_safe_identifier() before use. Double-quoted in all SQL.
    """
    tenant_slug = slug or current_tenant_slug.get()
    if not tenant_slug:
        raise ProjectServiceError("No tenant context — cannot access project data.")
    schema_name = slug_to_schema_name(tenant_slug)
    if not validate_safe_identifier(schema_name):
        raise ProjectServiceError(f"Invalid tenant schema: {schema_name}")
    return schema_name


def _slugify_base(name: str) -> str:
    """
    Generate a URL-safe base slug from project name (AC6, C9).
    Steps: Unicode normalize → ASCII → lowercase → non-alnum→hyphens →
           collapse hyphens → strip edges → truncate to 90 chars.
    """
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name[:90] or "project"


# ---------------------------------------------------------------------------
# ProjectService
# ---------------------------------------------------------------------------

class ProjectService:
    """
    CRUD operations for projects in tenant schemas.
    All methods accept an AsyncSession from the public schema get_db() dependency;
    they target the correct tenant schema via double-quoted schema name in raw SQL.
    """

    # ------------------------------------------------------------------
    # AC6 — generate_slug: lowercase + hyphens + collision suffix
    # ------------------------------------------------------------------

    async def generate_slug(
        self,
        name: str,
        db: AsyncSession,
        schema_name: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> str:
        """
        Generate a unique slug within the tenant schema.

        Algorithm (AC6):
          1. Slugify: lowercase, replace non-alnum with hyphens, collapse, strip, truncate.
          2. Check uniqueness in {schema}.projects.
          3. On collision: append -1, -2, ... until available.
        """
        base = _slugify_base(name)
        candidate = base
        counter = 0

        while True:
            if exclude_id is not None:
                stmt = text(
                    f'SELECT 1 FROM "{schema_name}".projects '
                    "WHERE slug = :slug AND id != :exclude_id"
                )
                result = await db.execute(stmt, {"slug": candidate, "exclude_id": str(exclude_id)})
            else:
                stmt = text(
                    f'SELECT 1 FROM "{schema_name}".projects WHERE slug = :slug'
                )
                result = await db.execute(stmt, {"slug": candidate})

            if result.fetchone() is None:
                return candidate

            counter += 1
            suffix = f"-{counter}"
            candidate = base[: 100 - len(suffix)] + suffix

    # ------------------------------------------------------------------
    # AC2, AC5 — create_project
    # ------------------------------------------------------------------

    async def create_project(
        self,
        name: str,
        description: Optional[str],
        app_url: Optional[str],
        github_repo_url: Optional[str],
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        db: AsyncSession,
        organization_id: Optional[uuid.UUID] = None,
    ) -> "Project":
        """
        Create a new project in the tenant schema (AC2, AC5).

        - Auto-generates slug with collision handling (AC6)
        - created_by recorded from authenticated user (AC5)
        - tenant_id always from JWT context, never request body (C1)
        """
        schema_name = _get_schema()
        project_id = uuid.uuid4()

        # AC6: generate unique slug
        slug = await self.generate_slug(name, db, schema_name)

        # AC2: insert project record
        stmt = text(
            f'INSERT INTO "{schema_name}".projects '
            "(id, name, slug, description, app_url, github_repo_url, "
            " tenant_id, organization_id, settings, status, is_active, created_by) "
            "VALUES (:id, :name, :slug, :description, :app_url, :github_repo_url, "
            "        :tenant_id, :org_id, :settings::jsonb, 'active', true, :created_by) "
            "RETURNING *"
        )
        result = await db.execute(
            stmt,
            {
                "id": str(project_id),
                "name": name,
                "slug": slug,
                "description": description,
                "app_url": app_url,
                "github_repo_url": github_repo_url,
                "tenant_id": str(tenant_id),
                "org_id": str(organization_id) if organization_id else None,
                "settings": "{}",
                "created_by": str(created_by),
            },
        )
        row = result.mappings().fetchone()
        if row is None:
            raise ProjectServiceError("Insert returned no row — unexpected DB error.")

        # AC#6 (Story 1.10): auto-assign creator to project_members before commit.
        # Wrapped in try/except so Story 1.9 works even when migration 009
        # (project_members table) has not yet been applied.
        try:
            from src.services.project_member_service import project_member_service as _pm_svc
            await _pm_svc.auto_assign_creator(
                project_id=project_id,
                creator_id=created_by,
                tenant_id=tenant_id,
                db=db,
            )
        except Exception as exc:
            logger.warning(
                "auto_assign_creator failed (project_members may not exist yet)",
                exc=str(exc),
            )

        await db.commit()
        logger.info(
            "Project created",
            project_id=str(project_id),
            slug=slug,
            tenant_id=str(tenant_id),
            created_by=str(created_by),
        )
        return Project(row)

    # ------------------------------------------------------------------
    # AC3 — get_project (by ID or slug)
    # ------------------------------------------------------------------

    async def get_project(
        self,
        db: AsyncSession,
        project_id: Optional[uuid.UUID] = None,
        slug: Optional[str] = None,
    ) -> "Project":
        """
        Retrieve project by ID or slug within the tenant schema (AC3).
        Raises ProjectNotFoundError if not found.
        """
        if project_id is None and slug is None:
            raise InvalidProjectDataError("Must provide project_id or slug.")

        schema_name = _get_schema()

        if project_id is not None:
            stmt = text(
                f'SELECT * FROM "{schema_name}".projects '
                "WHERE id = :project_id AND is_active = true"
            )
            result = await db.execute(stmt, {"project_id": str(project_id)})
        else:
            stmt = text(
                f'SELECT * FROM "{schema_name}".projects '
                "WHERE slug = :slug AND is_active = true"
            )
            result = await db.execute(stmt, {"slug": slug})

        row = result.mappings().fetchone()
        if row is None:
            raise ProjectNotFoundError(
                f"Project not found: {project_id or slug}"
            )
        return Project(row)

    # ------------------------------------------------------------------
    # Internal helper — get project regardless of is_active (Story 1.11)
    # ------------------------------------------------------------------

    async def _get_project_raw(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        schema_name: str,
    ) -> "Project":
        """Fetch project by ID without filtering on is_active. Used internally."""
        stmt = text(
            f'SELECT * FROM "{schema_name}".projects WHERE id = :project_id'
        )
        result = await db.execute(stmt, {"project_id": str(project_id)})
        row = result.mappings().fetchone()
        if row is None:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return Project(row)

    # ------------------------------------------------------------------
    # AC3, AC4 — update_project
    # ------------------------------------------------------------------

    async def update_project(
        self,
        project_id: uuid.UUID,
        updates: dict,
        db: AsyncSession,
    ) -> "Project":
        """
        Update project fields (AC3, AC4).

        Handles:
          - name change → slug regeneration (AC3)
          - description, app_url, github_repo_url changes
          - settings JSONB merge (AC4): deep-merge with existing settings
        """
        schema_name = _get_schema()

        # Fetch current project
        project = await self.get_project(db, project_id=project_id)

        set_clauses: list[str] = []
        params: dict = {"project_id": str(project_id)}

        if "name" in updates and updates["name"] is not None:
            new_name = updates["name"]
            new_slug = await self.generate_slug(
                new_name, db, schema_name, exclude_id=project_id
            )
            set_clauses.append("name = :name")
            set_clauses.append("slug = :slug")
            params["name"] = new_name
            params["slug"] = new_slug

        if "description" in updates:
            set_clauses.append("description = :description")
            params["description"] = updates["description"]

        if "app_url" in updates:
            set_clauses.append("app_url = :app_url")
            params["app_url"] = updates["app_url"]

        if "github_repo_url" in updates:
            set_clauses.append("github_repo_url = :github_repo_url")
            params["github_repo_url"] = updates["github_repo_url"]

        if "settings" in updates and updates["settings"] is not None:
            # AC4: merge JSONB settings
            merged = {**project.settings, **updates["settings"]}
            import json
            set_clauses.append("settings = :settings::jsonb")
            params["settings"] = json.dumps(merged)

        if not set_clauses:
            return project  # nothing to update

        set_clauses.append("updated_at = NOW()")

        stmt = text(
            f'UPDATE "{schema_name}".projects '
            f"SET {', '.join(set_clauses)} "
            "WHERE id = :project_id "
            "RETURNING *"
        )
        result = await db.execute(stmt, params)
        row = result.mappings().fetchone()
        if row is None:
            raise ProjectNotFoundError(f"Project not found during update: {project_id}")

        await db.commit()
        logger.info(
            "Project updated",
            project_id=str(project_id),
            fields=list(updates.keys()),
        )
        return Project(row)


    # ------------------------------------------------------------------
    # Story 1.11, AC1, AC2 — list_projects
    # ------------------------------------------------------------------

    async def list_projects(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        user_role: str,
        tenant_id: uuid.UUID,
        status: str = "active",
        search: Optional[str] = None,
        sort: str = "created_at",
        page: int = 1,
        per_page: int = 20,
    ) -> "PaginatedResult":
        """
        List projects accessible to the authenticated user. Story 1.11, AC1, AC2.

        Membership filtering (C7):
          - Owner/Admin: all projects in tenant
          - Other roles: only projects in project_members for this user

        Filtering:
          - status='active'   → is_active = true
          - status='archived' → is_active = false
          - status='all'      → no is_active filter

        Search: ILIKE on name (parameterized — C2).
        Sort: name, created_at (default), status.
        Pagination: page/per_page with total count.
        Member count: LEFT JOIN project_members GROUP BY project id.
        Health: placeholder '—' (AC6).
        """
        schema_name = _get_schema()

        # --- Build WHERE clause ---
        where_clauses = ["p.tenant_id = :tenant_id"]
        params: dict = {"tenant_id": str(tenant_id)}

        if status == "active":
            where_clauses.append("p.is_active = true")
        elif status == "archived":
            where_clauses.append("p.is_active = false")
        # status == 'all' → no is_active filter

        if search:
            where_clauses.append("p.name ILIKE :search")
            params["search"] = f"%{search}%"

        # --- Membership filter (C7) ---
        if user_role not in ("owner", "admin"):
            # Subquery: only projects user is explicitly a member of
            where_clauses.append(
                f'EXISTS (SELECT 1 FROM "{schema_name}".project_members pm2 '
                "WHERE pm2.project_id = p.id AND pm2.user_id = :user_id)"
            )
            params["user_id"] = str(user_id)

        where_sql = " AND ".join(where_clauses)

        # --- Sort ---
        valid_sorts = {"name": "p.name", "created_at": "p.created_at", "status": "p.status"}
        order_col = valid_sorts.get(sort, "p.created_at")
        order_sql = f"{order_col} DESC"

        # --- Count query ---
        count_stmt = text(
            f'SELECT COUNT(*) FROM "{schema_name}".projects p WHERE {where_sql}'
        )
        count_result = await db.execute(count_stmt, params)
        total = count_result.scalar_one()

        total_pages = max(1, -(-total // per_page))  # ceiling division
        offset = (page - 1) * per_page
        params["limit"] = per_page
        params["offset"] = offset

        # --- Data query with member count LEFT JOIN ---
        data_stmt = text(
            f'SELECT p.*, COALESCE(mc.cnt, 0) AS member_count '
            f'FROM "{schema_name}".projects p '
            f'LEFT JOIN ('
            f'  SELECT project_id, COUNT(*) AS cnt '
            f'  FROM "{schema_name}".project_members '
            f'  GROUP BY project_id'
            f') mc ON mc.project_id = p.id '
            f'WHERE {where_sql} '
            f'ORDER BY {order_sql} '
            f'LIMIT :limit OFFSET :offset'
        )
        data_result = await db.execute(data_stmt, params)
        rows = data_result.mappings().fetchall()

        projects = []
        for row in rows:
            p = Project(row)
            projects.append(
                ProjectWithMemberCount(
                    id=p.id,
                    name=p.name,
                    slug=p.slug,
                    description=p.description,
                    app_url=p.app_url,
                    github_repo_url=p.github_repo_url,
                    status=p.status,
                    settings=p.settings,
                    is_active=p.is_active,
                    created_by=p.created_by,
                    tenant_id=p.tenant_id,
                    organization_id=p.organization_id,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    member_count=int(row["member_count"]),
                    health="—",
                )
            )

        return PaginatedResult(
            data=projects,
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        )

    # ------------------------------------------------------------------
    # Story 1.11, AC3 — archive_project
    # ------------------------------------------------------------------

    async def archive_project(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> "Project":
        """
        Soft-delete: set is_active=false and status='archived'. Story 1.11, AC3.
        Raises ProjectAlreadyArchivedError (400) if already archived (C5, AC7).
        """
        schema_name = _get_schema()
        project = await self._get_project_raw(db, project_id, schema_name)

        if not project.is_active:
            raise ProjectAlreadyArchivedError(
                f"Project '{project.name}' is already archived."
            )

        stmt = text(
            f'UPDATE "{schema_name}".projects '
            "SET is_active = false, status = 'archived', updated_at = NOW() "
            "WHERE id = :project_id "
            "RETURNING *"
        )
        result = await db.execute(stmt, {"project_id": str(project_id)})
        row = result.mappings().fetchone()
        if row is None:
            raise ProjectNotFoundError(f"Project not found during archive: {project_id}")

        await db.commit()
        logger.info("Project archived", project_id=str(project_id), name=project.name)
        return Project(row)

    # ------------------------------------------------------------------
    # Story 1.11, AC4 — restore_project
    # ------------------------------------------------------------------

    async def restore_project(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
    ) -> "Project":
        """
        Restore: set is_active=true and status='active'. Story 1.11, AC4.
        Raises ProjectNotArchivedError (400) if project is not archived (C5, AC7).
        """
        schema_name = _get_schema()
        project = await self._get_project_raw(db, project_id, schema_name)

        if project.is_active:
            raise ProjectNotArchivedError(
                f"Project '{project.name}' is not archived."
            )

        stmt = text(
            f'UPDATE "{schema_name}".projects '
            "SET is_active = true, status = 'active', updated_at = NOW() "
            "WHERE id = :project_id "
            "RETURNING *"
        )
        result = await db.execute(stmt, {"project_id": str(project_id)})
        row = result.mappings().fetchone()
        if row is None:
            raise ProjectNotFoundError(f"Project not found during restore: {project_id}")

        await db.commit()
        logger.info("Project restored", project_id=str(project_id), name=project.name)
        return Project(row)

    # ------------------------------------------------------------------
    # Story 1.11, AC5 — delete_project (hard-delete with cascade)
    # ------------------------------------------------------------------

    async def delete_project(
        self,
        project_id: uuid.UUID,
        db: AsyncSession,
        audit_schema: Optional[str] = None,
        audit_tenant_id: Optional[uuid.UUID] = None,
        audit_actor_id: Optional[uuid.UUID] = None,
        audit_actor_email: Optional[str] = None,  # retained for compat; not stored
        audit_ip: Optional[str] = None,
    ) -> None:
        """
        Hard-delete: permanently remove project and all related data. Story 1.11, AC5.

        Cascade order (C3, C8 — no FK constraints, handled at app layer):
          1. test_executions WHERE test_case_id IN (test_cases for this project)
          2. test_cases WHERE project_id = project_id
          3. project_members WHERE project_id = project_id
          4. projects WHERE id = project_id

        Audit entry logged BEFORE deletion (C3, AC8) so project_id/name are available.
        """
        schema_name = _get_schema()
        project = await self._get_project_raw(db, project_id, schema_name)

        # AC8, C3: Audit BEFORE deletion — project data must be available
        if audit_schema and audit_actor_id and audit_tenant_id:
            await _write_delete_audit(
                db=db,
                audit_schema=audit_schema,
                project_id=project_id,
                project_name=project.name,
                tenant_id=audit_tenant_id,
                actor_id=audit_actor_id,
                ip=audit_ip,
            )

        # C8: Cascade — test_executions (via test_cases.project_id)
        await db.execute(
            text(
                f'DELETE FROM "{schema_name}".test_executions '
                f'WHERE test_case_id IN ('
                f'  SELECT id FROM "{schema_name}".test_cases '
                f'  WHERE project_id = :project_id'
                f')'
            ),
            {"project_id": str(project_id)},
        )

        # C8: Cascade — test_cases
        await db.execute(
            text(
                f'DELETE FROM "{schema_name}".test_cases WHERE project_id = :project_id'
            ),
            {"project_id": str(project_id)},
        )

        # C8: Cascade — project_members
        await db.execute(
            text(
                f'DELETE FROM "{schema_name}".project_members WHERE project_id = :project_id'
            ),
            {"project_id": str(project_id)},
        )

        # Hard-delete the project itself
        result = await db.execute(
            text(
                f'DELETE FROM "{schema_name}".projects WHERE id = :project_id RETURNING id'
            ),
            {"project_id": str(project_id)},
        )
        if result.fetchone() is None:
            raise ProjectNotFoundError(f"Project not found during delete: {project_id}")

        await db.commit()
        logger.info(
            "Project hard-deleted",
            project_id=str(project_id),
            name=project.name,
        )


# ---------------------------------------------------------------------------
# Audit helper for delete (runs within the same session/transaction)
# ---------------------------------------------------------------------------

async def _write_delete_audit(
    db: AsyncSession,
    audit_schema: str,
    project_id: uuid.UUID,
    project_name: str,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    ip: Optional[str],
) -> None:
    """
    Write project.deleted audit entry into {audit_schema}.audit_logs.
    Story 1.11, AC8 — audit BEFORE deletion (C3).
    Column names match migration 011_create_audit_logs (Story 1.12).
    """
    try:
        await db.execute(
            text(
                f'INSERT INTO "{audit_schema}".audit_logs '
                "(tenant_id, actor_user_id, action, resource_type, resource_id, details, ip_address) "
                "VALUES (:tenant_id, :actor_user_id, 'project.deleted', 'project', :resource_id, "
                "        :details::jsonb, :ip_address)"
            ),
            {
                "tenant_id": str(tenant_id),
                "actor_user_id": str(actor_id),
                "resource_id": str(project_id),
                "details": json.dumps(
                    {"project_id": str(project_id), "project_name": project_name, "deleted_by": str(actor_id)},
                    default=str,
                ),
                "ip_address": ip,
            },
        )
    except Exception as exc:
        logger.error("Delete audit write failed (non-fatal)", error=str(exc))


# Module-level singleton
project_service = ProjectService()
