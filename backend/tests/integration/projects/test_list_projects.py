"""
Integration tests — GET /api/v1/projects (extended)
Story: 1-11-project-management-archive-delete-list
Task 6.2 — List projects with filters, membership filtering, pagination
AC: AC1 — Table columns, search, sort, pagination, 20/page
AC: AC2 — status filter: active (default), archived, all
AC: AC7 — invalid status filter returns 422
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service


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


def _make_owner_token(user_id, tenant_id, slug="test-org"):
    return token_service.create_access_token(
        user_id=user_id, email="owner@test.com",
        tenant_id=tenant_id, role="owner", tenant_slug=slug,
    )


def _setup_auth_mocks(user_id, tenant_id, role="owner"):
    """Return mocked DB that returns user + tenant + membership for RBAC."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = "owner@test.com"

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
async def test_list_projects_requires_auth():
    """AC1: unauthenticated → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.get("/api/v1/projects")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_projects_returns_paginated_response():
    """AC1: valid owner request returns PaginatedProjectsResponse with pagination metadata."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id)
    mock_session = _setup_auth_mocks(user_id, tenant_id)

    from src.services.project_service import PaginatedResult, ProjectWithMemberCount
    import datetime

    mock_project = MagicMock(spec=ProjectWithMemberCount)
    mock_project.to_dict.return_value = {
        "id": str(uuid.uuid4()), "name": "Test Project", "slug": "test-project",
        "description": None, "app_url": None, "github_repo_url": None,
        "status": "active", "settings": {}, "is_active": True,
        "created_by": None, "tenant_id": str(tenant_id), "organization_id": None,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "member_count": 2, "health": "—",
    }

    mock_result = PaginatedResult(
        data=[mock_project], page=1, per_page=20, total=1, total_pages=1
    )

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.list_projects", return_value=mock_result), \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get("/api/v1/projects")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "pagination" in body
    assert body["pagination"]["total"] == 1
    assert body["pagination"]["page"] == 1


@pytest.mark.asyncio
async def test_list_projects_invalid_status_filter():
    """AC7: invalid status filter → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.get("/api/v1/projects?status=invalid_value")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_invalid_sort_field():
    """AC1: invalid sort field → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_owner_token(user_id, tenant_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.get("/api/v1/projects?sort=invalid_sort")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_viewer_sees_only_assigned():
    """AC1, C7: non-Admin sees only assigned projects (service handles membership filter)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = token_service.create_access_token(
        user_id=user_id, email="viewer@test.com",
        tenant_id=tenant_id, role="viewer", tenant_slug="test-org",
    )
    mock_session = _setup_auth_mocks(user_id, tenant_id, role="viewer")

    from src.services.project_service import PaginatedResult

    mock_result = PaginatedResult(data=[], page=1, per_page=20, total=0, total_pages=1)

    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("src.api.v1.projects.router.project_service.list_projects", return_value=mock_result) as mock_list, \
         patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get("/api/v1/projects")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    # Verify list_projects was called with viewer's user_id for membership filtering
    mock_list.assert_awaited_once()
    call_kwargs = mock_list.call_args.kwargs
    assert call_kwargs["user_role"] == "viewer"
    assert call_kwargs["user_id"] == user_id
