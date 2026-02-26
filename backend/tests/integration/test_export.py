"""
Integration tests — Data Export & Org Deletion endpoints
Story: 1-13-data-export-org-deletion
Tasks 7.3, 7.4, 7.5, 7.6, 7.7, 7.8
AC: #2 — export request, rate limiting, RBAC
AC: #3, #5 — export status, deletion flow, RBAC (Owner only)
AC: #7 — error codes: 409 in-progress, 400 name mismatch, 403 wrong 2FA, 429 rate limit
AC: #8 — audit records preserved in public.deletion_audit
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
    mock.setex = AsyncMock(return_value=True)
    mock.set = AsyncMock(return_value=True)
    mock.scan = AsyncMock(return_value=(0, []))
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    return mock


def _setup_auth_session(user_id, tenant_id, role="owner"):
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = f"{role}@test.com"
    mock_user.full_name = "Test User"
    mock_user.totp_enabled = False
    mock_user.password_hash = None

    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id
    mock_tenant.name = "Test Org"
    mock_tenant.slug = "test-org"
    mock_tenant.schema_name = "tenant_test_org"

    mock_membership = MagicMock(spec=TenantUser)
    mock_membership.role = role
    mock_membership.is_active = True
    mock_membership.tenant_id = tenant_id
    mock_membership.user_id = user_id

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()

        if "export_jobs" in s and "processing" in s and "select" in s:
            # No in-progress jobs
            result.fetchone.return_value = None
        elif "export_jobs" in s and "insert" in s:
            result.rowcount = 1
        elif "export_jobs" in s and "select" in s:
            mappings = MagicMock()
            mappings.fetchall.return_value = []
            mappings.fetchone.return_value = None
            result.mappings.return_value = mappings
        elif "deletion_audit" in s:
            mappings = MagicMock()
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []
            result.mappings.return_value = mappings
        elif "tenants_users" in s and "select" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "tenants" in s and "select" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_user
        return result

    mock_session.execute = mock_execute
    return mock_session


# ---------------------------------------------------------------------------
# C1: Unauthenticated access — 401
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    @pytest.mark.asyncio
    async def test_export_unauthenticated_401(self):
        user_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"/api/v1/orgs/{user_id}/export")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_exports_unauthenticated_401(self):
        org_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"/api/v1/orgs/{org_id}/exports")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_org_unauthenticated_401(self):
        org_id = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"/api/v1/orgs/{org_id}/delete",
                json={"org_name_confirmation": "Test", "password": "pass"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# C2: RBAC — only Owner (Admin is NOT sufficient)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ["admin", "member", "viewer", "developer"])
class TestRBACExport:
    @pytest.mark.asyncio
    async def test_non_owner_export_403(self, role: str):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_auth_session(user_id, tenant_id, role=role)

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
        assert resp.status_code == 403, f"Expected 403 for role={role}, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_non_owner_delete_403(self, role: str):
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_auth_session(user_id, tenant_id, role=role)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                    resp = await c.post(
                        f"/api/v1/orgs/{tenant_id}/delete",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"org_name_confirmation": "Test Org", "password": "pass"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# C3: Export — valid request returns 202
# ---------------------------------------------------------------------------

class TestExportRequest:
    @pytest.mark.asyncio
    async def test_owner_can_request_export_202(self):
        """Owner can trigger export — returns 202 with job metadata."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")
        mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                with patch(
                    "src.services.export_service.ExportService._check_export_rate_limit",
                    new_callable=AsyncMock,
                    return_value=True,
                ):
                    with patch(
                        "src.services.export_service.ExportService.generate_export",
                        new_callable=AsyncMock,
                    ):
                        async with AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ) as c:
                            resp = await c.post(
                                f"/api/v1/orgs/{tenant_id}/export",
                                headers={"Authorization": f"Bearer {token}"},
                            )

        app.dependency_overrides.clear()
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "processing"
        assert "job_id" in body

    @pytest.mark.asyncio
    async def test_export_rate_limit_returns_429(self):
        """Export limited to 1/24h — blocked after first request."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")
        mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                with patch(
                    "src.services.export_service.ExportService._check_export_rate_limit",
                    new_callable=AsyncMock,
                    return_value=False,  # Rate limit hit
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.post(
                            f"/api/v1/orgs/{tenant_id}/export",
                            headers={"Authorization": f"Bearer {token}"},
                        )

        app.dependency_overrides.clear()
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# C4: Delete Org — org name mismatch returns 400
# ---------------------------------------------------------------------------

class TestDeleteOrg:
    @pytest.mark.asyncio
    async def test_wrong_org_name_returns_400(self):
        """Deletion with wrong org_name_confirmation → 400."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")
        mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.post(
                        f"/api/v1/orgs/{tenant_id}/delete",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "org_name_confirmation": "wrong name",
                            "password": "mypassword",
                        },
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "ORG_NAME_MISMATCH"

    @pytest.mark.asyncio
    async def test_invalid_password_returns_403(self):
        """Deletion with wrong password → 403 VERIFICATION_FAILED."""
        import bcrypt
        correct_hash = bcrypt.hashpw(b"correct", bcrypt.gensalt()).decode()

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "owner@test.com"
        mock_user.full_name = "Test Owner"
        mock_user.totp_enabled = False
        mock_user.password_hash = correct_hash

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
            mappings = MagicMock()

            if "totp_enabled" in s or "password_hash" in s:
                mappings.fetchone.return_value = {
                    "totp_enabled": False,
                    "password_hash": correct_hash,
                    "id": user_id,
                }
            elif "tenants_users" in s:
                result.scalar_one_or_none.return_value = mock_membership
            elif "tenants" in s and "user" not in s:
                result.scalar_one_or_none.return_value = mock_tenant
            else:
                result.scalar_one_or_none.return_value = mock_user
                mappings.fetchone.return_value = None

            result.mappings.return_value = mappings
            return result

        mock_session.execute = mock_execute

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.post(
                        f"/api/v1/orgs/{tenant_id}/delete",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "org_name_confirmation": "Test Org",
                            "password": "wrong-password",
                        },
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 403
        assert "VERIFICATION_FAILED" in resp.json()["error"]["code"]

    @pytest.mark.asyncio
    async def test_valid_deletion_returns_202(self):
        """Valid deletion request (correct name + correct password) → 202."""
        import bcrypt
        correct_hash = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode()

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "owner@test.com"
        mock_user.full_name = "Test Owner"
        mock_user.totp_enabled = False
        mock_user.password_hash = correct_hash

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
            mappings = MagicMock()

            if "totp_enabled" in s or "password_hash" in s:
                mappings.fetchone.return_value = {
                    "totp_enabled": False,
                    "password_hash": correct_hash,
                    "id": user_id,
                }
            elif "tenants_users" in s and "select" in s:
                result.scalar_one_or_none.return_value = mock_membership
            elif "tenants" in s and "select" in s and "user" not in s:
                result.scalar_one_or_none.return_value = mock_tenant
            else:
                result.scalar_one_or_none.return_value = mock_user
                mappings.fetchone.return_value = None

            result.mappings.return_value = mappings
            return result

        mock_session.execute = mock_execute

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
                with patch(
                    "src.services.org_deletion_service.OrgDeletionService.execute_deletion",
                    new_callable=AsyncMock,
                ):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.post(
                            f"/api/v1/orgs/{tenant_id}/delete",
                            headers={"Authorization": f"Bearer {token}"},
                            json={
                                "org_name_confirmation": "Test Org",
                                "password": "correct-password",
                            },
                        )

        app.dependency_overrides.clear()
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "processing"
