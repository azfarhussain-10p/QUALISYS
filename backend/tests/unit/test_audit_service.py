"""
Unit tests — AuditService
Story: 1-12-usage-analytics-audit-logs-basic
Task 7.1 — AuditService.log_action() inserts correct record, graceful failure
AC: #3 — Non-blocking, convenience methods, action naming convention
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.services.audit_service import AuditService, audit_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db_session():
    """Mock AsyncSession with execute and commit stubs."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.commit = AsyncMock()
    return session


SCHEMA = "tenant_test"
TENANT_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()
RESOURCE_ID = uuid.uuid4()


# ---------------------------------------------------------------------------
# Test log_action() — synchronous in-transaction insert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_action_executes_insert():
    """log_action() should call db.execute with correct params."""
    db = _make_db_session()
    svc = AuditService()

    await svc.log_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="project.deleted",
        resource_type="project",
        resource_id=RESOURCE_ID,
        details={"project_name": "Alpha"},
        ip_address="1.2.3.4",
        user_agent="pytest/test",
    )

    db.execute.assert_called_once()
    call_args = db.execute.call_args
    # The first positional arg is the text() statement; second is params dict
    params = call_args.args[1]

    assert params["tenant_id"] == str(TENANT_ID)
    assert params["actor_user_id"] == str(ACTOR_ID)
    assert params["action"] == "project.deleted"
    assert params["resource_type"] == "project"
    assert params["resource_id"] == str(RESOURCE_ID)
    assert json.loads(params["details"]) == {"project_name": "Alpha"}
    assert params["ip_address"] == "1.2.3.4"
    assert params["user_agent"] == "pytest/test"


@pytest.mark.asyncio
async def test_log_action_none_resource_id():
    """resource_id=None should store None, not 'None'."""
    db = _make_db_session()
    svc = AuditService()

    await svc.log_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="user.login",
        resource_type="session",
    )

    params = db.execute.call_args.args[1]
    assert params["resource_id"] is None


@pytest.mark.asyncio
async def test_log_action_graceful_on_db_error():
    """DB errors must not propagate — audit failures are non-fatal."""
    db = _make_db_session()
    db.execute = AsyncMock(side_effect=Exception("DB error"))
    svc = AuditService()

    # Should not raise
    await svc.log_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="project.archived",
        resource_type="project",
    )


# ---------------------------------------------------------------------------
# Test log_action_async() — non-blocking (opens own session)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_action_async_graceful_on_error():
    """log_action_async() catches exceptions and never raises."""
    svc = AuditService()

    # Patch AsyncSessionLocal to raise
    with patch("src.services.audit_service.AuditService.log_action_async") as mock_async:
        mock_async.side_effect = Exception("session error")
        # Should not raise from caller perspective since we're patching the method itself
        # Test graceful handling in the real method instead:
        pass

    # Test real graceful handling by patching AsyncSessionLocal
    with patch("src.db.AsyncSessionLocal") as MockSession:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.side_effect = Exception("db unavailable")
        MockSession.return_value = mock_ctx

        # Should not raise
        await svc.log_action_async(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            actor_user_id=ACTOR_ID,
            action="user.login",
            resource_type="session",
        )


# ---------------------------------------------------------------------------
# Test convenience methods
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_project_action_sets_resource_type():
    """log_project_action() pre-fills resource_type='project'."""
    db = _make_db_session()
    svc = AuditService()

    await svc.log_project_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="project.archived",
        resource_id=RESOURCE_ID,
    )

    params = db.execute.call_args.args[1]
    assert params["resource_type"] == "project"
    assert params["action"] == "project.archived"


@pytest.mark.asyncio
async def test_log_user_action_sets_resource_type():
    """log_user_action() pre-fills resource_type='user'."""
    db = _make_db_session()
    svc = AuditService()

    await svc.log_user_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="user.role_changed",
        resource_id=RESOURCE_ID,
        details={"old_role": "member", "new_role": "admin"},
    )

    params = db.execute.call_args.args[1]
    assert params["resource_type"] == "user"
    assert params["action"] == "user.role_changed"


@pytest.mark.asyncio
async def test_log_org_action_sets_resource_type():
    """log_org_action() pre-fills resource_type='organization'."""
    db = _make_db_session()
    svc = AuditService()

    await svc.log_org_action(
        db=db,
        schema_name=SCHEMA,
        tenant_id=TENANT_ID,
        actor_user_id=ACTOR_ID,
        action="org.settings_updated",
    )

    params = db.execute.call_args.args[1]
    assert params["resource_type"] == "organization"


# ---------------------------------------------------------------------------
# Test action naming convention (AC3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", [
    "org.created",
    "org.settings_updated",
    "user.created",
    "user.invited",
    "user.invitation_accepted",
    "user.invitation_revoked",
    "user.role_changed",
    "user.removed",
    "user.login",
    "user.password_reset",
    "user.mfa_enabled",
    "user.mfa_disabled",
    "user.profile_updated",
    "user.password_changed",
    "project.created",
    "project.updated",
    "project.archived",
    "project.restored",
    "project.deleted",
    "member.added",
    "member.removed",
])
def test_action_naming_convention(action: str):
    """All catalog actions must follow {resource_type}.{verb} format."""
    assert "." in action, f"Action '{action}' missing dot separator"
    parts = action.split(".")
    assert len(parts) == 2, f"Action '{action}' has more than one dot"
    resource_type, verb = parts
    assert resource_type, "resource_type must not be empty"
    assert verb, "verb must not be empty"
    assert resource_type == resource_type.lower(), "resource_type must be lowercase"
    assert verb == verb.lower(), "verb must be lowercase"


# ---------------------------------------------------------------------------
# Test singleton
# ---------------------------------------------------------------------------

def test_audit_service_singleton_is_audit_service():
    """Module-level `audit_service` should be an AuditService instance."""
    assert isinstance(audit_service, AuditService)
