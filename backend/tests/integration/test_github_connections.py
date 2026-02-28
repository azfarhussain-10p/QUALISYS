"""
Integration tests — GitHub Connection (Story 2-3)
Task 7.1 — 4 integration tests for GitHub connection endpoints.
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override)
  - Redis (cache + rate_limit)
  - GitHubConnectorService._validate_pat (httpx GitHub API)
  - clone_repo_task (background clone — not executed in tests)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
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


def _setup_db_session(
    user_id:    uuid.UUID,
    tenant_id:  uuid.UUID,
    project_id: uuid.UUID,
    role:       str = "owner",
    has_connection: bool = False,
    connection_id:  uuid.UUID = None,
    analysis_summary: dict = None,
):
    """Mock DB session for GitHub connection integration tests."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user           = MagicMock(spec=User)
    mock_user.id        = user_id
    mock_user.email     = f"{role}@test.com"

    mock_tenant         = MagicMock(spec=Tenant)
    mock_tenant.id      = tenant_id
    mock_tenant.slug    = "test-org"

    mock_membership             = MagicMock(spec=TenantUser)
    mock_membership.role        = role
    mock_membership.is_active   = True
    mock_membership.tenant_id   = tenant_id
    mock_membership.user_id     = user_id

    now    = datetime.now(timezone.utc)
    cid    = connection_id or uuid.uuid4()

    # Real dict so dict(row) works in get_connection()
    connection_row = {
        "id":               cid,
        "project_id":       project_id,
        "repo_url":         "https://github.com/owner/repo",
        "status":           "analyzed" if analysis_summary else "cloned",
        "routes_count":     len(analysis_summary.get("routes", [])) if analysis_summary else 0,
        "components_count": len(analysis_summary.get("components", [])) if analysis_summary else 0,
        "endpoints_count":  len(analysis_summary.get("endpoints", [])) if analysis_summary else 0,
        "analysis_summary": analysis_summary,
        "error_message":    None,
        "expires_at":       None,
        "created_at":       now,
        "updated_at":       now,
    }

    mock_session         = AsyncMock()
    mock_session.commit  = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result  = MagicMock()
        s       = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "select id from" in s and "github_connections" in s and "status not in" in s:
            # Conflict check: no active connection
            mappings = MagicMock()
            mappings.fetchone.return_value = None  # no conflict in connect tests
            result.mappings.return_value = mappings
        elif "select" in s and "github_connections" in s:
            # get_connection() SELECT: return real dict so dict(row) works
            mappings = MagicMock()
            mappings.fetchone.return_value = connection_row if has_connection else None
            result.mappings.return_value = mappings
        elif "insert" in s and "github_connections" in s:
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

class TestGitHubConnections:

    @pytest.mark.asyncio
    async def test_connect_repo_201(self):
        # Proves: POST /github with valid PAT → 201 and connection status='pending'.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, has_connection=False)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch(
                "src.services.github_connector_service.GitHubConnectorService._validate_pat",
                new_callable=AsyncMock,
            ):
                with patch("src.api.v1.github.router.clone_repo_task", new_callable=AsyncMock):
                    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                            async with AsyncClient(
                                transport=ASGITransport(app=app), base_url="http://test"
                            ) as c:
                                resp = await c.post(
                                    f"/api/v1/projects/{project_id}/github",
                                    json={"repo_url": "https://github.com/owner/repo", "pat": "ghp_valid123"},
                                    headers={"Authorization": f"Bearer {token}"},
                                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["repo_url"] == "https://github.com/owner/repo"

    @pytest.mark.asyncio
    async def test_connect_repo_invalid_pat_400(self):
        # Proves: POST /github with invalid PAT → 400 INVALID_TOKEN.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, has_connection=False)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch(
                "src.services.github_connector_service.GitHubConnectorService._validate_pat",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=400,
                    detail={"error": "INVALID_TOKEN", "message": "Invalid token"},
                ),
            ):
                with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                    with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as c:
                            resp = await c.post(
                                f"/api/v1/projects/{project_id}/github",
                                json={"repo_url": "https://github.com/owner/repo", "pat": "ghp_bad"},
                                headers={"Authorization": f"Bearer {token}"},
                            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_get_connection_200(self):
        # Proves: GET /github returns the connection with status and repo_url.
        user_id       = uuid.uuid4()
        tenant_id     = uuid.uuid4()
        project_id    = uuid.uuid4()
        connection_id = uuid.uuid4()
        token         = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id, has_connection=True, connection_id=connection_id
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/github",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cloned"
        assert "repo_url" in data

    @pytest.mark.asyncio
    async def test_get_connection_returns_analysis_summary(self):
        # Proves: GET /github for an 'analyzed' connection returns analysis_summary with framework/routes/components/endpoints keys (AC-11d).
        user_id       = uuid.uuid4()
        tenant_id     = uuid.uuid4()
        project_id    = uuid.uuid4()
        connection_id = uuid.uuid4()
        token         = _make_token(user_id, tenant_id, "owner")

        analysis_summary = {
            "framework":  "fastapi",
            "routes":     [{"method": "GET", "path": "/api/v1/users", "file": "backend/src/api/v1/users/router.py"}],
            "components": [{"name": "UserCard", "file": "web/src/components/UserCard.tsx"}],
            "endpoints":  [{"method": "GET", "path": "/api/v1/users", "file": "backend/src/api/v1/users/router.py"}],
        }

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            has_connection=True, connection_id=connection_id,
            analysis_summary=analysis_summary,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/github",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "analyzed"
        assert data["analysis_summary"] is not None
        summary = data["analysis_summary"]
        assert "framework" in summary
        assert "routes" in summary
        assert "components" in summary
        assert "endpoints" in summary
        assert summary["framework"] == "fastapi"
        assert len(summary["routes"]) == 1
        assert summary["routes"][0]["method"] == "GET"

    @pytest.mark.asyncio
    async def test_get_connection_404_when_none(self):
        # Proves: GET /github when no connection exists → 404 CONNECTION_NOT_FOUND.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, has_connection=False)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/github",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "CONNECTION_NOT_FOUND"
