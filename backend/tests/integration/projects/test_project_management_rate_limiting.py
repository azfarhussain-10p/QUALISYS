"""
Integration tests — Rate Limiting for Project Management Operations
Story: 1-11-project-management-archive-delete-list
Task 6.8 — 11th operation (archive/restore/delete) returns 429 with Retry-After
AC: AC8 — archive/restore/delete rate-limited to 10/org/hour (key: rate:project_destroy:{tenant_id})
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock(count: int = 1):
    """
    Build a redis mock that returns `count` on pipeline.execute()[0].
    count > 10 triggers the 429 rate limit in _check_project_destroy_rate_limit.
    """
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[count, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr = AsyncMock(return_value=count)
    mock.expire = AsyncMock(return_value=True)
    return mock


def _make_token(user_id, tenant_id, role="owner"):
    return token_service.create_access_token(
        user_id=user_id, email=f"{role}@test.com",
        tenant_id=tenant_id, role=role, tenant_slug="test-org",
    )


def _setup_auth_session(user_id, tenant_id, role="owner"):
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = f"{role}@test.com"

    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id

    mock_membership = MagicMock(spec=TenantUser)
    mock_membership.role = role
    mock_membership.is_active = True
    mock_membership.tenant_id = tenant_id
    mock_membership.user_id = user_id

    mock_session = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()
        if "user" in s and "tenant" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute
    return mock_session


# ---------------------------------------------------------------------------
# Rate limit tests — archive endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_under_rate_limit_allowed():
    """First 10 archive ops (count <= 10) → not rate-limited."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id)
    mock_session = _setup_auth_session(user_id, tenant_id)

    from src.services.project_service import Project as _Project
    from unittest.mock import MagicMock as MM

    row = MM()
    row.__getitem__ = lambda self, key: {
        "id": project_id, "name": "T", "slug": "t",
        "description": None, "app_url": None, "github_repo_url": None,
        "status": "archived", "settings": {}, "is_active": False,
        "created_by": None, "tenant_id": tenant_id, "organization_id": None,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }[key]

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.archive_project",
               return_value=_Project(row)), \
         patch("src.api.v1.projects.router._get_schema_name", return_value="tenant_test"), \
         patch("src.api.v1.projects.router.get_redis_client", return_value=_make_redis_mock(count=10)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 200  # count=10 is the limit, not exceeded


@pytest.mark.asyncio
async def test_archive_exceeds_rate_limit_returns_429():
    """11th archive op (count=11 > 10) → 429 RATE_LIMIT_EXCEEDED."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id)
    mock_session = _setup_auth_session(user_id, tenant_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.get_redis_client", return_value=_make_redis_mock(count=11)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_restore_exceeds_rate_limit_returns_429():
    """11th restore op → 429 with Retry-After. Same rate key as archive/delete."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id)
    mock_session = _setup_auth_session(user_id, tenant_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.get_redis_client", return_value=_make_redis_mock(count=11)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_delete_exceeds_rate_limit_returns_429():
    """11th delete op → 429 with Retry-After."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id)
    mock_session = _setup_auth_session(user_id, tenant_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.get_redis_client", return_value=_make_redis_mock(count=11)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.delete(f"/api/v1/projects/{project_id}")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp.headers


@pytest.mark.asyncio
async def test_rate_limit_retry_after_header_is_positive_integer():
    """AC8: Retry-After header value is a positive integer (seconds until reset)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id)
    mock_session = _setup_auth_session(user_id, tenant_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    # ttl=1800 seconds remaining in rate window
    rate_mock = _make_redis_mock(count=11)
    rate_mock.pipeline.return_value.execute = AsyncMock(return_value=[11, 1800])

    with patch("src.api.v1.projects.router.get_redis_client", return_value=rate_mock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    retry_after = resp.headers.get("Retry-After", "0")
    assert retry_after.isdigit(), f"Retry-After should be integer, got: {retry_after!r}"
    assert int(retry_after) > 0
