"""
Integration tests — POST /api/v1/projects/{id}/restore
Story: 1-11-project-management-archive-delete-list
Task 6.4 — restore: valid, not archived (400), RBAC (non-admin 403)
AC: AC4 — restore sets is_active=true, returns 200 with updated project
AC: AC7 — cannot restore active project → 400
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
    ProjectNotArchivedError,
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
async def test_restore_project_success():
    """AC4: valid restore → 200 with restored project (is_active=True, status='active')."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    from src.services.project_service import Project as _Project
    from unittest.mock import MagicMock as MM

    restored_row = MM()
    restored_row.__getitem__ = lambda self, key: {
        "id": project_id, "name": "Test", "slug": "test",
        "description": None, "app_url": None, "github_repo_url": None,
        "status": "active", "settings": {}, "is_active": True,
        "created_by": None, "tenant_id": tenant_id, "organization_id": None,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    }[key]
    mock_restored_project = _Project(restored_row)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.restore_project",
               return_value=mock_restored_project), \
         patch("src.api.v1.projects.router._get_schema_name", return_value="tenant_test"), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is True
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_restore_active_project_returns_400():
    """AC7: restoring active (non-archived) project → 400 PROJECT_NOT_ARCHIVED."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.restore_project",
               side_effect=ProjectNotArchivedError("Project 'Test' is not archived.")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "PROJECT_NOT_ARCHIVED"


@pytest.mark.asyncio
async def test_restore_project_not_found_returns_404():
    """AC7: non-existent project → 404."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.restore_project",
               side_effect=ProjectNotFoundError("Not found")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_project_non_admin_forbidden():
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
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_restore_project_rate_limit_exceeded():
    """AC8: 11th restore operation → 429 with Retry-After."""
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
            resp = await client.post(f"/api/v1/projects/{project_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
