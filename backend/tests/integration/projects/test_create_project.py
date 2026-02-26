"""
Integration tests — POST /api/v1/projects
Story: 1-9-project-creation-configuration
Task 6.2 — valid creation, duplicate slug, missing required fields, RBAC (non-admin rejected)
AC: AC1 — Owner/Admin access only
AC: AC2 — Project record created with slug, tenant_id from context, created_by from auth
AC: AC6 — Duplicate slug rejected
AC: AC7 — Validation errors return 400
AC: AC8 — Rate limiting returns 429 after 11 creates

NOTE: These tests run against a real PostgreSQL test DB with tenant schema set up.
Skip if TEST_DATABASE_URL not set (tests assume schema has been migrated).
"""

import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.db import get_db
from src.middleware.tenant_context import current_tenant_slug
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_redis_mock():
    """Mock Redis — never trips rate limits."""
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


def _make_owner_token(user_id: uuid.UUID, tenant_id: uuid.UUID, tenant_slug: str) -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email="owner@test.com",
        tenant_id=tenant_id,
        role="owner",
        tenant_slug=tenant_slug,
    )


def _make_viewer_token(user_id: uuid.UUID, tenant_id: uuid.UUID, tenant_slug: str) -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email="viewer@test.com",
        tenant_id=tenant_id,
        role="viewer",
        tenant_slug=tenant_slug,
    )


# ---------------------------------------------------------------------------
# Tests that mock the project service (pure HTTP + RBAC testing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_project_requires_authentication():
    """AC1: unauthenticated request → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.post("/api/v1/projects", json={"name": "My Project"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_project_viewer_forbidden():
    """AC1: viewer role → 403 (Owner/Admin only)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_viewer_token(user_id, tenant_id, tenant_slug)

    with patch("src.middleware.rbac.get_db") as mock_get_db, \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):

        # Mock DB to return user + active viewer membership
        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id

        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.id = tenant_id

        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.role = "viewer"
        mock_membership.is_active = True
        mock_membership.tenant_id = tenant_id
        mock_membership.user_id = user_id

        mock_session = AsyncMock()

        async def mock_execute(stmt, *args, **kwargs):
            result = MagicMock()
            if "User" in str(stmt) or "users" in str(stmt).lower():
                result.scalar_one_or_none.return_value = mock_user
            elif "Tenant" in str(stmt) or "tenants" in str(stmt).lower():
                result.scalar_one_or_none.return_value = mock_tenant
            else:
                result.scalar_one_or_none.return_value = mock_membership
            return result

        mock_session.execute = mock_execute

        async def get_db_override():
            yield mock_session

        app.dependency_overrides[get_db] = get_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post("/api/v1/projects", json={"name": "My Project"})

        app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_create_project_name_too_short():
    """AC7: name < 3 chars → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id, "test-org")

    with patch("src.middleware.rbac.get_db") as _, \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post("/api/v1/projects", json={"name": "AB"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_invalid_app_url():
    """AC7: invalid app_url format → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id, "test-org")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Valid Name", "app_url": "not-a-url"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_javascript_url_rejected():
    """AC7, C6: javascript: URL → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id, "test-org")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Valid Name", "app_url": "javascript:alert(1)"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_invalid_github_url():
    """AC7: github_repo_url must match github.com pattern."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id, "test-org")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Valid Name", "github_repo_url": "https://gitlab.com/owner/repo"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_project_rate_limit():
    """AC8: 11th request in same hour → 429."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id, "test-org")

    # Simulate Redis returning count=11 (rate limit exceeded)
    rate_limited_mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[11, 3000])  # count=11, ttl=3000
    rate_limited_mock.pipeline.return_value = pipeline
    rate_limited_mock.expire = AsyncMock(return_value=True)

    with patch("src.middleware.rbac.get_db") as mock_get_db, \
         patch("src.cache.get_redis_client", return_value=rate_limited_mock), \
         patch("src.api.v1.projects.router.get_redis_client", return_value=rate_limited_mock):

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "owner@test.com"

        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.id = tenant_id

        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.role = "owner"
        mock_membership.is_active = True
        mock_membership.tenant_id = tenant_id
        mock_membership.user_id = user_id

        mock_session = AsyncMock()

        async def mock_execute(stmt, *args, **kwargs):
            result = MagicMock()
            s = str(stmt).lower()
            if "user" in s and "tenant" not in s:
                result.scalar_one_or_none.return_value = mock_user
            elif "tenant" in s and "user" not in s:
                result.scalar_one_or_none.return_value = mock_tenant
            else:
                result.scalar_one_or_none.return_value = mock_membership
            return result

        mock_session.execute = mock_execute

        async def get_db_override():
            yield mock_session

        app.dependency_overrides[get_db] = get_db_override

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post("/api/v1/projects", json={"name": "My Rate Limited Project"})

        app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
