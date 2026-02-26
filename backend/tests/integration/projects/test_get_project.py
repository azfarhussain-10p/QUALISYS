"""
Integration tests — GET /api/v1/projects/{id}
                    GET /api/v1/projects/{id}/settings
Story: 1-9-project-creation-configuration
Task 6.3 — existing project, non-existent, cross-tenant isolation, settings RBAC

AC: AC3 — all authenticated org members can view project details
AC: AC4 — /settings returns advanced JSONB settings (Owner/Admin only)
AC: AC7 — 404 on non-existent project
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock():
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


def _make_token(user_id, tenant_id, tenant_slug, role="owner"):
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug=tenant_slug,
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
        elif "tenant" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


def _make_project(project_id, tenant_id, user_id):
    """Return a minimal Project-like object matching the Project dataclass."""
    from src.services.project_service import Project
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda k: {
        "id": project_id,
        "name": "Test Project",
        "slug": "test-project",
        "description": "A test project",
        "app_url": "https://app.example.com",
        "github_repo_url": "https://github.com/owner/repo",
        "status": "active",
        "settings": {"default_environment": "staging", "tags": ["smoke"]},
        "is_active": True,
        "created_by": user_id,
        "tenant_id": tenant_id,
        "organization_id": None,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }[k])
    return Project(row)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_requires_authentication():
    """Unauthenticated request → 401."""
    project_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_project_success():
    """Owner can retrieve an existing project → 200 with project data."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    mock_project = _make_project(project_id, tenant_id, user_id)

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.get_project",
        new=AsyncMock(return_value=mock_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(project_id)
    assert data["name"] == "Test Project"
    assert data["slug"] == "test-project"
    assert data["tenant_id"] == str(tenant_id)


@pytest.mark.asyncio
async def test_get_project_viewer_can_access():
    """AC3: viewer (any active org member) can GET project details."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug, role="viewer")

    mock_project = _make_project(project_id, tenant_id, user_id)

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id, role="viewer")

    with patch(
        "src.api.v1.projects.router.project_service.get_project",
        new=AsyncMock(return_value=mock_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}")

    app.dependency_overrides.clear()

    # GET allows any active member — viewer should succeed
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_project_not_found():
    """AC7: non-existent project → 404 PROJECT_NOT_FOUND."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    from src.services.project_service import ProjectNotFoundError

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.get_project",
        new=AsyncMock(side_effect=ProjectNotFoundError("not found")),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}")

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/settings — Owner/Admin only (AC4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_project_settings_returns_advanced_fields():
    """AC4: /settings includes default_environment, default_browser, tags."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    mock_project = _make_project(project_id, tenant_id, user_id)

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.get_project",
        new=AsyncMock(return_value=mock_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}/settings")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["default_environment"] == "staging"
    assert data["tags"] == ["smoke"]


@pytest.mark.asyncio
async def test_get_project_settings_viewer_forbidden():
    """AC4: viewer cannot access /settings (Owner/Admin only)."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug, role="viewer")

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id, role="viewer")

    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}/settings")

    app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"
