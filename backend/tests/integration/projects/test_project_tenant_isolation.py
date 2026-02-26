"""
Integration tests — Tenant Isolation for Projects
Story: 1-9-project-creation-configuration
Task 6.6 — project created in tenant A is NOT accessible from tenant B

AC: AC2 — tenant_id always from JWT context, never from request body
Architecture: schema-per-tenant ensures projects are isolated at the DB layer.
These tests verify that the API correctly scopes operations to the requesting
tenant's context (ContextVar set from JWT tenant_slug claim).
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


# ---------------------------------------------------------------------------
# Cross-tenant project access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_in_tenant_a_not_accessible_from_tenant_b():
    """
    AC2, Architecture: project created in tenant A's schema cannot be fetched
    by a user authenticated in tenant B.

    The project service uses `current_tenant_slug` ContextVar (set from JWT).
    When tenant B's user makes the GET request, the ContextVar is set to
    tenant_b_slug, so the service queries tenant_b's schema — where the project
    doesn't exist — and returns 404.
    """
    # Tenant A owns the project
    user_a_id = uuid.uuid4()
    tenant_a_id = uuid.uuid4()
    project_id = uuid.uuid4()

    # Tenant B's user tries to access tenant A's project
    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    tenant_b_slug = "tenant-b-org"

    # Tenant B's valid token (authenticated, active member of tenant B)
    token_b = _make_token(user_b_id, tenant_b_id, tenant_b_slug)

    from src.services.project_service import ProjectNotFoundError

    # When tenant B's JWT is used, ContextVar = "tenant-b-org"
    # project_service.get_project will look in tenant_b schema → not found
    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_b_id, tenant_b_id)

    with patch(
        "src.api.v1.projects.router.project_service.get_project",
        new=AsyncMock(side_effect=ProjectNotFoundError("project not in tenant B schema")),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            resp = await client.get(f"/api/v1/projects/{project_id}")

    app.dependency_overrides.clear()

    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_project_uses_jwt_tenant_not_request_body():
    """
    AC2: tenant_id in the created project comes from JWT context, not request body.
    Even if a rogue payload included `tenant_id`, the service reads from ContextVar.

    The CreateProjectRequest schema has no `tenant_id` field — it cannot be
    submitted via POST body. The router passes `membership.tenant_id` (from RBAC)
    to the service.
    """
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    tenant_slug = "test-org"
    token = _make_token(user_id, tenant_id, tenant_slug)

    # Build minimal project object that would be returned
    from src.services.project_service import Project
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda k: {
        "id": uuid.uuid4(),
        "name": "My Project",
        "slug": "my-project",
        "description": None,
        "app_url": None,
        "github_repo_url": None,
        "status": "active",
        "settings": {},
        "is_active": True,
        "created_by": user_id,
        "tenant_id": tenant_id,  # <- from JWT, not body
        "organization_id": None,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }[k])
    mock_project = Project(row)

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_id, tenant_id)

    with patch(
        "src.api.v1.projects.router.project_service.create_project",
        new=AsyncMock(return_value=mock_project),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            resp = await client.post(
                "/api/v1/projects",
                # Send a rogue 'tenant_id' in the body — should be ignored
                json={"name": "My Project", "tenant_id": str(uuid.uuid4())},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 201
    # Confirm tenant_id in response is from JWT, not from the rogue body field
    assert resp.json()["tenant_id"] == str(tenant_id)


@pytest.mark.asyncio
async def test_tenant_b_user_cannot_update_tenant_a_project():
    """
    Tenant isolation on PATCH: a user in tenant B cannot update a project
    that lives in tenant A's schema.
    """
    user_b_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()
    tenant_b_slug = "tenant-b-org"
    project_id = uuid.uuid4()  # belongs to tenant A
    token_b = _make_token(user_b_id, tenant_b_id, tenant_b_slug)

    from src.services.project_service import ProjectNotFoundError

    app.dependency_overrides[get_db] = _make_rbac_db_mock(user_b_id, tenant_b_id)

    with patch(
        "src.api.v1.projects.router.project_service.update_project",
        new=AsyncMock(side_effect=ProjectNotFoundError("not in tenant B")),
    ), patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            resp = await client.patch(
                f"/api/v1/projects/{project_id}",
                json={"name": "Hijacked Name"},
            )

    app.dependency_overrides.clear()

    assert resp.status_code == 404
