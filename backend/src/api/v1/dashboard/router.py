"""
QUALISYS — PM Dashboard API
Story: 2-12-pm-csm-dashboard-project-health-overview
       2-13-pm-dashboard-test-coverage-metrics
AC-30: GET /api/v1/projects/{project_id}/dashboard/overview
AC-31: GET /api/v1/projects/{project_id}/dashboard/coverage
AC-1:  week_over_week fields on coverage response
AC-2:  GET /api/v1/projects/{project_id}/dashboard/coverage/matrix
RBAC: require_project_role("owner", "admin", "qa-automation", "pm-csm")
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dashboard.schemas import (
    CoverageMatrixResponse,
    DashboardCoverageResponse,
    DashboardOverviewResponse,
)
from src.db import get_db
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.pm_dashboard_service import pm_dashboard_service
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(tags=["Dashboard"])

_DASHBOARD_ROLES = require_project_role("owner", "admin", "qa-automation", "pm-csm")


@router.get(
    "/api/v1/projects/{project_id}/dashboard/overview",
    response_model=DashboardOverviewResponse,
)
async def get_dashboard_overview(
    project_id: uuid.UUID,
    auth: tuple = _DASHBOARD_ROLES,
    db: AsyncSession = Depends(get_db),
) -> DashboardOverviewResponse:
    """AC-30: Return project health overview with coverage % and health status."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    data = await pm_dashboard_service.get_overview(db, schema_name, str(project_id))
    return DashboardOverviewResponse(**data)


@router.get(
    "/api/v1/projects/{project_id}/dashboard/coverage",
    response_model=DashboardCoverageResponse,
)
async def get_dashboard_coverage(
    project_id: uuid.UUID,
    auth: tuple = _DASHBOARD_ROLES,
    db: AsyncSession = Depends(get_db),
) -> DashboardCoverageResponse:
    """AC-31 + AC-1: Return 30-day coverage trend + lifetime totals + week-over-week delta."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    data = await pm_dashboard_service.get_coverage_trend(db, schema_name, str(project_id))
    return DashboardCoverageResponse(**data)


@router.get(
    "/api/v1/projects/{project_id}/dashboard/coverage/matrix",
    response_model=CoverageMatrixResponse,
)
async def get_coverage_matrix(
    project_id: uuid.UUID,
    auth: tuple = _DASHBOARD_ROLES,
    db: AsyncSession = Depends(get_db),
) -> CoverageMatrixResponse:
    """AC-2: Return latest coverage_matrix artifact parsed as requirement coverage list."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    data = await pm_dashboard_service.get_coverage_matrix(db, schema_name, str(project_id))
    return CoverageMatrixResponse(**data)
