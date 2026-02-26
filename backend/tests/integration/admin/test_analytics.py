"""
Integration tests — GET /api/v1/admin/analytics
Story: 1-12-usage-analytics-audit-logs-basic
Task 7.3 — returns metrics JSON, RBAC enforcement (non-admin → 403)
AC: #1 — active_users, active_projects, test_runs, storage_consumed
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service


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
        if "tenants_users" in s and "is_active" in s:
            # Analytics COUNT query
            result.fetchone.return_value = (5,)
            result.scalar.return_value = 5
        elif "tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.tenants" in s or "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "public.users" in s or ("user" in s and "tenant" not in s):
            result.scalar_one_or_none.return_value = mock_user
        elif "projects" in s:
            result.fetchone.return_value = (3,)
            result.scalar.return_value = 3
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    return mock_session, mock_user


def _make_mock_redis():
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    return mock


@pytest.mark.asyncio
async def test_get_analytics_returns_metrics():
    """AC1: GET /admin/analytics → 200 with metrics object."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="owner")

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.services.analytics_service.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.get(
                        "/api/v1/admin/analytics",
                        headers={"Authorization": f"Bearer {token}"},
                    )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "active_users" in data
    assert "active_projects" in data
    assert "test_runs" in data
    assert data["test_runs"] == 0         # placeholder
    assert data["storage_consumed"] == "—" # placeholder


@pytest.mark.asyncio
async def test_get_analytics_requires_owner_admin():
    """AC1: Non-admin role → 403 INSUFFICIENT_ROLE."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="member")
    mock_session, _ = _setup_auth_session(user_id, tenant_id, role="member")

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/analytics",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_analytics_unauthenticated():
    """No token → 401."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/admin/analytics")

    assert resp.status_code == 401
