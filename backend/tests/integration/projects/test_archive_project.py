"""
Integration tests — POST /api/v1/projects/{id}/archive
Story: 1-11-project-management-archive-delete-list
Task 6.3 — archive: valid, already archived (400), RBAC (non-admin 403)
AC: AC3 — archive sets is_active=false, returns 200 with updated project
AC: AC7 — cannot archive already-archived project → 400
AC: AC8 — rate limiting returns 429 on 11th operation
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service
from src.services.project_service import (
    ProjectAlreadyArchivedError,
    ProjectNotFoundError,
)


def _make_redis_mock(count: int = 1):
    """count=11 simulates rate limit hit."""
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
    return mock_session, mock_user


@pytest.mark.asyncio
async def test_archive_project_success():
    """AC3: valid archive → 200 with archived project."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, mock_user = _setup_auth_session(user_id, tenant_id, role="owner")

    from src.services.project_service import Project as _Project
    from unittest.mock import MagicMock as MM

    archived_row = MM()
    archived_row.__getitem__ = lambda self, key: {
        "id": project_id, "name": "Test", "slug": "test",
        "description": None, "app_url": None, "github_repo_url": None,
        "status": "archived", "settings": {}, "is_active": False,
        "created_by": None, "tenant_id": tenant_id, "organization_id": None,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }[key]
    mock_archived_project = _Project(archived_row)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.archive_project",
               return_value=mock_archived_project), \
         patch("src.api.v1.projects.router._get_schema_name", return_value="tenant_test"), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert data["status"] == "archived"


@pytest.mark.asyncio
async def test_archive_already_archived_returns_400():
    """AC7: archiving already-archived → 400 PROJECT_ALREADY_ARCHIVED."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.archive_project",
               side_effect=ProjectAlreadyArchivedError("Project 'Test' is already archived.")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PROJECT_ALREADY_ARCHIVED"


@pytest.mark.asyncio
async def test_archive_project_not_found_returns_404():
    """AC7: non-existent project → 404."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.archive_project",
               side_effect=ProjectNotFoundError("Not found")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_archive_project_non_admin_forbidden():
    """AC7: non-Admin role → 403 INSUFFICIENT_ROLE."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="viewer")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="viewer")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_archive_project_rate_limit_exceeded():
    """AC8: 11th archive operation → 429 with Retry-After."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.get_redis_client", return_value=_make_redis_mock(count=11)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
