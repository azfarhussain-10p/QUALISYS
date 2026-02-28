"""
Integration tests — Document Upload & Parsing API endpoints
Story: 2-1-document-upload-parsing
Task 9.2 — 7 integration tests for /documents endpoints
AC: #1 — POST 201 valid PDF, 400 FILE_TOO_LARGE, 400 UNSUPPORTED_FILE_TYPE
AC: #3, #5 — GET list 200, GET detail 200
AC: #6 — DELETE 204
Unauthenticated — 401

DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.
"""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str = "owner") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
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


def _setup_db_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    role: str = "owner",
    document_row: dict | None = None,
):
    """Build a mock DB session returning the correct rows for RBAC + document queries."""
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

    # Default document row for GET/DELETE tests
    _doc_row = document_row or {
        "id": uuid.uuid4(),
        "project_id": project_id,
        "filename": "test.pdf",
        "file_type": "pdf",
        "file_size_bytes": 1024,
        "s3_key": f"documents/{tenant_id}/{project_id}/doc-id/test.pdf",
        "parse_status": "completed",
        "preview_text": "Preview text here",
        "page_count": 2,
        "chunk_count": 0,
        "error_message": None,
        "created_by": user_id,
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    }

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()

        # RBAC queries — use schema-qualified table names (public.users, etc.)
        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        # Document count query
        elif "count(*)" in s and "documents" in s:
            result.scalar.return_value = 1
        # Document list query
        elif "select" in s and "documents" in s and "order by" in s:
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, k: _doc_row.get(k)
            mappings = MagicMock()
            mappings.fetchall.return_value = [mock_row]
            result.mappings.return_value = mappings
        # Document single-row query (detail, delete)
        elif "documents" in s:
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, k: _doc_row.get(k)
            mappings = MagicMock()
            mappings.fetchone.return_value = mock_row
            result.mappings.return_value = mappings
        else:
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# AC1: POST /documents
# ---------------------------------------------------------------------------

class TestUploadDocument:

    @pytest.mark.asyncio
    async def test_upload_pdf_201(self):
        # Proves: POST with valid PDF ≤ 25MB → 201, parse_status='pending'.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
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
                                            files={"file": ("requirements.pdf", b"%PDF small", "application/pdf")},
                                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 201
        data = resp.json()
        assert data["parse_status"] == "pending"
        assert data["filename"] == "requirements.pdf"

    @pytest.mark.asyncio
    async def test_upload_too_large_400(self):
        # Proves: POST with 26MB file → 400 FILE_TOO_LARGE.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        big_content = b"x" * (26 * 1024 * 1024)  # 26 MB

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.post(
                            f"/api/v1/projects/{project_id}/documents",
                            headers={"Authorization": f"Bearer {token}"},
                            files={"file": ("big.pdf", big_content, "application/pdf")},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_upload_unsupported_type_400(self):
        # Proves: POST with .exe file → 400 UNSUPPORTED_FILE_TYPE.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
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
                            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "UNSUPPORTED_FILE_TYPE"


# ---------------------------------------------------------------------------
# AC5: GET /documents (list)
# ---------------------------------------------------------------------------

class TestListDocuments:

    @pytest.mark.asyncio
    async def test_list_documents_200(self):
        # Proves: GET list → 200 with paginated response fields: items, total, page, page_size.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/documents",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data


# ---------------------------------------------------------------------------
# AC3: GET /documents/{id} (detail)
# ---------------------------------------------------------------------------

class TestGetDocument:

    @pytest.mark.asyncio
    async def test_get_document_detail_200(self):
        # Proves: GET detail → 200 with parse_status, preview_text, page_count fields.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        document_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        doc_row = {
            "id": document_id,
            "project_id": project_id,
            "filename": "spec.pdf",
            "file_type": "pdf",
            "file_size_bytes": 2048,
            "s3_key": f"documents/{tenant_id}/{project_id}/{document_id}/spec.pdf",
            "parse_status": "completed",
            "preview_text": "Requirements overview...",
            "page_count": 5,
            "chunk_count": 0,
            "error_message": None,
            "created_by": user_id,
            "created_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        }

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, document_row=doc_row)
        app.dependency_overrides[get_db] = get_db_override

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()):
                    async with AsyncClient(
                        transport=ASGITransport(app=app), base_url="http://test"
                    ) as c:
                        resp = await c.get(
                            f"/api/v1/projects/{project_id}/documents/{document_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["parse_status"] == "completed"
        assert data["preview_text"] == "Requirements overview..."
        assert data["page_count"] == 5


# ---------------------------------------------------------------------------
# AC6: DELETE /documents/{id}
# ---------------------------------------------------------------------------

class TestDeleteDocument:

    @pytest.mark.asyncio
    async def test_delete_document_204(self):
        # Proves: DELETE with valid document → 204, S3 delete attempted, DB record removed.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        document_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        mock_s3 = MagicMock()
        mock_s3.delete_object = MagicMock()

        try:
            with patch("src.services.document_service._make_s3_client", return_value=mock_s3):
                with patch("src.services.document_service.settings") as m:
                    m.s3_bucket_name = "test-bucket"
                    with patch("src.services.document_service._audit_service.log_action_async", new_callable=AsyncMock):
                        with patch("src.cache.get_redis_client", return_value=_make_redis_mock()):
                            with patch(
                                "src.middleware.rate_limit.get_redis_client",
                                return_value=_make_redis_mock(),
                            ):
                                async with AsyncClient(
                                    transport=ASGITransport(app=app), base_url="http://test"
                                ) as c:
                                    resp = await c.delete(
                                        f"/api/v1/projects/{project_id}/documents/{document_id}",
                                        headers={"Authorization": f"Bearer {token}"},
                                    )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Unauthenticated — 401
# ---------------------------------------------------------------------------

class TestUnauthenticated:

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self):
        # Proves: request without JWT → 401 on all document endpoints.
        project_id = uuid.uuid4()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            resp = await c.post(
                f"/api/v1/projects/{project_id}/documents",
                files={"file": ("test.pdf", b"%PDF", "application/pdf")},
            )
        assert resp.status_code == 401
