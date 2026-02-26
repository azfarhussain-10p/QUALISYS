"""
QUALISYS — Project Access FastAPI Dependency
Story: 1-10-project-team-assignment
AC: #3 — check_project_access: Owner/Admin bypass + project_members lookup

This dependency enforces that only authorized users can access project-scoped
resources. It layers on top of require_project_role() (org membership check) to
additionally verify project-level membership.

Usage:
    @router.get("/{project_id}/members")
    async def list_members(
        project_id: uuid.UUID,
        auth: tuple = Depends(check_project_access),
        db: AsyncSession = Depends(get_db),
    ):
        user, membership = auth
        ...

    Or as a route-level dependency:
    @router.get("/{project_id}/...", dependencies=[Depends(check_project_access)])
"""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.rbac import require_project_role
from src.services.project_member_service import ProjectMemberError, project_member_service


async def check_project_access(
    project_id: uuid.UUID,
    auth: tuple = require_project_role(),   # any active org member
    db: AsyncSession = Depends(get_db),
) -> tuple:
    """
    FastAPI dependency: verify requesting user can access a specific project.

    AC#3 Algorithm:
      1. User must be active org member (require_project_role() handles 401/403)
      2. Owner/Admin → implicit access to ALL projects (check_access returns True)
      3. Other roles → must be in project_members for this project_id
      4. Not authorized → HTTP 403 PROJECT_ACCESS_DENIED

    Returns (User, TenantUser) tuple — passed through for downstream use.
    """
    user, membership = auth

    try:
        has_access = await project_member_service.check_access(
            project_id=project_id,
            user_id=user.id,
            user_org_role=membership.role,
            tenant_id=membership.tenant_id,
            db=db,
        )
    except ProjectMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "PROJECT_ACCESS_CHECK_FAILED",
                    "message": str(exc),
                }
            },
        ) from exc

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "PROJECT_ACCESS_DENIED",
                    "message": "You do not have access to this project.",
                }
            },
        )

    return auth  # pass through for downstream endpoint use
