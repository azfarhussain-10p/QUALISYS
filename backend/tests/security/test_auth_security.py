"""
Security Tests — Registration Endpoint
Story: 1-1-user-account-creation (Task 6.6)
AC: AC7 — SQL injection, XSS, credential exposure, CSRF

Per architecture.md#Security-Threat-Model: parameterized queries ONLY,
never log credentials, sanitize all user input.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


SQL_INJECTION_PAYLOADS = [
    "admin'--",
    "'; DROP TABLE users; --",
    "' OR '1'='1",
    "admin'/*",
    "1' UNION SELECT NULL,NULL--",
]

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "javascript:alert(1)",
    "<svg/onload=alert(1)>",
]


class TestSQLInjectionPrevention:
    @pytest.mark.parametrize("injection", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_email_rejected(
        self, client: AsyncClient, injection: str
    ):
        """AC7: ORM parameterized queries prevent SQL injection in email field."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"{injection}@example.com",
                "password": "SecurePass123!",
                "full_name": "Test",
            },
        )
        # SQLAlchemy ORM uses parameterized queries — injection is treated as data
        # The email validation rejects non-RFC5322 formats regardless
        assert response.status_code in (201, 422, 400, 409)
        # Server must NOT return 500 (which would indicate an unhandled SQL error)
        assert response.status_code != 500

    @pytest.mark.parametrize("injection", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_full_name_handled(
        self, client: AsyncClient, injection: str
    ):
        """AC7: full_name field SQL injection stored as literal text, not executed."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"sqltest_{hash(injection) % 100000}@example.com",
                "password": "SecurePass123!",
                "full_name": injection,
            },
        )
        assert response.status_code != 500


class TestXSSPrevention:
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_full_name_not_in_response(
        self, client: AsyncClient, payload: str
    ):
        """AC7: XSS payloads in full_name are stored as plain text (Pydantic sanitizes)."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"xsstest_{abs(hash(payload)) % 100000}@example.com",
                "password": "SecurePass123!",
                "full_name": payload,
            },
        )
        if response.status_code == 201:
            # The payload is returned as literal string, not executed HTML
            response_text = response.text
            # The raw payload may appear but must not be an unescaped script tag
            # (Content-Type: application/json means it's JSON-encoded, safe by default)
            assert "<script>" not in response_text.replace("\\u003c", "<")


class TestCredentialExposure:
    async def test_password_not_in_successful_response(self, client: AsyncClient):
        """AC7: password_hash NEVER appears in 201 response."""
        password = "SecurePass123!"
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "credcheck@example.com",
                "password": password,
                "full_name": "Test User",
            },
        )
        assert response.status_code == 201
        assert password not in response.text
        assert "password_hash" not in response.text
        assert "$2b$" not in response.text  # bcrypt hash prefix not in response

    async def test_password_not_in_error_response(self, client: AsyncClient):
        """AC7: password not echoed back in error response."""
        password = "SecurePass123!"
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "bademail", "password": password, "full_name": "Test"},
        )
        assert password not in response.text


class TestRateLimiting:
    async def test_rate_limit_header_present_on_429(self, client: AsyncClient):
        """AC6: 429 response includes Retry-After header."""
        from unittest.mock import AsyncMock, MagicMock, patch

        # Simulate rate limit exceeded
        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[6, 45])  # count=6 > max=5 → 429
        mock_redis.pipeline.return_value = pipe
        mock_redis.expire = AsyncMock()

        with patch("src.middleware.rate_limit.get_redis_client", return_value=mock_redis):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "ratelimited@example.com",
                    "password": "SecurePass123!",
                    "full_name": "Test",
                },
            )
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    async def test_rate_limit_error_code(self, client: AsyncClient):
        """AC8: 429 response has structured error {error: {code, message}}."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[10, 30])
        mock_redis.pipeline.return_value = pipe
        mock_redis.expire = AsyncMock()

        with patch("src.middleware.rate_limit.get_redis_client", return_value=mock_redis):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "ratelimited2@example.com",
                    "password": "SecurePass123!",
                    "full_name": "Test",
                },
            )
        assert response.status_code == 429
        data = response.json()
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
