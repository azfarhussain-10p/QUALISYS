"""
QUALISYS — PM Dashboard Org-Level API
Story: 2-13-pm-dashboard-test-coverage-metrics
AC-3: GET /api/v1/orgs/{org_id}/dashboard/projects
RBAC: require_role("owner", "admin", "pm-csm")
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends  # noqa: F401 (Depends used by get_db)
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dashboard.schemas import ProjectsHealthResponse
from src.db import get_db
from src.middleware.rbac import require_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.pm_dashboard_service import pm_dashboard_service
from src.services.tenant_provisioning import slug_to_schema_name

org_router = APIRouter(tags=["PM Dashboard"])


@org_router.get(
    "/api/v1/orgs/{org_id}/dashboard/projects",
    response_model=ProjectsHealthResponse,
)
async def get_projects_health(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner", "admin", "pm-csm"),
    db: AsyncSession = Depends(get_db),
) -> ProjectsHealthResponse:
    """AC-3: Return health cards for all projects in the tenant."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    tenant_id = str(auth[1].tenant_id)
    data = await pm_dashboard_service.get_all_projects_health(db, schema_name, tenant_id)
    return ProjectsHealthResponse(**data)
