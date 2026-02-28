"""
Integration tests — DOM Crawling endpoints (Story 2-5)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override)
  - Redis (cache + rate_limit)
  - crawl_task (background crawl — not executed in tests)
"""

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


def _make_crawl_row(crawl_id: uuid.UUID, project_id: uuid.UUID, status: str = "pending") -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id":            str(crawl_id),
        "project_id":    str(project_id),
        "target_url":    "https://app.example.com",
        "status":        status,
        "pages_crawled": 0,
        "forms_found":   0,
        "links_found":   0,
        "crawl_data":    None,
        "error_message": None,
        "started_at":    None,
        "completed_at":  None,
        "created_at":    now,
    }


def _setup_db_session(
    user_id:    uuid.UUID,
    tenant_id:  uuid.UUID,
    project_id: uuid.UUID,
    role:       str = "owner",
    has_active_crawl: bool = False,
    crawl_row:  dict = None,
    crawl_rows: list = None,
):
    """Mock DB session for crawl integration tests."""
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
        elif "status in" in s and "crawl_sessions" in s:
            # Concurrent check
            mappings.fetchone.return_value = _make_crawl_row(uuid.uuid4(), project_id) if has_active_crawl else None
            result.mappings.return_value = mappings
        elif "order by created_at desc limit 50" in s:
            # list_crawls
            mappings.fetchall.return_value = crawl_rows or []
            result.mappings.return_value = mappings
        elif "select" in s and "crawl_sessions" in s:
            # get_crawl single lookup
            mappings.fetchone.return_value = crawl_row
            result.mappings.return_value = mappings
        elif "insert" in s and "crawl_sessions" in s:
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

class TestCrawlEndpoints:

    @pytest.mark.asyncio
    async def test_start_crawl_201(self):
        # Proves: POST /crawls with valid target_url → 201 and status='pending' in response.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, has_active_crawl=False)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.api.v1.crawls.router.crawl_task", new_callable=AsyncMock):
                with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                    with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as c:
                            resp = await c.post(
                                f"/api/v1/projects/{project_id}/crawls",
                                json={"target_url": "https://app.example.com"},
                                headers={"Authorization": f"Bearer {token}"},
                            )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["target_url"] == "https://app.example.com"

    @pytest.mark.asyncio
    async def test_start_crawl_conflict_409(self):
        # Proves: POST /crawls when active session exists → 409 CRAWL_ALREADY_ACTIVE.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, has_active_crawl=True)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.post(
                            f"/api/v1/projects/{project_id}/crawls",
                            json={"target_url": "https://app.example.com"},
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 409
        assert resp.json()["detail"]["error"] == "CRAWL_ALREADY_ACTIVE"

    @pytest.mark.asyncio
    async def test_list_crawls_200(self):
        # Proves: GET /crawls with sessions seeded → 200 and list returned.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        crawl_id   = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        rows = [_make_crawl_row(crawl_id, project_id, status="completed")]
        get_db_override = _setup_db_session(user_id, tenant_id, project_id, crawl_rows=rows)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/crawls",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_crawl_404_when_none(self):
        # Proves: GET /crawls/{unknown_id} when no session exists → 404 CRAWL_NOT_FOUND.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        crawl_id   = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, crawl_row=None)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/crawls/{crawl_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "CRAWL_NOT_FOUND"
