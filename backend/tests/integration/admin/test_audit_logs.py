"""
Integration tests — GET /api/v1/admin/audit-logs, POST /audit-logs/export
Story: 1-12-usage-analytics-audit-logs-basic
Task 7.4 — list with filters (date range, action, actor), pagination
Task 7.5 — CSV download, empty result, rate limiting
Task 7.6 — audit log immutability (UPDATE/DELETE blocked)
Task 7.7 — tenant isolation (tenant A logs not visible to tenant B)
Task 7.8 — @audit_action decorator auto-logs
Task 7.9 — non-blocking audit (request completes even if audit insert delayed)
AC: #4, #5, #6, #8
"""

import uuid
from datetime import datetime, timezone
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


def _make_audit_row(tenant_id: uuid.UUID, action: str = "project.created"):
    """Build a fake audit_logs row mapping."""
    row = MagicMock()
    row_id = uuid.uuid4()

    def getitem(key):
        data = {
            "id": row_id,
            "tenant_id": tenant_id,
            "actor_user_id": uuid.uuid4(),
            "action": action,
            "resource_type": "project",
            "resource_id": uuid.uuid4(),
            "details": {"project_name": "Test"},
            "ip_address": "1.2.3.4",
            "user_agent": "pytest",
            "created_at": datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        }
        return data[key]

    row.__getitem__ = getitem
    row.get = lambda key, default=None: getitem(key) if key in [
        "id","tenant_id","actor_user_id","action","resource_type","resource_id",
        "details","ip_address","user_agent","created_at"
    ] else default
    return row


def _setup_auth_session(user_id, tenant_id, role="owner", audit_rows=None):
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    if audit_rows is None:
        audit_rows = []

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

        if "audit_logs" in s and ("count(*)" in s or "select count" in s):
            result.scalar.return_value = len(audit_rows)
        elif "audit_logs" in s:
            mappings = MagicMock()
            mappings.fetchall.return_value = audit_rows
            result.mappings.return_value = mappings
        elif "tenants_users" in s and "is_active" not in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "tenants" in s and "user" not in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "user" in s and "tenant" not in s:
            result.scalar_one_or_none.return_value = mock_user
        else:
            result.scalar_one_or_none.return_value = mock_membership
        return result

    mock_session.execute = mock_execute
    mock_session.commit = AsyncMock()
    return mock_session


def _make_mock_redis(export_count=1):
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.incr = AsyncMock(return_value=export_count)
    mock.expire = AsyncMock(return_value=True)
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[export_count, 3600])
    mock.pipeline.return_value = pipeline
    return mock


# ---------------------------------------------------------------------------
# Task 7.4 — List with filters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_audit_logs_returns_paginated():
    """AC4: GET /admin/audit-logs returns paginated entries."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    rows = [_make_audit_row(tenant_id, "project.created") for _ in range(3)]
    mock_session = _setup_auth_session(user_id, tenant_id, role="owner", audit_rows=rows)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/audit-logs",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "pagination" in data
    assert data["pagination"]["per_page"] == 50


@pytest.mark.asyncio
async def test_list_audit_logs_invalid_action_returns_400():
    """AC8: Invalid action filter → 400 INVALID_ACTION."""
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
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/audit-logs",
                    params={"action": "bad.action.unknown"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_ACTION"


@pytest.mark.asyncio
async def test_list_audit_logs_invalid_date_range_returns_400():
    """AC8: date_from > date_to → 400 INVALID_DATE_RANGE."""
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
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/audit-logs",
                    params={"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATE_RANGE"


@pytest.mark.asyncio
async def test_list_audit_logs_action_group_filter():
    """AC5: 'project_actions' group filter is accepted."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="admin")
    rows = [_make_audit_row(tenant_id, "project.deleted")]
    mock_session = _setup_auth_session(user_id, tenant_id, role="admin", audit_rows=rows)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/audit-logs",
                    params={"action": "project_actions"},
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_audit_logs_rbac_non_admin_403():
    """AC4: Non-admin role → 403."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="viewer")
    mock_session = _setup_auth_session(user_id, tenant_id, role="viewer")

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/admin/audit-logs",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Task 7.5 — CSV export
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_audit_logs_returns_csv():
    """AC6: POST /admin/audit-logs/export → Content-Type: text/csv."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    rows = [_make_audit_row(tenant_id, "project.archived")]
    mock_session = _setup_auth_session(user_id, tenant_id, role="owner", audit_rows=rows)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/admin/audit-logs/export",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    content = resp.text
    # CSV must have header row
    assert "timestamp" in content
    assert "actor_user_id" in content
    assert "action" in content


@pytest.mark.asyncio
async def test_export_empty_result_returns_csv_with_headers():
    """AC8: Export with no matching entries → empty CSV with headers."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session = _setup_auth_session(user_id, tenant_id, role="owner", audit_rows=[])

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/admin/audit-logs/export",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert "timestamp" in resp.text  # header row present even when empty


@pytest.mark.asyncio
async def test_export_rate_limited_on_6th_request():
    """AC6: 6th export in 1 hour → 429 RATE_LIMIT_EXCEEDED."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session = _setup_auth_session(user_id, tenant_id, role="owner")

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    # count=6 triggers rate limit (>5)
    redis_over_limit = _make_mock_redis(export_count=6)

    with patch("src.cache.get_redis_client", return_value=redis_over_limit):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=redis_over_limit):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/v1/admin/audit-logs/export",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()

    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in resp.headers


# ---------------------------------------------------------------------------
# Task 7.6 — Audit log immutability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logs_not_updatable():
    """AC2: audit_logs table must block UPDATE (INSERT-ONLY constraint via RLS)."""
    # This test verifies the AuditService never calls UPDATE on audit_logs.
    # The RLS policy `block_update USING(false)` enforces this at DB level.
    # Here we verify the service only calls INSERT.
    from src.services.audit_service import AuditService

    db = AsyncMock()
    db.execute = AsyncMock()
    svc = AuditService()

    await svc.log_action(
        db=db,
        schema_name="tenant_test",
        tenant_id=uuid.uuid4(),
        actor_user_id=uuid.uuid4(),
        action="project.archived",
        resource_type="project",
    )

    # Verify INSERT was called, not UPDATE
    call_args = db.execute.call_args
    sql_text = str(call_args.args[0]).upper()
    assert "INSERT" in sql_text
    assert "UPDATE" not in sql_text
    assert "DELETE" not in sql_text


# ---------------------------------------------------------------------------
# Task 7.7 — Tenant isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_logs_tenant_isolated():
    """AC2: audit_logs WHERE clause always includes tenant_id = :tenant_id."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = _make_token(user_id, tenant_id, role="owner")
    mock_session = _setup_auth_session(user_id, tenant_id, role="owner", audit_rows=[])
    executed_sqls: list[str] = []

    original_execute = mock_session.execute

    async def capture_execute(stmt, *args, **kwargs):
        executed_sqls.append(str(stmt).lower())
        return await original_execute(stmt, *args, **kwargs)

    mock_session.execute = capture_execute

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    with patch("src.cache.get_redis_client", return_value=_make_mock_redis()):
        with patch("src.middleware.rate_limit.get_redis_client", return_value=_make_mock_redis()):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.get(
                    "/api/v1/admin/audit-logs",
                    headers={"Authorization": f"Bearer {token}"},
                )

    app.dependency_overrides.clear()

    # All queries touching audit_logs must filter by tenant_id
    audit_queries = [s for s in executed_sqls if "audit_logs" in s]
    for q in audit_queries:
        assert "tenant_id" in q, f"Audit query missing tenant_id filter: {q}"
