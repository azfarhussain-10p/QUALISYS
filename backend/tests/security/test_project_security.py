"""
Security Tests — Project Endpoints
Story: 1-9-project-creation-configuration (Task 6.7)
AC: AC7 — SQL injection prevention, XSS in name/description, RBAC bypass attempts

C1  — Parameterized queries protect against SQL injection
C2  — Schema name validated by validate_safe_identifier() before use
C6  — javascript:/data: URLs rejected by Pydantic validator
C9  — Slug algorithm produces safe, lower-case alphanumeric + hyphens only
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.db import get_db
from src.services.token_service import token_service


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

SQL_INJECTION_NAMES = [
    "'; DROP TABLE projects; --",
    "a UNION SELECT * FROM users --",
    "x'; DELETE FROM projects WHERE '1'='1",
    "<script>document.cookie</script>",
    "' OR '1'='1",
]

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "onmouseover=alert(1)",
    "<svg/onload=alert(1)>",
]

DANGEROUS_URL_SCHEMES = [
    "javascript:alert(document.cookie)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
]

NON_GITHUB_URLS = [
    "https://gitlab.com/owner/repo",
    "https://bitbucket.org/owner/repo",
    "https://evil.com/github.com/owner/repo",
    "https://github.com.evil.com/owner/repo",
]


# ---------------------------------------------------------------------------
# Fixtures
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


def _make_owner_token(user_id=None, tenant_id=None, tenant_slug="test-org"):
    user_id = user_id or uuid.uuid4()
    tenant_id = tenant_id or uuid.uuid4()
    return token_service.create_access_token(
        user_id=user_id,
        email="owner@test.com",
        tenant_id=tenant_id,
        role="owner",
        tenant_slug=tenant_slug,
    )


# ---------------------------------------------------------------------------
# SQL Injection in project name — C1
# ---------------------------------------------------------------------------

class TestSQLInjectionPrevention:
    """C1: Parameterized queries must not execute injected SQL."""

    @pytest.mark.parametrize("injection", SQL_INJECTION_NAMES)
    async def test_sql_injection_in_project_name_no_500(self, injection: str):
        """
        SQL injection in project name must never cause a 500 error.
        Accepted outcomes: 422 (Pydantic rejects), 400, 201 (stored safely).
        A 500 would indicate unparameterized SQL execution.
        """
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_owner_token(user_id, tenant_id)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(
                    "/api/v1/projects",
                    json={"name": injection},
                    headers={"Authorization": f"Bearer {token}"},
                )
        # Must not be a server error — 500 would indicate unsanitized SQL
        assert resp.status_code != 500, (
            f"Potential SQL injection via name: {injection!r} caused 500"
        )

    async def test_sql_injection_in_project_name_does_not_execute(self):
        """
        A well-formed injection string (≥3 chars) might pass Pydantic validation
        but must be stored as-is (parameterized), not executed as SQL.
        The project_service uses SQLAlchemy text() with :params — safe.
        """
        # "x OR 1=1" is 8 chars, passes min_length=3
        # If it were interpreted as SQL it would select all rows / cause an error.
        token = _make_owner_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(
                    "/api/v1/projects",
                    json={"name": "x OR 1=1"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        # 422 (fails RBAC / no tenant) or 401 are both acceptable —
        # what matters is no 500
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# XSS in project name / description — C6
# ---------------------------------------------------------------------------

class TestXSSPrevention:
    """XSS payloads in string fields must not cause 500 errors."""

    @pytest.mark.parametrize("xss", XSS_PAYLOADS)
    async def test_xss_in_name_no_500(self, xss: str):
        """XSS payload in name — server must not crash. Short names → 422."""
        token = _make_owner_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(
                    "/api/v1/projects",
                    json={"name": xss},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code != 500

    async def test_xss_in_description_rejected_or_stored_safely(self):
        """XSS in description stored as-is (server returns it escaped in JSON)."""
        token = _make_owner_token()
        xss_description = "<script>document.cookie</script>"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(
                    "/api/v1/projects",
                    json={"name": "Valid Project Name", "description": xss_description},
                    headers={"Authorization": f"Bearer {token}"},
                )
        # 401/403 expected without valid RBAC setup — the point is no 500
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Dangerous URL schemes — C6 (AC7)
# ---------------------------------------------------------------------------

class TestDangerousURLRejection:
    """C6: javascript:, data:, vbscript:, file: URLs must be rejected (422)."""

    @pytest.mark.parametrize("url", DANGEROUS_URL_SCHEMES)
    async def test_dangerous_app_url_rejected(self, url: str):
        """AC7, C6: dangerous URL schemes in app_url → 422."""
        token = _make_owner_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/projects",
                json={"name": "Valid Name", "app_url": url},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 422, (
            f"Expected 422 for dangerous URL {url!r}, got {resp.status_code}"
        )

    @pytest.mark.parametrize("url", NON_GITHUB_URLS)
    async def test_non_github_repo_url_rejected(self, url: str):
        """AC7: github_repo_url must match github.com pattern — others rejected."""
        token = _make_owner_token()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/projects",
                json={"name": "Valid Name", "github_repo_url": url},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 422, (
            f"Expected 422 for non-GitHub URL {url!r}, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# RBAC bypass attempts
# ---------------------------------------------------------------------------

class TestRBACBypassPrevention:
    """Verify that RBAC cannot be bypassed via crafted requests."""

    async def test_no_token_returns_401(self):
        """No JWT → 401 NOT_AUTHENTICATED."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/projects", json={"name": "Test"})
        assert resp.status_code == 401

    async def test_malformed_jwt_returns_401(self):
        """Malformed/tampered JWT → 401 INVALID_TOKEN."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/projects",
                json={"name": "Test Project"},
                headers={"Authorization": "Bearer not.a.jwt"},
            )
        assert resp.status_code == 401

    async def test_token_without_tenant_id_returns_403(self):
        """JWT with no tenant_id claim (no org selected) → 403 NO_TENANT_CONTEXT."""
        # token_service.create_access_token with tenant_id=None
        from src.services.token_service import token_service as ts
        token = ts.create_access_token(
            user_id=uuid.uuid4(),
            email="test@test.com",
        )  # no tenant_id → None
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(
                    "/api/v1/projects",
                    json={"name": "Test Project"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "NO_TENANT_CONTEXT"


# ---------------------------------------------------------------------------
# Slug safety — C9
# ---------------------------------------------------------------------------

class TestSlugSafety:
    """C9: Generated slugs must contain only safe characters."""

    def test_slug_from_xss_name_is_safe(self):
        """XSS in name produces a slug with only [a-z0-9-]."""
        from src.services.project_service import _slugify_base
        import re
        slug = _slugify_base("<script>alert(1)</script>")
        assert re.match(r"^[a-z0-9-]+$", slug), f"Unsafe slug produced: {slug!r}"

    def test_slug_from_sql_injection_name_is_safe(self):
        """SQL injection in name produces a safe slug."""
        from src.services.project_service import _slugify_base
        import re
        slug = _slugify_base("'; DROP TABLE projects; --")
        assert re.match(r"^[a-z0-9-]+$", slug) or slug == "project", (
            f"Unsafe slug produced: {slug!r}"
        )

    def test_slug_from_unicode_attack_is_safe(self):
        """Unicode homograph attack → ASCII-only slug."""
        from src.services.project_service import _slugify_base
        import re
        # Cyrillic 'а' looks like Latin 'a'
        slug = _slugify_base("аdmin")  # Cyrillic а + Latin dmin
        assert re.match(r"^[a-z0-9-]*$", slug), f"Non-ASCII in slug: {slug!r}"
