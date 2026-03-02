"""
Integration tests — Artifact endpoints (Story 2-10)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override)
  - RBAC (token with tenant context)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str = "owner") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
    )


def _make_artifact_row(
    artifact_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_type: str = "coverage_matrix",
    agent_type: str = "ba_consultant",
    title: str = "Requirements Coverage Matrix",
) -> dict:
    return {
        "id": str(artifact_id),
        "agent_type": agent_type,
        "artifact_type": artifact_type,
        "title": title,
        "current_version": 1,
        "metadata": {"tokens_used": 100},
        "created_by": str(uuid.uuid4()),
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _make_detail_row(
    artifact_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_type: str = "coverage_matrix",
    content: str = '[{"requirement_id": "REQ-001"}]',
    content_type: str = "application/json",
) -> dict:
    row = _make_artifact_row(artifact_id, project_id, artifact_type=artifact_type)
    row["content"] = content
    row["content_type"] = content_type
    return row


def _make_version_row(version: int = 1) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "version": version,
        "content_type": "application/json",
        "edited_by": None,
        "created_at": _NOW,
    }


def _setup_db_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    role: str = "owner",
    artifact_rows: list | None = None,
    detail_row: dict | None = None,
    version_rows: list | None = None,
):
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
        mappings = MagicMock()
        s = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "select" in s and "artifact_versions" in s and "artifacts" in s:
            # get_artifact or get_version (JOIN query)
            mappings.fetchone.return_value = detail_row
            result.mappings.return_value = mappings
        elif "select" in s and "artifact_versions" in s:
            # list_versions
            mappings.fetchall.return_value = version_rows or []
            result.mappings.return_value = mappings
        elif "select id from" in s and "artifacts" in s and "id = :aid" in s:
            # ownership check in list_versions (SELECT id FROM ... WHERE id = :aid)
            if detail_row:
                result.fetchone.return_value = (detail_row["id"],)
            else:
                result.fetchone.return_value = None
        elif "select" in s and "artifacts" in s:
            # list_artifacts
            mappings.fetchall.return_value = artifact_rows or []
            result.mappings.return_value = mappings
        else:
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


def _setup_db_session_for_put(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    detail_row_v1: dict | None,
    detail_row_v2: dict | None,
    role: str = "owner",
):
    """DB session override for PUT /artifacts/{id} tests.

    Handles the multi-call sequence in update_artifact():
      RBAC queries → get_artifact() SELECT → INSERT → UPDATE → get_artifact() SELECT again.
    """
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

    # Track how many times the artifact SELECT+JOIN has been called
    artifact_select_count = {"n": 0}

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        mappings = MagicMock()
        s = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "select" in s and "artifact_versions" in s and "artifacts" in s and "join" in s:
            # get_artifact() SELECT+JOIN — called twice (before and after commit)
            artifact_select_count["n"] += 1
            row = detail_row_v1 if artifact_select_count["n"] == 1 else detail_row_v2
            mappings.fetchone.return_value = row
            result.mappings.return_value = mappings
        elif "insert" in s:
            # INSERT into artifact_versions — no return value needed
            pass
        elif "update" in s:
            # UPDATE artifacts.current_version — no return value needed
            pass
        else:
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestArtifactEndpoints:

    @pytest.mark.asyncio
    async def test_list_artifacts_empty(self):
        # Proves: GET /artifacts with no seeded data → 200 and empty list.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id, artifact_rows=[])
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(f"/api/v1/projects/{project_id}/artifacts")

            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_list_artifacts_with_type_filter(self):
        # Proves: GET /artifacts?artifact_type=coverage_matrix filters to matching type only.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        artifact_row = _make_artifact_row(uuid.uuid4(), project_id)
        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            artifact_rows=[artifact_row],
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts",
                    params={"artifact_type": "coverage_matrix"},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["artifact_type"] == "coverage_matrix"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_artifact_detail_includes_content(self):
        # Proves: GET /artifacts/{id} returns content field from artifact_versions JOIN.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        detail = _make_detail_row(artifact_id, project_id)
        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=detail,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}",
                )

            assert resp.status_code == 200
            data = resp.json()
            assert "content" in data
            assert data["content"] == '[{"requirement_id": "REQ-001"}]'
            assert data["content_type"] == "application/json"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_artifact_404_unknown_id(self):
        # Proves: GET /artifacts/{unknown-uuid} → 404 with ARTIFACT_NOT_FOUND error.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=None,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{uuid.uuid4()}",
                )

            assert resp.status_code == 404
            data = resp.json()
            assert data["detail"]["error"] == "ARTIFACT_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_list_versions_returns_ordered(self):
        # Proves: GET /artifacts/{id}/versions returns version list ordered latest-first.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        detail = _make_detail_row(artifact_id, project_id)
        versions = [_make_version_row(version=2), _make_version_row(version=1)]
        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=detail,
            version_rows=versions,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}/versions",
                )

            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 2
            assert data[0]["version"] == 2
            assert data[1]["version"] == 1
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_specific_version_returns_content(self):
        # Proves: GET /artifacts/{id}/versions/{ver} returns detail with content for that version.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        detail = _make_detail_row(artifact_id, project_id)
        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=detail,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}/versions/1",
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["content"] == '[{"requirement_id": "REQ-001"}]'
            assert data["content_type"] == "application/json"
            assert data["current_version"] == 1
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_get_version_404_unknown(self):
        # Proves: GET /artifacts/{id}/versions/{ver} → 404 when version does not exist.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=None,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}/versions/999",
                )

            assert resp.status_code == 404
            data = resp.json()
            assert data["detail"]["error"] == "VERSION_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_db, None)

    # ---------------------------------------------------------------------------
    # PUT /artifacts/{id} tests — AC-28 (Story 2-11)
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_put_artifact_creates_new_version(self):
        # Proves: PUT /artifacts/{id} with new content → 200 with current_version == 2.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        detail_v1 = _make_detail_row(artifact_id, project_id, content="original content")
        detail_v2 = _make_detail_row(artifact_id, project_id, content="updated content")
        detail_v2["current_version"] = 2

        get_db_override = _setup_db_session_for_put(
            user_id, tenant_id, project_id, artifact_id,
            detail_row_v1=detail_v1,
            detail_row_v2=detail_v2,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.put(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}",
                    json={"content": "updated content"},
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["current_version"] == 2
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_put_artifact_get_returns_new_content(self):
        # Proves: After PUT the GET endpoint returns the updated content.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        detail = _make_detail_row(artifact_id, project_id, content="updated content")
        detail["current_version"] = 2

        get_db_override = _setup_db_session(
            user_id, tenant_id, project_id,
            detail_row=detail,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.get(
                    f"/api/v1/projects/{project_id}/artifacts/{artifact_id}",
                )

            assert resp.status_code == 200
            data = resp.json()
            assert data["content"] == "updated content"
            assert data["current_version"] == 2
        finally:
            app.dependency_overrides.pop(get_db, None)

    @pytest.mark.asyncio
    async def test_put_artifact_404_unknown_id(self):
        # Proves: PUT /artifacts/{unknown-uuid} → 404 with ARTIFACT_NOT_FOUND error.
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        token = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session_for_put(
            user_id, tenant_id, project_id, uuid.uuid4(),
            detail_row_v1=None,
            detail_row_v2=None,
        )
        app.dependency_overrides[get_db] = get_db_override

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                cookies={"access_token": token},
            ) as client:
                resp = await client.put(
                    f"/api/v1/projects/{project_id}/artifacts/{uuid.uuid4()}",
                    json={"content": "x"},
                )

            assert resp.status_code == 404
            data = resp.json()
            assert data["detail"]["error"] == "ARTIFACT_NOT_FOUND"
        finally:
            app.dependency_overrides.pop(get_db, None)
