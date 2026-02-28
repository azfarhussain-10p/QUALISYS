"""
Integration tests — Agent Run endpoints (Story 2-6)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override)
  - Redis (cache + rate_limit)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str = "owner") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
    )


def _make_redis_mock():
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr    = MagicMock(return_value=pipeline)
    pipeline.expire  = MagicMock(return_value=pipeline)
    pipeline.ttl     = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr   = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.get    = AsyncMock(return_value=None)
    mock.set    = AsyncMock(return_value=True)
    mock.eval   = AsyncMock(return_value=[100, 2592000])
    return mock


def _make_run_row(run_id: uuid.UUID, project_id: uuid.UUID, status: str = "queued") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id":              str(run_id),
        "project_id":      str(project_id),
        "pipeline_mode":   "sequential",
        "agents_selected": ["ba_consultant"],
        "status":          status,
        "total_tokens":    0,
        "total_cost_usd":  0.0,
        "started_at":      None,
        "completed_at":    None,
        "error_message":   None,
        "created_at":      now,
    }


def _setup_db_session(
    user_id:    uuid.UUID,
    tenant_id:  uuid.UUID,
    project_id: uuid.UUID,
    role:       str = "owner",
    run_row:    dict = None,
    run_rows:   list = None,
    step_rows:  list = None,
):
    """Mock DB session for agent-run integration tests."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user            = MagicMock(spec=User)
    mock_user.id         = user_id
    mock_user.email      = f"{role}@test.com"

    mock_tenant          = MagicMock(spec=Tenant)
    mock_tenant.id       = tenant_id
    mock_tenant.slug     = "test-org"

    mock_membership              = MagicMock(spec=TenantUser)
    mock_membership.role         = role
    mock_membership.is_active    = True
    mock_membership.tenant_id    = tenant_id
    mock_membership.user_id      = user_id

    mock_session         = AsyncMock()
    mock_session.commit  = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result   = MagicMock()
        mappings = MagicMock()
        s        = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "order by created_at desc limit 20" in s:
            # list_runs
            mappings.fetchall.return_value = run_rows or []
            result.mappings.return_value = mappings
        elif "agent_run_steps" in s and "where run_id" in s:
            mappings.fetchall.return_value = step_rows or []
            result.mappings.return_value = mappings
        elif "select" in s and "agent_runs" in s:
            # get_run single lookup
            mappings.fetchone.return_value = run_row
            result.mappings.return_value = mappings
        elif "insert" in s and ("agent_runs" in s or "agent_run_steps" in s):
            result.rowcount = 1
        else:
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentEndpoints:

    @pytest.mark.asyncio
    async def test_list_agents_200(self):
        # Proves: GET /api/v1/agents returns 200 with list of 3 agent definitions.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.get("/api/v1/agents")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        types = {a["agent_type"] for a in data}
        assert types == {"ba_consultant", "qa_consultant", "automation_consultant"}

    @pytest.mark.asyncio
    async def test_start_run_201(self):
        # Proves: POST /agent-runs with valid agents → 201 and status='queued' in response.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with __import__("unittest.mock", fromlist=["patch"]).patch(
                "src.cache.get_redis_client", return_value=_make_redis_mock()
            ):
                with __import__("unittest.mock", fromlist=["patch"]).patch(
                    "src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()
                ):
                    with __import__("unittest.mock", fromlist=["patch"]).patch(
                        "src.services.token_budget_service.get_redis_client",
                        return_value=_make_redis_mock(),
                    ):
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as c:
                            resp = await c.post(
                                f"/api/v1/projects/{project_id}/agent-runs",
                                json={"agents_selected": ["ba_consultant", "qa_consultant"]},
                                headers={"Authorization": f"Bearer {token}"},
                            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "queued"
        assert "ba_consultant" in data["agents_selected"]

    @pytest.mark.asyncio
    async def test_start_run_invalid_agents_400(self):
        # Proves: POST /agent-runs with unknown agent_type → 400 INVALID_AGENT_TYPE.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with __import__("unittest.mock", fromlist=["patch"]).patch(
                "src.cache.get_redis_client", return_value=_make_redis_mock()
            ):
                with __import__("unittest.mock", fromlist=["patch"]).patch(
                    "src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()
                ):
                    with __import__("unittest.mock", fromlist=["patch"]).patch(
                        "src.services.token_budget_service.get_redis_client",
                        return_value=_make_redis_mock(),
                    ):
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as c:
                            resp = await c.post(
                                f"/api/v1/projects/{project_id}/agent-runs",
                                json={"agents_selected": ["not_a_real_agent"]},
                                headers={"Authorization": f"Bearer {token}"},
                            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "INVALID_AGENT_TYPE"

    @pytest.mark.asyncio
    async def test_list_runs_200(self):
        # Proves: GET /agent-runs with seeded rows → 200 and list returned.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        run_id     = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        rows = [_make_run_row(run_id, project_id, status="queued")]
        get_db_override = _setup_db_session(user_id, tenant_id, project_id, run_rows=rows)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with __import__("unittest.mock", fromlist=["patch"]).patch(
                "src.cache.get_redis_client", return_value=_make_redis_mock()
            ):
                with __import__("unittest.mock", fromlist=["patch"]).patch(
                    "src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/agent-runs",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_run_404(self):
        # Proves: GET /agent-runs/{unknown_id} when no run exists → 404 RUN_NOT_FOUND.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        run_id     = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, run_row=None)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with __import__("unittest.mock", fromlist=["patch"]).patch(
                "src.cache.get_redis_client", return_value=_make_redis_mock()
            ):
                with __import__("unittest.mock", fromlist=["patch"]).patch(
                    "src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/agent-runs/{run_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "RUN_NOT_FOUND"
