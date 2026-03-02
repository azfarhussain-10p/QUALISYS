"""
QUALISYS — PM Dashboard Schemas
Story: 2-12-pm-csm-dashboard-project-health-overview
       2-13-pm-dashboard-test-coverage-metrics
AC-30: DashboardOverviewResponse
AC-31: DashboardCoverageResponse, TrendPoint
AC-1:  week_over_week fields on DashboardCoverageResponse
AC-2:  RequirementCoverageItem, CoverageMatrixResponse
AC-3:  ProjectHealthItem, ProjectsHealthResponse
"""

from typing import Optional

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str                    # "YYYY-MM-DD"
    coverage_pct: Optional[float]


class DashboardOverviewResponse(BaseModel):
    coverage_pct: Optional[float]
    health_status: str           # "green" | "yellow" | "red" | "no_data"
    requirements_covered: int
    total_requirements: int
    artifact_count: int
    last_run_at: Optional[str]


class DashboardCoverageResponse(BaseModel):
    requirements_covered: int
    total_requirements: int
    coverage_pct: Optional[float]
    trend: list[TrendPoint]
    week_over_week_pct: Optional[float]   # AC-1 — signed delta, rounded 1dp
    week_over_week_direction: str          # AC-1 — "up"|"down"|"flat"|"no_data"


# AC-2 — Coverage matrix drill-down

class RequirementCoverageItem(BaseModel):
    name: str
    covered: bool
    test_count: int


class CoverageMatrixResponse(BaseModel):
    artifact_id: Optional[str]
    artifact_title: Optional[str]
    requirements: list[RequirementCoverageItem]
    generated_at: Optional[str]
    fallback_url: Optional[str]


# AC-3 — Multi-project health grid

class ProjectHealthItem(BaseModel):
    project_id: str
    project_name: str
    health_status: str           # "green" | "yellow" | "red" | "no_data"
    coverage_pct: Optional[float]
    artifact_count: int
    last_run_at: Optional[str]


class ProjectsHealthResponse(BaseModel):
    projects: list[ProjectHealthItem]
