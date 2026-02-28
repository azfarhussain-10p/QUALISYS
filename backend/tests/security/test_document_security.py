"""
Security Tests — Document Endpoints
Story: 2-1-document-upload-parsing
Task 9.3 — 4 security tests (RBAC + cross-tenant isolation)
AC: #7 — Viewer role → 403; qa-automation role → 201; cross-project → 404; cross-tenant → 403/404

DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.
DoD A8: test_cross_tenant_403 and S3 key isolation require independent reviewer sign-off.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str, tenant_slug: str = "test-org") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug=tenant_slug,
    )


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
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    return mock


def _setup_rbac_mock(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str):
    """Build DB mock that returns the correct User + Tenant + TenantUser for RBAC checks."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.email = f"{role}@test.com"

    mock_tenant = MagicMock(spec=Tenant)
    mock_tenant.id = tenant_id
    mock_tenant.slug = "test-org"

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
        # Use schema-qualified names — SQLAlchemy compiles to public.users, public.tenants, etc.
        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# AC7: Viewer role → 403
# ---------------------------------------------------------------------------

class TestViewerRoleBlocked:

    async def test_viewer_role_403(self):
        # Proves: Viewer JWT → 403 on POST upload; viewer is not in allowed roles.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="viewer")

        get_db_override = _setup_rbac_mock(user_id, tenant_id, "viewer")
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.post(
                            f"/api/v1/projects/{project_id}/documents",
                            headers={"Authorization": f"Bearer {token}"},
                            files={"file": ("test.pdf", b"%PDF", "application/pdf")},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AC7: Cross-project isolation → 404
# ---------------------------------------------------------------------------

class TestCrossProjectIsolation:

    async def test_cross_project_404(self):
        # Proves: document from project A accessed via project B's endpoint → 404.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_b_id = uuid.uuid4()  # different project from where doc belongs
        document_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="owner")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.email = "owner@test.com"

        mock_tenant = MagicMock(spec=Tenant)
        mock_tenant.id = tenant_id
        mock_tenant.slug = "test-org"

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
            # Use schema-qualified names
            if "public.tenants_users" in s:
                result.scalar_one_or_none.return_value = mock_membership
            elif "public.users" in s and "public.tenants" not in s:
                result.scalar_one_or_none.return_value = mock_user
            elif "public.tenants" in s:
                result.scalar_one_or_none.return_value = mock_tenant
            elif "documents" in s:
                # No document found for project_b_id (cross-project isolation)
                mappings = MagicMock()
                mappings.fetchone.return_value = None
                result.mappings.return_value = mappings
            else:
                result.scalar_one_or_none.return_value = mock_membership
            return result

        mock_session.execute = mock_execute

        app.dependency_overrides[get_db] = lambda: mock_session.__aenter__()

        async def get_db_override():
            yield mock_session

        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_b_id}/documents/{document_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# AC7 + DoD A8: Cross-tenant isolation → 403/404
# NOTE: Independent sign-off required per DoD A8 before marking story DONE.
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:

    async def test_cross_tenant_403(self):
        """
        DoD A8 verify-task: requires independent reviewer to confirm cross-tenant
        isolation is enforced at the service layer (slug_to_schema_name scoping),
        not only at the RBAC/router layer.

        S3 key isolation verify-task: documents/{tenant_id}/... path prevents
        cross-tenant S3 access — independent reviewer must confirm this is
        enforced in DocumentService.upload_document() before DoD is complete.
        """
        # Proves: Tenant B user cannot access Tenant A's documents → 403/404
        # via RBAC: TenantUser.tenant_id mismatch → membership not found → 403.
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        project_a_id = uuid.uuid4()
        document_id = uuid.uuid4()

        # Tenant B user presents tenant B token but tries to access project A's docs
        token = _make_token(user_b_id, tenant_b_id, role="owner", tenant_slug="tenant-b")

        from src.models.user import User
        from src.models.tenant import Tenant, TenantUser

        mock_user_b = MagicMock(spec=User)
        mock_user_b.id = user_b_id

        # Tenant A exists but NOT Tenant B — simulates cross-tenant access attempt
        mock_session = AsyncMock()

        async def mock_execute(stmt, *args, **kwargs):
            result = MagicMock()
            s = str(stmt).lower()
            # Use schema-qualified names
            if "public.tenants_users" in s:
                result.scalar_one_or_none.return_value = None
            elif "public.users" in s and "public.tenants" not in s:
                result.scalar_one_or_none.return_value = mock_user_b
            elif "public.tenants" in s:
                # Tenant B not found (tenant from JWT is B, but only A exists in this DB)
                result.scalar_one_or_none.return_value = None
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute = mock_execute

        async def get_db_override():
            yield mock_session

        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_a_id}/documents/{document_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        # Tenant not found → 404 (ORG_NOT_FOUND) or 403 — both prevent cross-tenant data access
        assert resp.status_code in (403, 404)


# ---------------------------------------------------------------------------
# AC7: qa-automation role can upload
# ---------------------------------------------------------------------------

class TestQaAutomationCanUpload:

    async def test_qa_automation_can_upload(self):
        # Proves: qa-automation role is in the allowed roles list → 201 on valid upload.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, role="qa-automation")

        get_db_override = _setup_rbac_mock(user_id, tenant_id, "qa-automation")
        app.dependency_overrides[get_db] = get_db_override

        mock_s3 = MagicMock()
        mock_s3.put_object = MagicMock()

        try:
            with patch("src.services.document_service._make_s3_client", return_value=mock_s3):
                with patch("src.services.document_service.settings") as m:
                    m.s3_bucket_name = "test-bucket"
                    m.s3_region = "us-east-1"
                    m.aws_access_key_id = ""
                    m.aws_secret_access_key = ""
                    # Patch audit log method (not asyncio.create_task — that breaks SQLAlchemy __aexit__)
                    with patch("src.services.document_service._audit_service.log_action_async", new_callable=AsyncMock):
                        # Patch background parse task to prevent real DB connection
                        with patch("src.api.v1.documents.router.parse_document_task", new_callable=AsyncMock):
                            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                                with patch(
                                    "src.middleware.rate_limit.get_redis_client",
                                    return_value=_make_redis_mock(),
                                ):
                                    async with AsyncClient(
                                        transport=ASGITransport(app=app), base_url="http://test"
                                    ) as c:
                                        resp = await c.post(
                                            f"/api/v1/projects/{project_id}/documents",
                                            headers={"Authorization": f"Bearer {token}"},
                                            files={
                                                "file": (
                                                    "reqs.pdf",
                                                    b"%PDF small pdf content",
                                                    "application/pdf",
                                                )
                                            },
                                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
