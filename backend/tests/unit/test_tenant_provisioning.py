"""
Unit Tests — TenantProvisioningService
Story: 1-2-organization-creation-setup (Task 7.2)
AC: AC3 — async tenant schema provisioning
AC: AC9 — SQL injection prevention in DDL via validate_safe_identifier
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.services.tenant_provisioning import (
    TenantProvisioningService,
    ProvisioningStatus,
    slug_to_schema_name,
    validate_safe_identifier,
    _build_base_migration_ddl,
)


pytestmark = pytest.mark.asyncio


def _make_mock_db():
    """Build a minimal async SQLAlchemy session mock for provisioning tests."""
    raw_conn = AsyncMock()
    raw_conn.transaction = MagicMock()
    raw_conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    raw_conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    raw_conn.execute = AsyncMock()
    raw_conn.fetchval = AsyncMock(return_value=None)

    sync_conn = MagicMock()
    sync_conn.get_raw_connection = AsyncMock(return_value=raw_conn)

    session = AsyncMock()
    session.connection = AsyncMock(return_value=sync_conn)
    return session, raw_conn


class TestValidateSafeIdentifier:
    """Mirrors router tests — provisioning service must also validate."""

    def test_valid_returns_true(self):
        assert validate_safe_identifier("tenant_acme") is True

    def test_injection_attempt_returns_false(self):
        assert validate_safe_identifier("t; DROP SCHEMA tenant_t CASCADE; --") is False

    def test_empty_returns_false(self):
        assert validate_safe_identifier("") is False


class TestBuildBaseMigrationDDL:
    def test_returns_list_of_strings(self):
        ddl = _build_base_migration_ddl("tenant_test")
        assert isinstance(ddl, list)
        assert len(ddl) > 0
        assert all(isinstance(s, str) for s in ddl)

    def test_ddl_contains_schema_name(self):
        ddl = _build_base_migration_ddl("tenant_acme")
        combined = " ".join(ddl)
        assert "tenant_acme" in combined

    def test_ddl_contains_org_members(self):
        ddl = _build_base_migration_ddl("tenant_acme")
        combined = " ".join(ddl).lower()
        assert "org_members" in combined

    def test_ddl_contains_audit_logs(self):
        ddl = _build_base_migration_ddl("tenant_acme")
        combined = " ".join(ddl).lower()
        assert "audit_logs" in combined


class TestProvisionTenant:
    async def test_provision_returns_ready_on_success(self):
        db, raw_conn = _make_mock_db()
        svc = TenantProvisioningService()
        status = await svc.provision_tenant(
            tenant_id=uuid.uuid4(),
            slug="acme-corp",
            db=db,
        )
        assert status == ProvisioningStatus.READY

    async def test_provision_executes_create_schema(self):
        db, raw_conn = _make_mock_db()
        svc = TenantProvisioningService()
        await svc.provision_tenant(
            tenant_id=uuid.uuid4(),
            slug="my-org",
            db=db,
        )
        # raw_conn.execute must have been called at least once (CREATE SCHEMA)
        assert raw_conn.execute.await_count >= 1
        first_call_sql = str(raw_conn.execute.call_args_list[0])
        assert "tenant_my_org" in first_call_sql

    async def test_provision_rejects_unsafe_slug(self):
        db, _ = _make_mock_db()
        svc = TenantProvisioningService()
        with pytest.raises(ValueError, match="safety validation"):
            await svc.provision_tenant(
                tenant_id=uuid.uuid4(),
                slug="bad'; DROP SCHEMA",
                db=db,
            )

    async def test_provision_fails_on_db_error_returns_failed(self):
        db, raw_conn = _make_mock_db()
        raw_conn.execute = AsyncMock(side_effect=Exception("connection refused"))
        # Also mock the drop fallback so it doesn't raise
        raw_conn.execute = AsyncMock(side_effect=[Exception("connection refused"), None])

        svc = TenantProvisioningService()
        with pytest.raises(RuntimeError):
            await svc.provision_tenant(
                tenant_id=uuid.uuid4(),
                slug="failing-org",
                db=db,
            )

    async def test_correlation_id_accepted(self):
        """provision_tenant accepts optional correlation_id for structured logs."""
        db, raw_conn = _make_mock_db()
        svc = TenantProvisioningService()
        status = await svc.provision_tenant(
            tenant_id=uuid.uuid4(),
            slug="log-org",
            db=db,
            correlation_id="test-corr-123",
        )
        assert status == ProvisioningStatus.READY
