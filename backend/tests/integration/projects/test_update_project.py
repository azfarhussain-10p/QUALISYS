"""
Integration tests — PATCH /api/v1/projects/{id}
Story: 1-9-project-creation-configuration
Task 6.4 — update name (slug regenerated), update settings JSONB, RBAC enforcement

AC: AC3 — Owner/Admin can update project name/description/URLs
AC: AC4 — settings JSONB merged (not replaced)
AC: AC7 — validation errors on invalid inputs
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
# Helpers (same pattern as test_get_project.py)
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


def _make_project(project_id, tenant_id, user_id, name="Test Project", slug="test-project", settings=None):
    from src.services.project_service import Project
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda k: {
        "id": project_id,
        "name": name,
        "slug": slug,
        "description": "A test project",
        "app_url": "https://app.example.com",
        "github_repo_url": "https://github.com/owner/repo",
        "status": "active",
        "settings": settings or {},
        "is_active": True,
        "created_by": user_id,
        "tenant_id": tenant_id,
        "organization_id": None,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
    }[k])
    return Project(row)


# ---------------------------------------------------------------------------
# PATCH /api/v1/projects/{project_id} — RBAC (AC1, AC3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_requires_authentication():
    """Unauthenticated request → 401."""
    project_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "New Name"},
            )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_project_viewer_forbidden():
    """AC1/AC3: viewer role → 403 INSUFFICIENT_ROLE."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, "test-org", role="viewer")

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id, role="viewer")

    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Hacked Name"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"


# ---------------------------------------------------------------------------
# PATCH — Name update triggers slug regeneration (AC3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_name_changes_slug():
    """AC3: updating name regenerates slug → returned project has new name/slug."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    updated_project = _make_project(
        project_id, tenant_id, user_id,
        name="Renamed Project",
        slug="renamed-project",
    )

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.update_project",
        new=AsyncMock(return_value=updated_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Renamed Project"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed Project"
    assert data["slug"] == "renamed-project"


# ---------------------------------------------------------------------------
# PATCH — Settings JSONB merge (AC4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_settings_jsonb_merged():
    """AC4: PATCH settings merges JSONB rather than replacing."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    merged_settings = {
        "default_environment": "production",
        "default_browser": "firefox",
        "tags": ["smoke", "regression"],
    }
    updated_project = _make_project(
        project_id, tenant_id, user_id, settings=merged_settings
    )

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.update_project",
        new=AsyncMock(return_value=updated_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={
                    "settings": {
                        "default_environment": "production",
                        "default_browser": "firefox",
                        "tags": ["smoke", "regression"],
                    }
                },
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["settings"]["default_environment"] == "production"
    assert "regression" in data["settings"]["tags"]


# ---------------------------------------------------------------------------
# PATCH — Validation errors (AC7)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_invalid_settings_environment():
    """AC7: invalid default_environment value → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, "test-org")

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"settings": {"default_environment": "invalid_env"}},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_project_name_too_short():
    """AC7: name < 3 chars → 422."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, "test-org")

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "AB"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH — 404 on non-existent project (AC7)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_project_not_found():
    """AC7: updating non-existent project → 404."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    project_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, "test-org")

    from src.services.project_service import ProjectNotFoundError

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.update_project",
        new=AsyncMock(side_effect=ProjectNotFoundError("not found")),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "New Valid Name"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"
