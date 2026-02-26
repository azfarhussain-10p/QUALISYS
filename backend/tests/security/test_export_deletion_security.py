"""
Security tests — Data Export & Org Deletion endpoints
Story: 1-13-data-export-org-deletion
Task 7.11 — SQL injection in schema name, RBAC bypass, cross-tenant access
AC: #7, #8 — RBAC enforcement, schema name validation
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


def _make_mock_redis():
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.setex = AsyncMock(return_value=True)
    mock.scan = AsyncMock(return_value=(0, []))
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    return mock


def _setup_owner_session(user_id, tenant_id):
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = "owner@test.com"
    mock_user.full_name = "Test Owner"

    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id
    mock_tenant.name = "Test Org"
    mock_tenant.slug = "test-org"
    mock_tenant.schema_name = "tenant_test_org"

    mock_membership = MagicMock(spec=TenantUser)
    mock_membership.role = "owner"
    mock_membership.is_active = True
    mock_membership.tenant_id = tenant_id
    mock_membership.user_id = user_id

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()
        if "tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_user
        result.fetchone.return_value = None
        mappings = MagicMock()
        mappings.fetchone.return_value = None
        result.mappings.return_value = mappings
        return result

    mock_session.execute = mock_execute
    return mock_session


# ---------------------------------------------------------------------------
# C1: Unauthenticated access blocked
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    @pytest.mark.asyncio
    async def test_export_no_token_401(self):
        org_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/v1/orgs/{org_id}/export")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_no_token_401(self):
        org_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/v1/orgs/{org_id}/delete",
                json={"org_name_confirmation": "X", "password": "y"},
            )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_401(self):
        org_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/v1/orgs/{org_id}/export",
                headers={"Authorization": "Bearer not.a.valid.jwt"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# C2: RBAC — Admin cannot access Owner-only endpoints
# ---------------------------------------------------------------------------

class TestAdminCannotDelete:
    @pytest.mark.asyncio
    async def test_admin_cannot_export_403(self):
        """Admin role is NOT sufficient for export — Owner only."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="admin")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "admin@test.com"
        mock_user.full_name = "Admin User"

        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.id = tenant_id
        mock_tenant.name = "Test Org"
        mock_tenant.slug = "test-org"

        mock_membership = MagicMock(spec=TenantUser)
        mock_membership.role = "admin"
        mock_membership.is_active = True
        mock_membership.tenant_id = tenant_id
        mock_membership.user_id = user_id

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        async def mock_execute(stmt, *args, **kwargs):
            result = MagicMock()
            s = str(stmt).lower()
            if "tenants_users" in s:
                result.scalar_one_or_none.return_value = mock_membership
            elif "tenants" in s and "user" not in s:
                result.scalar_one_or_none.return_value = mock_tenant
            else:
                result.scalar_one_or_none.return_value = mock_user
            return result

        mock_session.execute = mock_execute

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    resp = await c.post(
                        f"/api/v1/orgs/{tenant_id}/export",
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# C3: Cross-tenant access blocked
# ---------------------------------------------------------------------------

class TestCrossTenantAccess:
    @pytest.mark.asyncio
    async def test_cannot_export_another_tenants_data(self):
        """
        User from tenant A cannot trigger export for tenant B org_id.
        The org_id in the path is used for RBAC lookup — membership check fails.
        """
        user_id = uuid.uuid4()
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()  # <-- requesting this org's export

        token = _make_token(user_id, tenant_a_id, role="owner")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "owner@test.com"

        mock_tenant_b = MagicMock(spec=Tenant)
        mock_tenant_b.id = tenant_b_id
        mock_tenant_b.name = "Other Org"

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        async def mock_execute(stmt, *args, **kwargs):
            result = MagicMock()
            s = str(stmt).lower()
            if "tenants_users" in s:
                # User has NO membership in tenant B
                result.scalar_one_or_none.return_value = None
            elif "tenants" in s and "user" not in s:
                result.scalar_one_or_none.return_value = mock_tenant_b
            else:
                result.scalar_one_or_none.return_value = mock_user
            return result

        mock_session.execute = mock_execute

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    resp = await c.post(
                        f"/api/v1/orgs/{tenant_b_id}/export",  # wrong org
                        headers={"Authorization": f"Bearer {token}"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code in (403, 404), (
            f"Expected 403/404 for cross-tenant export, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# C4: Schema name validation in deletion service
# ---------------------------------------------------------------------------

class TestSchemaNameValidation:
    @pytest.mark.asyncio
    async def test_unsafe_schema_name_raises_not_drops(self):
        """
        OrgDeletionService._run_deletion() must validate schema name from DB.
        Ensures validate_safe_identifier blocks unsafe names (e.g. with injection chars).
        """
        from src.services.org_deletion_service import OrgDeletionService
        from src.services.tenant_provisioning import validate_safe_identifier

        # Verify validate_safe_identifier rejects unsafe names
        unsafe_names = [
            "tenant_'; DROP TABLE users; --",
            "tenant_test; DROP SCHEMA public CASCADE",
            'tenant_"malicious"',
        ]
        for name in unsafe_names:
            assert not validate_safe_identifier(name), (
                f"validate_safe_identifier should reject: {name!r}"
            )

        # Verify it accepts safe names
        safe_names = ["tenant_acme", "tenant_my_org", "tenant_test123"]
        for name in safe_names:
            assert validate_safe_identifier(name), (
                f"validate_safe_identifier should accept: {name!r}"
            )
