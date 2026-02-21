"""
Unit Tests — UserManagementService
Story: 1-4-user-management-remove-change-roles (Task 7.1)
AC: AC2, AC3, AC5, AC6
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.user_management.user_management_service import (
    ALLOWED_ROLES,
    ADMIN_ROLES,
    InvalidRoleError,
    LastAdminError,
    MemberAlreadyRemovedError,
    MemberNotFoundError,
    SelfActionError,
    UserManagementService,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant_user(role="viewer", is_active=True, user_id=None, tenant_id=None):
    """Return a MagicMock simulating a TenantUser row."""
    tu = MagicMock()
    tu.role = role
    tu.is_active = is_active
    tu.user_id = user_id or uuid.uuid4()
    tu.tenant_id = tenant_id or uuid.uuid4()
    tu.joined_at = datetime.now(timezone.utc)
    tu.removed_at = None
    tu.removed_by = None
    return tu


def _mock_db_result(obj):
    result = MagicMock()
    result.scalar_one_or_none.return_value = obj
    result.scalar_one.return_value = obj
    return result


# ---------------------------------------------------------------------------
# change_role (AC2)
# ---------------------------------------------------------------------------

class TestChangeRole:
    async def test_invalid_role_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        with pytest.raises(InvalidRoleError):
            await svc.change_role(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=uuid.uuid4(),
                new_role="superuser",
            )

    async def test_self_action_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        uid = uuid.uuid4()
        with pytest.raises(SelfActionError):
            await svc.change_role(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uid,
                target_user_id=uid,
                new_role="viewer",
            )

    async def test_member_not_found_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=_mock_db_result(None))
        with pytest.raises(MemberNotFoundError):
            await svc.change_role(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=uuid.uuid4(),
                new_role="viewer",
            )

    async def test_last_admin_guard_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="owner", is_active=True, user_id=target_id)

        # First execute: load membership; second: count remaining admins
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0  # zero admins remain excluding target

        db.execute = AsyncMock(
            side_effect=[
                _mock_db_result(membership),
                count_result,
            ]
        )

        with pytest.raises(LastAdminError):
            await svc.change_role(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=target_id,
                new_role="viewer",
            )

    async def test_valid_role_change_updates_membership(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="viewer", is_active=True, user_id=target_id)

        db.execute = AsyncMock(return_value=_mock_db_result(membership))

        result = await svc.change_role(
            db=db,
            tenant_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            target_user_id=target_id,
            new_role="developer",
        )
        assert result.role == "developer"

    async def test_all_allowed_roles_accepted(self):
        svc = UserManagementService()
        for role in ALLOWED_ROLES:
            db = AsyncMock(spec=AsyncSession)
            target_id = uuid.uuid4()
            membership = _make_tenant_user(role="pm-csm", is_active=True, user_id=target_id)
            count_result = MagicMock()
            count_result.scalar_one.return_value = 1  # at least one other admin

            db.execute = AsyncMock(
                side_effect=[
                    _mock_db_result(membership),
                    count_result,
                ]
                if role not in ADMIN_ROLES or membership.role not in ADMIN_ROLES
                else [_mock_db_result(membership)]
            )
            # Should not raise InvalidRoleError for any allowed role
            try:
                await svc.change_role(
                    db=db,
                    tenant_id=uuid.uuid4(),
                    actor_id=uuid.uuid4(),
                    target_user_id=target_id,
                    new_role=role,
                )
            except (MemberNotFoundError, LastAdminError, SelfActionError):
                pass  # business logic errors are fine — role validation passed


# ---------------------------------------------------------------------------
# remove_member (AC3)
# ---------------------------------------------------------------------------

class TestRemoveMember:
    async def test_self_removal_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        uid = uuid.uuid4()
        with pytest.raises(SelfActionError):
            await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uid,
                target_user_id=uid,
            )

    async def test_member_not_found_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        db.execute = AsyncMock(return_value=_mock_db_result(None))
        with pytest.raises(MemberNotFoundError):
            await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=uuid.uuid4(),
            )

    async def test_already_removed_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="viewer", is_active=False, user_id=target_id)
        db.execute = AsyncMock(return_value=_mock_db_result(membership))
        with pytest.raises(MemberAlreadyRemovedError):
            await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=target_id,
            )

    async def test_last_admin_removal_raises(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="owner", is_active=True, user_id=target_id)
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0  # no other admins

        db.execute = AsyncMock(
            side_effect=[_mock_db_result(membership), count_result]
        )

        with pytest.raises(LastAdminError):
            await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                target_user_id=target_id,
            )

    async def test_valid_removal_soft_deletes(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        actor_id = uuid.uuid4()
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="viewer", is_active=True, user_id=target_id)
        db.execute = AsyncMock(return_value=_mock_db_result(membership))

        with patch.object(svc, "_invalidate_sessions", new_callable=AsyncMock):
            result = await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=actor_id,
                target_user_id=target_id,
            )

        assert result.is_active is False
        assert result.removed_at is not None
        assert result.removed_by == actor_id

    async def test_removal_calls_session_invalidation(self):
        """AC5: _invalidate_sessions called on removal."""
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        actor_id = uuid.uuid4()
        target_id = uuid.uuid4()
        membership = _make_tenant_user(role="viewer", is_active=True, user_id=target_id)
        db.execute = AsyncMock(return_value=_mock_db_result(membership))

        with patch.object(svc, "_invalidate_sessions", new_callable=AsyncMock) as mock_inv:
            await svc.remove_member(
                db=db,
                tenant_id=uuid.uuid4(),
                actor_id=actor_id,
                target_user_id=target_id,
            )
            mock_inv.assert_called_once()


# ---------------------------------------------------------------------------
# check_last_admin (AC6)
# ---------------------------------------------------------------------------

class TestCheckLastAdmin:
    async def test_returns_true_when_zero_other_admins(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one.return_value = 0
        db.execute = AsyncMock(return_value=result)

        is_last = await svc.check_last_admin(
            db=db,
            tenant_id=uuid.uuid4(),
            exclude_user_id=uuid.uuid4(),
        )
        assert is_last is True

    async def test_returns_false_when_other_admins_exist(self):
        svc = UserManagementService()
        db = AsyncMock(spec=AsyncSession)
        result = MagicMock()
        result.scalar_one.return_value = 2
        db.execute = AsyncMock(return_value=result)

        is_last = await svc.check_last_admin(
            db=db,
            tenant_id=uuid.uuid4(),
            exclude_user_id=uuid.uuid4(),
        )
        assert is_last is False
