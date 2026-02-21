"""
Security tests — Login & Session Management (Story 1.5)
ACs: AC3 (cookie flags), AC7 (lockout), AC8 (no enumeration, rate limiting)
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.services.auth.auth_service import hash_password
from tests.conftest import _mock_redis


@pytest.fixture
def verified_user_email() -> str:
    return f"sec_test_{uuid.uuid4().hex[:6]}@example.com"


# ---------------------------------------------------------------------------
# AC8 — No email enumeration
# ---------------------------------------------------------------------------

class TestNoEmailEnumeration:
    @pytest.mark.asyncio
    async def test_wrong_email_and_wrong_password_same_status(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Both 'wrong email' and 'wrong password' should return the same HTTP status
        and error code — prevents attackers from discovering valid emails.
        """
        # Wrong email
        resp_no_email = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "SecurePass123!"},
        )

        # Create a real user so we can test wrong password
        user = User(
            id=uuid.uuid4(),
            email=f"real_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Real User",
            password_hash=hash_password("CorrectPass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(user)
        await db_session.flush()

        resp_wrong_pw = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "WrongPassword123!"},
        )

        assert resp_no_email.status_code == resp_wrong_pw.status_code == 401
        assert resp_no_email.json()["error"]["code"] == resp_wrong_pw.json()["error"]["code"]


# ---------------------------------------------------------------------------
# AC3 — Cookie security attributes
# ---------------------------------------------------------------------------

class TestCookieSecurityAttributes:
    @pytest.mark.asyncio
    async def test_access_token_cookie_is_httponly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """access_token cookie must have HttpOnly flag to prevent XSS theft."""
        user = User(
            id=uuid.uuid4(),
            email=f"cookie_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Cookie Test User",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 200

        # Collect all Set-Cookie headers and find the access_token entry
        set_cookie_headers = resp.headers.get_list("set-cookie")
        access_cookie = next(
            (h for h in set_cookie_headers if "access_token=" in h), None
        )
        assert access_cookie is not None, "access_token Set-Cookie header missing"
        assert "HttpOnly" in access_cookie, "access_token cookie must have HttpOnly flag"
        assert "SameSite" in access_cookie, "access_token cookie must have SameSite attribute"

    @pytest.mark.asyncio
    async def test_tokens_not_in_response_body(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Login response body must NOT contain raw token strings (tokens in cookies only)."""
        user = User(
            id=uuid.uuid4(),
            email=f"nobodytoken_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Token Test",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(user)
        await db_session.flush()

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "SecurePass123!"},
        )
        assert resp.status_code == 200
        body = resp.json()

        # LoginResponse schema has no access_token or refresh_token fields
        assert "access_token" not in body
        assert "refresh_token" not in body
        assert "token" not in body


# ---------------------------------------------------------------------------
# AC7 — Account lockout
# ---------------------------------------------------------------------------

class TestAccountLockoutSecurity:
    @pytest.mark.asyncio
    async def test_locked_account_returns_423_not_401(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Locked account returns 423 (distinct from 401) so user knows to check email."""
        user = User(
            id=uuid.uuid4(),
            email=f"locked_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Locked User",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(user)
        await db_session.flush()

        from src.db import get_db
        from src.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

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
                        json={"email": user.email, "password": "SecurePass123!"},
                    )

        app.dependency_overrides.clear()
        assert resp.status_code == 423
        assert "LOCKED" in resp.json()["error"]["code"]


# ---------------------------------------------------------------------------
# AC4 — Refresh token security
# ---------------------------------------------------------------------------

class TestRefreshTokenSecurity:
    @pytest.mark.asyncio
    async def test_refresh_reuse_returns_401(self, client: AsyncClient):
        """Replaying an expired/consumed refresh token returns 401."""
        client.cookies.set("refresh_token", "some-consumed-or-fake-token")
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_without_cookie_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "MISSING_REFRESH_TOKEN"
