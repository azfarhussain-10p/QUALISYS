"""
Integration tests — PM Dashboard endpoints (Story 2-12, 2-13)
DoD: every test has a one-line comment stating the behaviour proved.

Tests mock:
  - DB session (get_db override, AsyncMock pattern from test_artifacts.py)
  - Redis (patched get_redis_client — cache miss path for all tests)
  - RBAC (token with tenant context)

AC-30: GET /api/v1/projects/{project_id}/dashboard/overview
AC-31: GET /api/v1/projects/{project_id}/dashboard/coverage
AC-32: GET /api/v1/events/dashboard/{project_id} (SSE stream)
AC-1:  week_over_week fields on coverage response
AC-2:  GET /api/v1/projects/{project_id}/dashboard/coverage/matrix
AC-3:  GET /api/v1/orgs/{org_id}/dashboard/projects
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)


def _make_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str = "owner",
) -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
    )


def _setup_db_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    role: str = "owner",
    *,
    overview_agg_row=None,
    last_run_row=None,
    trend_rows=None,
    totals_row=None,
    last_week_row=None,
    matrix_row=None,
    project_rows=None,
    batch_project_agg_rows=None,
    batch_run_rows=None,
    project_exists: bool = True,
):
    """
    Build an AsyncMock DB session that routes queries by SQL content.
    Covers: RBAC lookups + overview/coverage/SSE/matrix/projects dashboard queries.

    Routing priority (most specific first):
      - public schema lookups → RBAC
      - "distinct on" → batch agent-run (get_all_projects_health O1 fix)
      - "artifact_versions" → coverage matrix JOIN
      - "group by project_id" → batch artifact agg (get_all_projects_health O1 fix)
      - "group by" + "date(" → daily trend (get_coverage_trend)
      - "select id, name" + "order by name" → project list (get_all_projects_health)
      - "artifact_count" → single-project overview agg (_compute_overview)
      - "interval '7 days'" → week-over-week secondary query
      - "reqs_covered" → lifetime totals query
      - "agent_runs" + "order by" → single-project last agent run (limit 1)
    """
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = f"{role}@test.com"

    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id
    mock_tenant.slug = "test-org"

    mock_membership = MagicMock(spec=TenantUser)
    mock_membership.role = role
    mock_membership.is_active = True
    mock_membership.tenant_id = tenant_id
    mock_membership.user_id = user_id

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "select id from" in s and "projects" in s:
            # SSE project existence check
            result.scalar_one_or_none.return_value = str(project_id) if project_exists else None
        elif "distinct on" in s and "agent_runs" in s:
            # get_all_projects_health — batch last-run per project (O1 fix)
            result.fetchall.return_value = batch_run_rows or []
        elif "artifact_versions" in s and "coverage_matrix" in s:
            # get_coverage_matrix — JOIN artifacts + artifact_versions
            result.fetchone.return_value = matrix_row
        elif "group by project_id" in s and "artifacts" in s:
            # get_all_projects_health — batch artifact aggregation (O1 fix)
            result.fetchall.return_value = batch_project_agg_rows or []
        elif "group by" in s and "date(" in s and "artifacts" in s:
            # get_coverage_trend — daily grouped query
            result.fetchall.return_value = trend_rows or []
        elif "select id, name" in s and "projects" in s and "order by name" in s:
            # get_all_projects_health — project list query
            result.fetchall.return_value = project_rows or []
        elif "artifact_count" in s:
            # _compute_overview — single-project aggregation
            result.fetchone.return_value = overview_agg_row
        elif "interval '7 days'" in s:
            # get_coverage_trend — week-over-week secondary query
            lw = last_week_row
            if lw is None:
                lw = MagicMock()
                lw.covered = 0
                lw.total = 0
            result.fetchone.return_value = lw
        elif "reqs_covered" in s and "reqs_total" in s:
            # get_coverage_trend — lifetime totals query
            result.fetchone.return_value = totals_row
        elif "agent_runs" in s and "created_at" in s and "order by" in s:
            # _compute_overview — single-project last agent run (limit 1)
            result.fetchone.return_value = last_run_row
        else:
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


def _no_cache():
    """Return an AsyncMock Redis client that always misses on get()."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    return mock_redis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardOverview:

    @pytest.mark.asyncio
    async def test_get_overview_200(self):
        # Proves: GET /dashboard/overview with seeded coverage_matrix artifact → 200,
        # coverage_pct == 80.0, health_status == "green".
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        # Aggregate row: 8 of 10 requirements covered → 80%
        agg_row = MagicMock()
        agg_row.artifact_count = 1
        agg_row.reqs_covered = 8
        agg_row.reqs_total = 10
        agg_row.last_artifact_at = _NOW

        last_run = MagicMock()
        last_run.created_at = _NOW

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            overview_agg_row=agg_row,
            last_run_row=last_run,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/overview")

            assert resp.status_code == 200
            data = resp.json()
            assert data["coverage_pct"] == 80.0
            assert data["health_status"] == "green"
            assert data["requirements_covered"] == 8
            assert data["total_requirements"] == 10
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_overview_no_data(self):
        # Proves: GET /dashboard/overview with no coverage artifacts → 200,
        # health_status == "no_data", coverage_pct == None.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        # Zero-row aggregation — no coverage_matrix artifacts
        agg_row = MagicMock()
        agg_row.artifact_count = 0
        agg_row.reqs_covered = 0
        agg_row.reqs_total = 0
        agg_row.last_artifact_at = None

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            overview_agg_row=agg_row,
            last_run_row=None,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/overview")

            assert resp.status_code == 200
            data = resp.json()
            assert data["health_status"] == "no_data"
            assert data["coverage_pct"] is None
            assert data["last_run_at"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_overview_rbac_401(self):
        # Proves: GET /dashboard/overview without auth header → 401 Unauthorized.
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/overview")

        assert resp.status_code == 401


class TestDashboardCoverage:

    @pytest.mark.asyncio
    async def test_get_coverage_trend_200(self):
        # Proves: GET /dashboard/coverage with seeded artifacts on 3 days → 200,
        # trend list has exactly 30 items, requirements_covered > 0.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        from datetime import date, timedelta

        # 3 trend rows on different days
        today = date.today()
        trend_rows = []
        for i in range(3):
            row = MagicMock()
            row.day = today - timedelta(days=i)
            row.covered = 6
            row.total = 10
            trend_rows.append(row)

        # Lifetime totals
        totals_row = MagicMock()
        totals_row.reqs_covered = 18
        totals_row.reqs_total = 30

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            trend_rows=trend_rows,
            totals_row=totals_row,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/coverage")

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["trend"]) == 30
            assert data["requirements_covered"] == 18
            assert data["total_requirements"] == 30
            assert data["coverage_pct"] == 60.0
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestDashboardCoverageWeekOverWeek:

    @pytest.mark.asyncio
    async def test_get_coverage_trend_includes_week_over_week_200(self):
        # Proves: GET /dashboard/coverage response includes week_over_week_pct and
        # week_over_week_direction fields when artifacts older than 7 days exist.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        totals_row = MagicMock()
        totals_row.reqs_covered = 18
        totals_row.reqs_total = 30

        # Last week had 12/30 covered → 40%  (current 60%, delta = +20%)
        last_week_row = MagicMock()
        last_week_row.covered = 12
        last_week_row.total = 30

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            trend_rows=[],
            totals_row=totals_row,
            last_week_row=last_week_row,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/coverage")

            assert resp.status_code == 200
            data = resp.json()
            assert "week_over_week_pct" in data
            assert "week_over_week_direction" in data
            # current 18/30 = 60.0%, last_week 12/30 = 40.0%, delta = +20.0 → "up"
            assert data["week_over_week_pct"] == 20.0
            assert data["week_over_week_direction"] == "up"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_coverage_trend_no_data_direction(self):
        # Proves: week_over_week_direction == "no_data" when no artifacts are older than 7 days.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        totals_row = MagicMock()
        totals_row.reqs_covered = 8
        totals_row.reqs_total = 10

        # last_week_row with zero total → no_data
        last_week_row = MagicMock()
        last_week_row.covered = 0
        last_week_row.total = 0

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            trend_rows=[],
            totals_row=totals_row,
            last_week_row=last_week_row,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/projects/{project_id}/dashboard/coverage")

            assert resp.status_code == 200
            data = resp.json()
            assert data["week_over_week_direction"] == "no_data"
            assert data["week_over_week_pct"] is None
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestDashboardCoverageMatrix:

    @pytest.mark.asyncio
    async def test_get_coverage_matrix_200(self):
        # Proves: GET /dashboard/coverage/matrix → 200; parseable artifact returns requirements list.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        matrix_row = MagicMock()
        matrix_row.id = uuid.uuid4()
        matrix_row.title = "Coverage Matrix v1"
        matrix_row.created_at = _NOW
        matrix_row.content = json.dumps(
            {
                "requirements": [
                    {"name": "REQ-001", "covered": True, "test_count": 3},
                    {"name": "REQ-002", "covered": False, "test_count": 0},
                ]
            }
        )

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            matrix_row=matrix_row,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(
                        f"/api/v1/projects/{project_id}/dashboard/coverage/matrix"
                    )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data["requirements"]) == 2
            assert data["requirements"][0]["name"] == "REQ-001"
            assert data["requirements"][0]["covered"] is True
            assert data["artifact_id"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_coverage_matrix_no_artifact_200(self):
        # Proves: GET /dashboard/coverage/matrix → 200 with empty requirements + fallback_url
        # when no coverage_matrix artifact exists.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            matrix_row=None,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(
                        f"/api/v1/projects/{project_id}/dashboard/coverage/matrix"
                    )

            assert resp.status_code == 200
            data = resp.json()
            assert data["requirements"] == []
            assert data["fallback_url"] is not None
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_coverage_matrix_rbac_401(self):
        # Proves: GET /dashboard/coverage/matrix without auth → 401 Unauthorized.
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"/api/v1/projects/{project_id}/dashboard/coverage/matrix"
            )

        assert resp.status_code == 401


class TestProjectsHealthGrid:

    @pytest.mark.asyncio
    async def test_get_projects_health_200(self):
        # Proves: GET /api/v1/orgs/{org_id}/dashboard/projects with valid owner auth → 200;
        # response has "projects" key; project shows health_status and coverage_pct from batch queries.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        org_id = tenant_id
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        # Project list returns one project
        p_row = MagicMock()
        p_row.id = project_id
        p_row.name = "Test Project"

        # Batch artifact aggregation row for the project (8/10 covered → 80% → green)
        batch_agg = MagicMock()
        batch_agg.project_id = project_id
        batch_agg.artifact_count = 1
        batch_agg.reqs_covered = 8
        batch_agg.reqs_total = 10

        # Batch last-run row (no agent runs for this project)
        # batch_run_rows=[] → last_run_at will be None

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            project_rows=[p_row],
            batch_project_agg_rows=[batch_agg],
            batch_run_rows=[],
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.services.pm_dashboard_service.get_redis_client", return_value=_no_cache()):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    cookies={"access_token": token},
                ) as client:
                    resp = await client.get(f"/api/v1/orgs/{org_id}/dashboard/projects")

            assert resp.status_code == 200
            data = resp.json()
            assert "projects" in data
            assert isinstance(data["projects"], list)
            assert len(data["projects"]) == 1
            assert data["projects"][0]["project_name"] == "Test Project"
            assert data["projects"][0]["coverage_pct"] == 80.0
            assert data["projects"][0]["health_status"] == "green"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_projects_health_rbac_401(self):
        # Proves: GET /api/v1/orgs/{org_id}/dashboard/projects without auth → 401 Unauthorized.
        org_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"/api/v1/orgs/{org_id}/dashboard/projects")

        assert resp.status_code == 401


class TestDashboardSSE:

    @pytest.mark.asyncio
    async def test_dashboard_sse_endpoint_200(self):
        # Proves: GET /api/v1/events/dashboard/{project_id} with valid auth → 200
        # and Content-Type text/event-stream (project existence validated first).
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            project_exists=True,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                async with client.stream(
                    "GET", f"/api/v1/events/dashboard/{project_id}"
                ) as resp:
                    assert resp.status_code == 200
                    assert "text/event-stream" in resp.headers.get("content-type", "")
        finally:
            app.dependency_overrides.pop(get_db, None)
