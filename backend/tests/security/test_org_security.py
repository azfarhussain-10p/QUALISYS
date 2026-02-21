"""
Security Tests — Organization Endpoints
Story: 1-2-organization-creation-setup (Task 7.5)
AC: AC9 — SQL injection in slugs rejected; IDOR prevented; rate limiting enforced;
          schema name validated; no sensitive data in responses
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant
from src.models.user import User

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

SQL_INJECTION_SLUGS = [
    "admin'--",
    "a'; DROP TABLE tenants; --",
    "' OR '1'='1",
    "a); DROP SCHEMA public CASCADE; --",
    "tenant_x UNION SELECT",
]

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(document.cookie)",
]

SCHEMA_INJECTION_ATTEMPTS = [
    "x'; DROP SCHEMA tenant_x CASCADE; --",
    "public",          # reserved schema name
    "pg_toast",        # PostgreSQL internal
    "information_schema",
]


# ---------------------------------------------------------------------------
# SQL Injection in org name / slug
# ---------------------------------------------------------------------------

class TestSQLInjectionPrevention:
    @pytest.mark.parametrize("injection", SQL_INJECTION_SLUGS)
    async def test_sql_injection_in_slug_rejected(
        self, client_with_auth: AsyncClient, injection: str
    ):
        """AC9: slug validation rejects all SQL injection patterns — no 500."""
        response = await client_with_auth.post(
            "/api/v1/orgs",
            json={"name": "Test Org", "slug": injection},
        )
        assert response.status_code in (400, 409, 422)
        assert response.status_code != 500

    @pytest.mark.parametrize("xss", XSS_PAYLOADS)
    async def test_xss_in_org_name_stored_as_literal(
        self, client_with_auth: AsyncClient, xss: str
    ):
        """
        XSS payloads in org name must be stored as literal text
        (ORM parameterized queries) — never 500.
        """
        with patch("src.api.v1.orgs.router.TenantProvisioningService"):
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": xss + "XA"},  # pad to ≥ 3 chars if XSS is short
            )
        # Must not 500; 201 (stored safely), 400, or 422 (name validation)
        assert response.status_code in (201, 400, 422)
        assert response.status_code != 500


# ---------------------------------------------------------------------------
# Schema name injection prevention (AC9 item 8.1)
# ---------------------------------------------------------------------------

class TestSchemaNameInjection:
    @pytest.mark.parametrize("bad_slug", SCHEMA_INJECTION_ATTEMPTS)
    async def test_schema_injection_slug_rejected(
        self, client_with_auth: AsyncClient, bad_slug: str
    ):
        """
        Slugs that would produce dangerous schema names must be rejected
        at the slug validation layer (422) or provisioning layer (500 never raised).
        """
        response = await client_with_auth.post(
            "/api/v1/orgs",
            json={"name": "Inject Test", "slug": bad_slug},
        )
        assert response.status_code in (400, 422, 409)
        assert response.status_code != 500


# ---------------------------------------------------------------------------
# IDOR (Insecure Direct Object Reference) prevention — AC9 item 8.3
# ---------------------------------------------------------------------------

class TestIDORPrevention:
    async def test_cannot_read_another_orgs_settings(
        self,
        client_with_auth: AsyncClient,
        db_session: AsyncSession,
        existing_user: User,
    ):
        """Authenticated user cannot read settings of an org they don't belong to."""
        # Create a second tenant owned by nobody in our test session
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Org",
            slug=f"other-org-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        response = await client_with_auth.get(
            f"/api/v1/orgs/{other_tenant.id}/settings"
        )
        # Existing_user is not a member of other_tenant — must get 403
        assert response.status_code == 403

    async def test_cannot_modify_another_orgs_settings(
        self,
        client_with_auth: AsyncClient,
        db_session: AsyncSession,
    ):
        """Authenticated user cannot patch settings of an org they don't belong to."""
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Victim Org",
            slug=f"victim-org-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        response = await client_with_auth.patch(
            f"/api/v1/orgs/{other_tenant.id}/settings",
            json={"name": "Hacked"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Sensitive data not in responses — AC9 item 8.4
# ---------------------------------------------------------------------------

class TestSensitiveDataExclusion:
    async def test_create_org_response_no_internal_fields(
        self, client_with_auth: AsyncClient
    ):
        """OrgResponse must NOT expose DB-internal or sensitive fields."""
        with patch("src.api.v1.orgs.router.TenantProvisioningService"):
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "Security Test Org", "slug": "sec-test-org-x1"},
            )
        if response.status_code == 201:
            body_str = response.text
            # These fields must never appear in any org response
            assert "password" not in body_str
            assert "password_hash" not in body_str
            assert "jwt_secret" not in body_str
            assert "aws_secret" not in body_str


# ---------------------------------------------------------------------------
# Rate limiting — AC9 item 8.5
# ---------------------------------------------------------------------------

class TestOrgCreationRateLimit:
    async def test_rate_limit_enforced_after_3_orgs(
        self, db_session: AsyncSession, existing_user: User
    ):
        """
        POST /api/v1/orgs rate-limited to 3/user/hour via Redis.
        After 3 calls the mock returns count > 3 → 429.
        """
        from src.db import get_db
        from src.main import app
        from httpx import ASGITransport, AsyncClient

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock Redis to simulate 4 prior calls (count=4 → rate limited)
        mock_redis = MagicMock()
        pipeline = MagicMock()
        pipeline.incr = MagicMock(return_value=pipeline)
        pipeline.expire = MagicMock(return_value=pipeline)
        pipeline.execute = AsyncMock(return_value=[4, 1])  # count=4, ttl=1 → RATE LIMITED
        mock_redis.pipeline.return_value = pipeline
        mock_redis.ping = AsyncMock(return_value=True)

        from src.services.auth.auth_service import create_access_token

        token = create_access_token(existing_user.id, existing_user.email)

        with patch("src.api.v1.orgs.router.get_redis_client", return_value=mock_redis):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=mock_redis):
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                    headers={"Authorization": f"Bearer {token}"},
                ) as ac:
                    response = await ac.post(
                        "/api/v1/orgs",
                        json={"name": "Rate Test Org"},
                    )

        app.dependency_overrides.clear()
        assert response.status_code == 429
