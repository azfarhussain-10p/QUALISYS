"""
Integration tests — Tenant Isolation for Project List, Archive, Delete
Story: 1-11-project-management-archive-delete-list
Task 6.7 — project list, archive, delete scoped to tenant
AC: Architecture — schema-per-tenant ensures all operations are tenant-isolated.
JWT tenant_slug determines which schema is queried — cross-tenant access returns 404.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service
from src.services.project_service import (
    ProjectNotFoundError,
    PaginatedResult,
)


def _make_redis_mock():
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


def _make_token(user_id, tenant_id, tenant_slug, role="owner"):
    return token_service.create_access_token(
        user_id=user_id, email=f"{role}@test.com",
        tenant_id=tenant_id, role=role, tenant_slug=tenant_slug,
    )


def _make_rbac_db_mock(user_id, tenant_id, role="owner"):
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


@pytest.mark.asyncio
async def test_list_projects_scoped_to_requesting_tenant():
    """
    AC2/Architecture: list_projects called with the authenticated user's tenant_id,
    not any other tenant. Service queries requesting tenant's schema only.
    """
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    other_tenant_id = uuid.uuid4()

    token = _make_token(user_id, tenant_id, "tenant-a-org")
    mock_session = _make_rbac_db_mock(user_id, tenant_id)

    mock_result = PaginatedResult(data=[], page=1, per_page=20, total=0, total_pages=1)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.list_projects",
               return_value=mock_result) as mock_list, \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get("/api/v1/projects")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    # Verify service was called with the JWT tenant, not other_tenant_id
    call_kwargs = mock_list.call_args.kwargs
    assert call_kwargs["tenant_id"] == tenant_id
    assert call_kwargs["tenant_id"] != other_tenant_id


@pytest.mark.asyncio
async def test_archive_project_in_different_tenant_returns_404():
    """
    Tenant isolation on archive: a user in tenant B cannot archive a project
    that lives in tenant A's schema. Service returns ProjectNotFoundError.
    """
    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    project_a_id = uuid.uuid4()  # belongs to tenant A

    token_b = _make_token(user_b_id, tenant_b_id, "tenant-b-org")
    mock_session = _make_rbac_db_mock(user_b_id, tenant_b_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.archive_project",
               side_effect=ProjectNotFoundError("project not in tenant B schema")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_a_id}/archive")

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_delete_project_in_different_tenant_returns_404():
    """
    Tenant isolation on delete: a user in tenant B cannot delete a project
    that lives in tenant A's schema. Service returns ProjectNotFoundError.
    """
    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    project_a_id = uuid.uuid4()  # belongs to tenant A

    token_b = _make_token(user_b_id, tenant_b_id, "tenant-b-org")
    mock_session = _make_rbac_db_mock(user_b_id, tenant_b_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.delete_project",
               side_effect=ProjectNotFoundError("project not in tenant B schema")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            resp = await client.delete(f"/api/v1/projects/{project_a_id}")

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_restore_project_in_different_tenant_returns_404():
    """
    Tenant isolation on restore: a user in tenant B cannot restore a project
    from tenant A's schema.
    """
    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    project_a_id = uuid.uuid4()

    token_b = _make_token(user_b_id, tenant_b_id, "tenant-b-org")
    mock_session = _make_rbac_db_mock(user_b_id, tenant_b_id)

    app.dependency_overrides[get_db] = lambda: mock_session

    from src.services.project_service import ProjectNotFoundError as _PNFE
    with patch("src.api.v1.projects.router.project_service.restore_project",
               side_effect=_PNFE("not in tenant B")), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_a_id}/restore")

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_unauthenticated_list_returns_401():
    """No JWT → 401 for list endpoint (tenant isolation starts with authentication)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_archive_returns_401():
    """No JWT → 401 for archive endpoint."""
    project_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_delete_returns_401():
    """No JWT → 401 for delete endpoint."""
    project_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 401
