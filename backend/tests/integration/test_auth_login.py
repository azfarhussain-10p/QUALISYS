"""
Integration tests — Login & Session Management endpoints (Story 1.5)
ACs: AC1, AC3, AC4, AC5, AC6, AC7, AC8
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.tenant import Tenant, TenantUser
from src.services.auth.auth_service import hash_password
from tests.conftest import _mock_redis


# ---------------------------------------------------------------------------
# Fixtures — verified user + org
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def verified_user(db_session: AsyncSession) -> User:
    """Verified email/password user (can log in)."""
    user = User(
        id=uuid.uuid4(),
        email=f"verified_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Verified User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=True,
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def unverified_user(db_session: AsyncSession) -> User:
    """Unverified user — cannot log in (AC1 guard)."""
    user = User(
        id=uuid.uuid4(),
        email=f"unverified_{uuid.uuid4().hex[:6]}@example.com",
        full_name="Unverified User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=False,
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def user_with_org(db_session: AsyncSession, verified_user: User) -> tuple[User, Tenant]:
    """verified_user enrolled in a single org (owner)."""
    slug = f"test-{uuid.uuid4().hex[:6]}"
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Org",
        slug=slug,
        data_retention_days=365,
        plan="free",
        settings={},
        created_by=verified_user.id,
    )
    db_session.add(tenant)
    await db_session.flush()

    membership = TenantUser(
        tenant_id=tenant.id,
        user_id=verified_user.id,
        role="owner",
    )
    db_session.add(membership)
    verified_user.default_tenant_id = tenant.id
    db_session.add(verified_user)
    await db_session.flush()

    return verified_user, tenant


# ---------------------------------------------------------------------------
# AC1 — POST /api/v1/auth/login
# ---------------------------------------------------------------------------

class TestLogin:
    @pytest.mark.asyncio
    async def test_login_valid_credentials_200(
        self, client: AsyncClient, user_with_org: tuple
    ):
        user, tenant = user_with_org
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["email"] == user.email
        assert isinstance(body["orgs"], list)
        assert body["has_multiple_orgs"] is False

    @pytest.mark.asyncio
    async def test_login_sets_httponly_cookies(
        self, client: AsyncClient, user_with_org: tuple
    ):
        user, _ = user_with_org
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        # Collect all Set-Cookie headers (httpx may return multiple)
        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_cookie = next(
            (h for h in set_cookie_headers if "access_token=" in h), None
        )
        refresh_cookie = next(
            (h for h in set_cookie_headers if "refresh_token=" in h), None
        )
        assert access_cookie is not None, "access_token Set-Cookie header missing"
        assert "HttpOnly" in access_cookie, "access_token cookie must have HttpOnly flag"
        assert "SameSite" in access_cookie, "access_token cookie must have SameSite attribute"
        assert refresh_cookie is not None, "refresh_token Set-Cookie header missing"
        assert "HttpOnly" in refresh_cookie, "refresh_token cookie must have HttpOnly flag"

    @pytest.mark.asyncio
    async def test_login_wrong_password_401(
        self, client: AsyncClient, verified_user: User
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": verified_user.email, "password": "WrongPassword123!"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_unknown_email_401(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "SecurePass123!"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_login_unverified_email_403(
        self, client: AsyncClient, unverified_user: User
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": unverified_user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    @pytest.mark.asyncio
    async def test_login_account_locked_423(
        self, client: AsyncClient, verified_user: User, db_session: AsyncSession
    ):
        from src.db import get_db
        from src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        # Redis mock that simulates active lockout
        locked_redis = _mock_redis()
        locked_redis.exists = AsyncMock(return_value=1)  # lockout active

        with patch("src.cache.get_redis_client", return_value=locked_redis):
            with patch("src.middleware.rate_limit.get_redis_client", return_value=locked_redis):
                from httpx import ASGITransport
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://test",
                ) as ac:
                    resp = await ac.post(
                        "/api/v1/auth/login",
                        json={"email": verified_user.email, "password": "SecurePass123!"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 423
        assert resp.json()["error"]["code"] == "ACCOUNT_LOCKED"

    @pytest.mark.asyncio
    async def test_login_multi_org_has_multiple_orgs_true(
        self, client: AsyncClient, db_session: AsyncSession, verified_user: User
    ):
        """User in 2 orgs → has_multiple_orgs=True, tenant_id=null in token."""
        for i in range(2):
            slug = f"org-multi-{uuid.uuid4().hex[:6]}"
            t = Tenant(id=uuid.uuid4(), name=f"Org {i}", slug=slug,
                       data_retention_days=365, plan="free", settings={},
                       created_by=verified_user.id)
            db_session.add(t)
            await db_session.flush()
            db_session.add(TenantUser(tenant_id=t.id, user_id=verified_user.id, role="admin"))
        await db_session.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": verified_user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_multiple_orgs"] is True
        assert len(body["orgs"]) == 2


# ---------------------------------------------------------------------------
# AC5 — POST /api/v1/auth/logout
# ---------------------------------------------------------------------------

class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_returns_200(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert "Logged out" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_logout_idempotent_when_no_cookie(self, client: AsyncClient):
        """Logout without a refresh cookie returns 200 (idempotent)."""
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC4 — POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    @pytest.mark.asyncio
    async def test_refresh_without_cookie_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "MISSING_REFRESH_TOKEN"

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_returns_401(self, client: AsyncClient):
        # Send a fake refresh token cookie
        client.cookies.set("refresh_token", "fake-invalid-token")
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# AC5 — GET /api/v1/auth/sessions
# ---------------------------------------------------------------------------

class TestSessions:
    @pytest.mark.asyncio
    async def test_sessions_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_sessions_returns_list_for_authenticated_user(
        self, client_with_auth: AsyncClient
    ):
        resp = await client_with_auth.get("/api/v1/auth/sessions")
        assert resp.status_code == 200
        assert "sessions" in resp.json()
        assert isinstance(resp.json()["sessions"], list)


# ---------------------------------------------------------------------------
# AC5 — POST /api/v1/auth/logout-all
# ---------------------------------------------------------------------------

class TestLogoutAll:
    @pytest.mark.asyncio
    async def test_logout_all_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout-all")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_all_returns_200_for_authenticated(
        self, client_with_auth: AsyncClient
    ):
        resp = await client_with_auth.post("/api/v1/auth/logout-all")
        assert resp.status_code == 200
        assert "revoked" in resp.json()["message"]


# ---------------------------------------------------------------------------
# AC6 — POST /api/v1/auth/select-org
# ---------------------------------------------------------------------------

class TestSelectOrg:
    @pytest.mark.asyncio
    async def test_select_org_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/select-org",
            json={"tenant_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_select_org_forbidden_if_not_member(
        self, client_with_auth: AsyncClient
    ):
        resp = await client_with_auth.post(
            "/api/v1/auth/select-org",
            json={"tenant_id": str(uuid.uuid4())},  # random org
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NOT_A_MEMBER"
