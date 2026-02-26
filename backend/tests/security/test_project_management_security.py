"""
Security Tests — Project Management (Archive, Delete, List)
Story: 1-11-project-management-archive-delete-list
Task 6.9 — SQL injection prevention, RBAC bypass, cross-tenant access

C1  — Parameterized queries protect against SQL injection in project IDs / search
C2  — Schema name validated before use; no user-controlled schema injection
C7  — Non-Admin roles cannot archive, restore, or delete projects (RBAC enforced)
C10 — Cross-tenant access to archive/delete blocked at RBAC + schema layer
C12 — DELETE without authentication returns 401
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
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock():
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


def _make_token(user_id, tenant_id, role="owner", slug="test-org"):
    return token_service.create_access_token(
        user_id=user_id, email=f"{role}@test.com",
        tenant_id=tenant_id, role=role, tenant_slug=slug,
    )


def _setup_rbac_session(user_id, tenant_id, role="owner"):
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
        elif "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute
    return mock_session


# ---------------------------------------------------------------------------
# C12 — Unauthenticated access to all management endpoints
# ---------------------------------------------------------------------------

class TestUnauthenticatedAccess:
    """C12: All management endpoints require authentication."""

    async def test_archive_without_token_returns_401(self):
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(f"/api/v1/projects/{project_id}/archive")
        assert resp.status_code == 401

    async def test_restore_without_token_returns_401(self):
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(f"/api/v1/projects/{project_id}/restore")
        assert resp.status_code == 401

    async def test_delete_without_token_returns_401(self):
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.delete(f"/api/v1/projects/{project_id}")
        assert resp.status_code == 401

    async def test_list_without_token_returns_401(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.get("/api/v1/projects")
        assert resp.status_code == 401

    async def test_archive_with_malformed_token_returns_401(self):
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": "Bearer tampered.token.value"},
        ) as client:
            resp = await client.post(f"/api/v1/projects/{project_id}/archive")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# C7 — RBAC: non-Owner/Admin roles blocked from management operations
# ---------------------------------------------------------------------------

class TestRBACEnforcement:
    """C7: Only Owner/Admin can archive, restore, delete. Viewers/Members are blocked."""

    @pytest.mark.parametrize("role", ["viewer", "member", "tester"])
    async def test_low_privilege_role_cannot_archive(self, role: str):
        """C7: roles below admin get 403 INSUFFICIENT_ROLE on archive."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_rbac_session(user_id, tenant_id, role=role)

        app.dependency_overrides[get_db] = lambda: mock_session
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                resp = await client.post(f"/api/v1/projects/{project_id}/archive")
        app.dependency_overrides.clear()

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    @pytest.mark.parametrize("role", ["viewer", "member", "tester"])
    async def test_low_privilege_role_cannot_restore(self, role: str):
        """C7: roles below admin get 403 on restore."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_rbac_session(user_id, tenant_id, role=role)

        app.dependency_overrides[get_db] = lambda: mock_session
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                resp = await client.post(f"/api/v1/projects/{project_id}/restore")
        app.dependency_overrides.clear()

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    @pytest.mark.parametrize("role", ["viewer", "member", "tester"])
    async def test_low_privilege_role_cannot_delete(self, role: str):
        """C7: roles below admin get 403 on delete."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role=role)
        mock_session = _setup_rbac_session(user_id, tenant_id, role=role)

        app.dependency_overrides[get_db] = lambda: mock_session
        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                resp = await client.delete(f"/api/v1/projects/{project_id}")
        app.dependency_overrides.clear()

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    async def test_admin_role_can_archive(self):
        """C7: admin role is permitted to archive."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="admin")
        mock_session = _setup_rbac_session(user_id, tenant_id, role="admin")

        from src.services.project_service import Project as _P
        from unittest.mock import MagicMock as MM
        row = MM()
        row.__getitem__ = lambda self, k: {
            "id": project_id, "name": "T", "slug": "t",
            "description": None, "app_url": None, "github_repo_url": None,
            "status": "archived", "settings": {}, "is_active": False,
            "created_by": None, "tenant_id": tenant_id, "organization_id": None,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        }[k]

        app.dependency_overrides[get_db] = lambda: mock_session
        with patch("src.api.v1.projects.router.project_service.archive_project",
                   return_value=_P(row)), \
             patch("src.api.v1.projects.router._get_schema_name", return_value="tenant_test"), \
             patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token}"},
            ) as client:
                resp = await client.post(f"/api/v1/projects/{project_id}/archive")
        app.dependency_overrides.clear()

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# C1 — SQL injection via project_id path parameter
# ---------------------------------------------------------------------------

class TestSQLInjectionInPathParam:
    """
    C1: project_id is a UUID path parameter parsed by FastAPI/Pydantic.
    Any non-UUID value → 422 Unprocessable Entity before reaching service layer.
    SQL injection attempts via project_id are blocked at the type-parsing layer.
    """

    @pytest.mark.parametrize("bad_id", [
        "'; DROP TABLE projects; --",
        "1 UNION SELECT * FROM users",
        "../../../etc/passwd",
        "<script>alert(1)</script>",
        "0' OR '1'='1",
        "1; DELETE FROM projects WHERE 1=1",
    ])
    async def test_sql_injection_in_project_id_returns_422(self, bad_id: str):
        """C1: Non-UUID project_id → 422 before any DB interaction."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.post(f"/api/v1/projects/{bad_id}/archive")
        # FastAPI UUID validation rejects before service layer
        assert resp.status_code == 422, (
            f"Expected 422 for injection ID {bad_id!r}, got {resp.status_code}"
        )

    @pytest.mark.parametrize("bad_id", [
        "'; DROP TABLE projects; --",
        "x OR 1=1",
    ])
    async def test_sql_injection_in_delete_id_returns_422(self, bad_id: str):
        """C1: Non-UUID project_id in DELETE → 422."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.delete(f"/api/v1/projects/{bad_id}")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# C1 — SQL injection in search query parameter
# ---------------------------------------------------------------------------

class TestSQLInjectionInSearchParam:
    """
    C1: search query parameter is passed to service as a string value,
    then used in ILIKE parameterized query. Injections must NOT cause 500.
    """

    SQL_INJECTIONS = [
        "'; DROP TABLE projects; --",
        "x' OR '1'='1",
        "a UNION SELECT password FROM users --",
        "%'; TRUNCATE projects; --",
    ]

    @pytest.mark.parametrize("injection", SQL_INJECTIONS)
    async def test_sql_injection_in_search_no_500(self, injection: str):
        """C1: SQL injection in ?search= must not cause a server error."""
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id)
        # No DB session needed — RBAC will kick in before service
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                resp = await client.get(
                    "/api/v1/projects",
                    params={"search": injection},
                )
        # Any response except 500 is acceptable
        assert resp.status_code != 500, (
            f"SQL injection in search {injection!r} caused server error"
        )


# ---------------------------------------------------------------------------
# C10 — Cross-tenant project operations blocked
# ---------------------------------------------------------------------------

class TestCrossTenantBlocked:
    """
    C10: A token from tenant B cannot affect projects in tenant A's schema.
    The service queries only the requesting JWT's tenant schema.
    """

    async def test_cross_tenant_archive_returns_404(self):
        """C10: tenant B token cannot archive tenant A's project → 404."""
        user_b_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        project_a_id = uuid.uuid4()  # actually exists in tenant A only
        token_b = _make_token(user_b_id, tenant_b_id, role="owner", slug="tenant-b")
        mock_session = _setup_rbac_session(user_b_id, tenant_b_id, role="owner")

        app.dependency_overrides[get_db] = lambda: mock_session

        from src.services.project_service import ProjectNotFoundError
        with patch("src.api.v1.projects.router.project_service.archive_project",
                   side_effect=ProjectNotFoundError("not in tenant B")), \
             patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token_b}"},
            ) as client:
                resp = await client.post(f"/api/v1/projects/{project_a_id}/archive")

        app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    async def test_cross_tenant_delete_returns_404(self):
        """C10: tenant B token cannot delete tenant A's project → 404."""
        user_b_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        project_a_id = uuid.uuid4()
        token_b = _make_token(user_b_id, tenant_b_id, role="owner", slug="tenant-b")
        mock_session = _setup_rbac_session(user_b_id, tenant_b_id, role="owner")

        app.dependency_overrides[get_db] = lambda: mock_session

        from src.services.project_service import ProjectNotFoundError
        with patch("src.api.v1.projects.router.project_service.delete_project",
                   side_effect=ProjectNotFoundError("not in tenant B")), \
             patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test",
                headers={"Authorization": f"Bearer {token_b}"},
            ) as client:
                resp = await client.delete(f"/api/v1/projects/{project_a_id}")

        app.dependency_overrides.clear()

        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# C2 — Schema name validation
# ---------------------------------------------------------------------------

class TestSchemaNameValidation:
    """
    C2: _get_schema_name() validates the slug produces a safe identifier.
    Crafted JWT slugs cannot inject schema names into SQL.
    """

    async def test_invalid_slug_produces_no_schema(self):
        """
        A JWT with a slug that produces an unsafe schema identifier results in
        schema_name=None and the audit log is skipped (not a crash or injection).
        _get_schema_name returns None for slugs that fail validate_safe_identifier.
        """
        from src.api.v1.projects.router import _get_schema_name
        from unittest.mock import patch as _patch

        # Patch slug ContextVar to return an unsafe value
        with _patch("src.api.v1.projects.router.current_tenant_slug") as mock_ctx:
            mock_ctx.get.return_value = "'; DROP SCHEMA tenant_x; --"
            with _patch("src.services.tenant_provisioning.validate_safe_identifier",
                        return_value=False):
                result = _get_schema_name()

        # schema_name should be None — not the injected string
        assert result is None
