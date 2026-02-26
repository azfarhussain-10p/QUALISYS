"""
Security tests — Admin audit log endpoints
Story: 1-12-usage-analytics-audit-logs-basic
Task 7.10 — RBAC bypass attempts, SQL injection in filters, cross-tenant access
AC: #8 — RBAC enforcement, no cross-tenant data leakage
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
        if "audit_logs" in s and "count" in s:
            result.scalar.return_value = 0
        elif "audit_logs" in s:
            mappings = MagicMock()
            mappings.fetchall.return_value = []
            result.mappings.return_value = mappings
        elif "tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_user
        return result

    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    return mock_session


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


# ---------------------------------------------------------------------------
# C1: Unauthenticated access blocked
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    @pytest.mark.asyncio
    async def test_analytics_unauthenticated_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/analytics")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_audit_logs_unauthenticated_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/audit-logs")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_export_unauthenticated_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/admin/audit-logs/export")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/admin/analytics",
                headers={"Authorization": "Bearer not.a.valid.jwt.token"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# C2: RBAC enforcement — only owner/admin
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["viewer", "member", "tester", "developer"])
class TestRBACEnforcement:
    @pytest.mark.asyncio
    async def test_non_admin_analytics_403(self, role: str):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_auth_session(user_id, tenant_id, role=role)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(
                        "/api/v1/admin/analytics",
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_audit_logs_403(self, role: str):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_auth_session(user_id, tenant_id, role=role)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(
                        "/api/v1/admin/audit-logs",
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# C3: SQL injection in filter params → blocked by validation
# ---------------------------------------------------------------------------

_SQL_INJECTION_ACTIONS = [
    "'; DROP TABLE audit_logs; --",
    "project.created OR 1=1",
    "project.created' UNION SELECT * FROM users--",
    "org.created\x00",
]


class TestSQLInjectionInFilters:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("malicious_action", _SQL_INJECTION_ACTIONS)
    async def test_sql_injection_in_action_param_rejected(self, malicious_action: str):
        """SQL injection in ?action= must not cause 500 — validation returns 400."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")
        mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(
                        "/api/v1/admin/audit-logs",
                        params={"action": malicious_action},
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        # Must be 400 (validation) — NEVER 500
        assert resp.status_code in (400, 422), (
            f"Expected 400/422 for SQL injection, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_sql_injection_in_actor_user_id_rejected(self):
        """Malformed actor_user_id (not a UUID) → 400, not 500."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")
        mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.get(
                        "/api/v1/admin/audit-logs",
                        params={"actor_user_id": "'; DROP TABLE--"},
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_ACTOR_ID"
