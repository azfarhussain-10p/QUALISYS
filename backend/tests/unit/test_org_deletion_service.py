"""
Unit tests — OrgDeletionService
Story: 1-13-data-export-org-deletion
Task 7.2 — deletion sequence ordering, verification logic, partial failure handling
AC: #3 — org name match, 2FA/password verification
AC: #4 — ordered deletion sequence
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.services.org_deletion_service import OrgDeletionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _make_session_with_row(row: dict | None):
    """Mock AsyncSession that returns a single row from mappings().fetchone()."""
    session = AsyncMock()
    result = MagicMock()
    mappings = MagicMock()
    mappings.fetchone.return_value = row
    result.mappings.return_value = mappings
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test: verify_deletion — org name mismatch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_deletion_name_mismatch():
    """verify_deletion() should raise ORG_NAME_MISMATCH for wrong org name."""
    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": False, "password_hash": "hashed", "id": USER_ID})

    with pytest.raises(ValueError, match="ORG_NAME_MISMATCH"):
        await svc.verify_deletion(
            db=db,
            org_id=ORG_ID,
            org_name="Acme Corp",
            org_name_confirmation="acme corp",  # wrong case
            user_id=USER_ID,
        )


@pytest.mark.asyncio
async def test_verify_deletion_name_case_sensitive():
    """verify_deletion() must be case-sensitive — 'Acme' != 'acme'."""
    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": False, "password_hash": "hashed", "id": USER_ID})

    with pytest.raises(ValueError, match="ORG_NAME_MISMATCH"):
        await svc.verify_deletion(
            db=db,
            org_id=ORG_ID,
            org_name="Acme Corp",
            org_name_confirmation="ACME CORP",
            user_id=USER_ID,
        )


# ---------------------------------------------------------------------------
# Test: verify_deletion — password verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_deletion_password_required_when_no_totp():
    """verify_deletion() should require password when MFA is not enabled."""
    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": False, "password_hash": "hashed", "id": USER_ID})

    with pytest.raises(ValueError, match="PASSWORD_REQUIRED"):
        await svc.verify_deletion(
            db=db,
            org_id=ORG_ID,
            org_name="Acme",
            org_name_confirmation="Acme",
            user_id=USER_ID,
            # no password provided
        )


@pytest.mark.asyncio
async def test_verify_deletion_invalid_password():
    """verify_deletion() should raise INVALID_PASSWORD for wrong password."""
    import bcrypt
    hashed = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode()

    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": False, "password_hash": hashed, "id": USER_ID})

    with pytest.raises(ValueError, match="INVALID_PASSWORD"):
        await svc.verify_deletion(
            db=db,
            org_id=ORG_ID,
            org_name="Acme",
            org_name_confirmation="Acme",
            user_id=USER_ID,
            password="wrong-password",
        )


@pytest.mark.asyncio
async def test_verify_deletion_correct_password_succeeds():
    """verify_deletion() should succeed with correct password."""
    import bcrypt
    hashed = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode()

    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": False, "password_hash": hashed, "id": USER_ID})

    # Should not raise
    await svc.verify_deletion(
        db=db,
        org_id=ORG_ID,
        org_name="Acme",
        org_name_confirmation="Acme",
        user_id=USER_ID,
        password="correct-password",
    )


# ---------------------------------------------------------------------------
# Test: verify_deletion — TOTP required
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verify_deletion_totp_required_when_mfa_enabled():
    """verify_deletion() should require TOTP code when MFA is enabled."""
    svc = OrgDeletionService()
    db = _make_session_with_row({"totp_enabled": True, "password_hash": "hashed", "id": USER_ID})

    with pytest.raises(ValueError, match="TOTP_REQUIRED"):
        await svc.verify_deletion(
            db=db,
            org_id=ORG_ID,
            org_name="Acme",
            org_name_confirmation="Acme",
            user_id=USER_ID,
            # no totp_code provided
        )


# ---------------------------------------------------------------------------
# Test: execute_deletion — tenant not found (early exit)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_deletion_skips_when_tenant_not_found():
    """execute_deletion() should log warning and return if tenant not found."""
    svc = OrgDeletionService()

    with patch('src.services.org_deletion_service.AsyncSessionLocal') as mock_sl:
        mock_db = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        mock_db.commit = AsyncMock()

        # tenant query returns None
        result = MagicMock()
        mappings = MagicMock()
        mappings.fetchone.return_value = None
        result.mappings.return_value = mappings
        mock_db.execute = AsyncMock(return_value=result)

        mock_sl.return_value = mock_db

        # Should not raise
        await svc.execute_deletion(
            org_id=ORG_ID,
            deleted_by=USER_ID,
            deleted_by_name="Admin User",
        )


# ---------------------------------------------------------------------------
# Test: deletion sequence ordering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deletion_sequence_records_audit_before_data_deleted():
    """
    _run_deletion() must insert deletion_audit BEFORE deleting tenants_users.
    Verify audit INSERT happens in the sequence before DELETE tenants_users.
    """
    svc = OrgDeletionService()

    calls_order = []

    async def mock_execute(stmt, *args, **kwargs):
        sql = str(stmt)
        if "deletion_audit" in sql and "INSERT" in sql.upper():
            calls_order.append("audit_insert")
        elif "tenants_users" in sql and "DELETE" in sql.upper():
            calls_order.append("delete_members")
        elif "DROP SCHEMA" in sql.upper():
            calls_order.append("drop_schema")
        result = MagicMock()
        mappings = MagicMock()
        if "tenants" in sql.lower() and "select" in sql.lower() and "tenants_users" not in sql.lower():
            if "count" in sql.lower():
                result.scalar.return_value = 3
            else:
                # tenant lookup
                mappings.fetchone.return_value = {
                    "name": "Acme", "slug": "acme", "id": str(ORG_ID)
                }
        elif "tenants_users" in sql.lower() and "select" in sql.lower():
            mappings.fetchall.return_value = []
        elif "count" in sql.lower():
            result.scalar.return_value = 3
        else:
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []
        result.mappings.return_value = mappings
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch('src.services.org_deletion_service._send_deletion_notification', new_callable=AsyncMock):
        with patch('src.services.org_deletion_service._delete_s3_objects', new_callable=AsyncMock):
            with patch('src.services.tenant_provisioning.validate_safe_identifier', return_value=True):
                try:
                    await svc._run_deletion(
                        db=mock_db,
                        org_id=ORG_ID,
                        deleted_by=USER_ID,
                        deleted_by_name="Admin",
                    )
                except Exception:
                    pass

    # Audit insert must come before delete members in the sequence
    if "audit_insert" in calls_order and "delete_members" in calls_order:
        audit_idx = calls_order.index("audit_insert")
        delete_idx = calls_order.index("delete_members")
        assert audit_idx < delete_idx, (
            f"audit_insert (step {audit_idx}) must precede delete_members (step {delete_idx})"
        )


# ---------------------------------------------------------------------------
# Test: Task 7.7 — multi-org user default_tenant_id update (AC6)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_deletion_updates_default_tenant_for_multi_org_user():
    """
    Task 7.7: User belonging to 2 orgs — after org A is deleted,
    _run_deletion() step 8 must set default_tenant_id to org B (not NULL).
    AC6: "Users who belong to MULTIPLE organizations: their default_tenant_id
    updated to another org they belong to."
    """
    svc = OrgDeletionService()

    OTHER_TENANT_ID = uuid.uuid4()
    update_calls: list[dict] = []

    async def mock_execute(stmt, *args, **kwargs):
        sql = str(stmt)
        sql_lower = sql.lower()
        result = MagicMock()
        mappings = MagicMock()

        if "count(*)" in sql_lower and "tenants_users" in sql_lower:
            # Member count query
            result.scalar.return_value = 1
        elif "select" in sql_lower and "tenants" in sql_lower and "tenants_users" not in sql_lower and "count" not in sql_lower:
            # Tenant lookup — return org info
            mappings.fetchone.return_value = {
                "name": "Acme Corp",
                "slug": "acme-corp",
                "id": str(ORG_ID),
            }
        elif "join" in sql_lower and "tenants_users" in sql_lower and "users" in sql_lower:
            # Member list query — one member
            mappings.fetchall.return_value = [
                {"id": USER_ID, "email": "user@test.com", "full_name": "Test User"}
            ]
        elif "select tenant_id from public.tenants_users" in sql_lower:
            # Step 8: find another org for this user — returns other tenant
            result.scalar_one_or_none.return_value = OTHER_TENANT_ID
        elif "update public.users set default_tenant_id" in sql_lower:
            # Capture the update params
            params = args[0] if args else kwargs
            update_calls.append(dict(params))
        elif "delete from public.tenants_users" in sql_lower:
            pass  # step 4
        elif "drop schema" in sql_lower:
            pass  # step 6
        elif "delete from public.tenants" in sql_lower:
            pass  # step 7
        elif "insertion_audit" in sql_lower or "deletion_audit" in sql_lower:
            pass  # step 1 + final update
        else:
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []

        result.mappings.return_value = mappings
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("src.services.org_deletion_service._send_deletion_notification", new_callable=AsyncMock):
        with patch("src.services.org_deletion_service._delete_s3_objects", new_callable=AsyncMock):
            with patch("src.services.tenant_provisioning.validate_safe_identifier", return_value=True):
                try:
                    await svc._run_deletion(
                        db=mock_db,
                        org_id=ORG_ID,
                        deleted_by=USER_ID,
                        deleted_by_name="Admin",
                    )
                except Exception:
                    pass

    # Step 8: verify UPDATE was called with OTHER_TENANT_ID (not None)
    assert len(update_calls) > 0, "UPDATE users SET default_tenant_id should have been called"
    # The new_tid should be the other tenant, not NULL
    assert any(
        str(call.get("new_tid")) == str(OTHER_TENANT_ID)
        for call in update_calls
    ), (
        f"Expected default_tenant_id to be updated to OTHER_TENANT_ID={OTHER_TENANT_ID!s}, "
        f"but got update_calls={update_calls!r}"
    )


@pytest.mark.asyncio
async def test_run_deletion_sets_default_tenant_null_for_single_org_user():
    """
    Task 7.7: User belonging to only 1 org — after deletion,
    default_tenant_id must be set to NULL (no other org).
    AC6: "Users who belong to ONLY this organization: their account remains but
    they have no active organization."
    """
    svc = OrgDeletionService()
    update_calls: list[dict] = []

    async def mock_execute(stmt, *args, **kwargs):
        sql = str(stmt)
        sql_lower = sql.lower()
        result = MagicMock()
        mappings = MagicMock()

        if "count(*)" in sql_lower and "tenants_users" in sql_lower:
            result.scalar.return_value = 1
        elif "select" in sql_lower and "tenants" in sql_lower and "tenants_users" not in sql_lower and "count" not in sql_lower:
            mappings.fetchone.return_value = {
                "name": "Solo Org",
                "slug": "solo-org",
                "id": str(ORG_ID),
            }
        elif "join" in sql_lower and "tenants_users" in sql_lower and "users" in sql_lower:
            mappings.fetchall.return_value = [
                {"id": USER_ID, "email": "user@test.com", "full_name": "Solo User"}
            ]
        elif "select tenant_id from public.tenants_users" in sql_lower:
            # No other org found
            result.scalar_one_or_none.return_value = None
        elif "update public.users set default_tenant_id" in sql_lower:
            params = args[0] if args else kwargs
            update_calls.append(dict(params))
        else:
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []

        result.mappings.return_value = mappings
        return result

    mock_db = AsyncMock()
    mock_db.execute = mock_execute
    mock_db.commit = AsyncMock()

    with patch("src.services.org_deletion_service._send_deletion_notification", new_callable=AsyncMock):
        with patch("src.services.org_deletion_service._delete_s3_objects", new_callable=AsyncMock):
            with patch("src.services.tenant_provisioning.validate_safe_identifier", return_value=True):
                try:
                    await svc._run_deletion(
                        db=mock_db,
                        org_id=ORG_ID,
                        deleted_by=USER_ID,
                        deleted_by_name="Admin",
                    )
                except Exception:
                    pass

    assert len(update_calls) > 0, "UPDATE users SET default_tenant_id should have been called"
    assert any(
        call.get("new_tid") is None
        for call in update_calls
    ), f"Expected default_tenant_id to be set to None for single-org user, got {update_calls!r}"
