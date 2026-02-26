"""
Unit Tests — ProjectMemberService
Story: 1-10-project-team-assignment (Task 7.1)
AC: #3 — check_access (Owner/Admin bypass, member check, non-member denied)
AC: #7 — AlreadyMemberError, UserNotInOrgError

Tests use AsyncMock to isolate service from DB — no real DB required.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.project_member_service import (
    AlreadyMemberError,
    MemberNotFoundError,
    ProjectMemberError,
    ProjectMemberService,
    UserNotInOrgError,
    project_member_service,
)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_db_mock():
    """Return an AsyncSession mock with configurable execute results."""
    db = AsyncMock(spec=AsyncSession)
    return db


def _mock_result(row=None):
    """Mock an execute() result with fetchone()."""
    result = MagicMock()
    result.fetchone.return_value = row
    result.mappings.return_value.fetchone.return_value = row
    return result


def _mock_result_all(rows=None):
    result = MagicMock()
    result.mappings.return_value.fetchall.return_value = rows or []
    result.fetchall.return_value = rows or []
    return result


# ---------------------------------------------------------------------------
# check_access — AC#3
# ---------------------------------------------------------------------------

class TestCheckAccess:
    """AC#3: Owner/Admin implicit access + project_members lookup."""

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_owner_always_has_access(self, mock_ctx):
        """AC#3: Owner role → True without hitting project_members table."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()

        svc = ProjectMemberService()
        result = await svc.check_access(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_org_role="owner",
            tenant_id=uuid.uuid4(),
            db=db,
        )

        assert result is True
        # Should NOT have queried project_members for Owner
        db.execute.assert_not_called()

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_admin_always_has_access(self, mock_ctx):
        """AC#3: Admin role → True without hitting project_members table."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()

        svc = ProjectMemberService()
        result = await svc.check_access(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_org_role="admin",
            tenant_id=uuid.uuid4(),
            db=db,
        )

        assert result is True
        db.execute.assert_not_called()

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_explicit_member_has_access(self, mock_ctx):
        """AC#3: User in project_members → True."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        # Simulate row found in project_members
        db.execute.return_value = _mock_result(row=(1,))

        svc = ProjectMemberService()
        result = await svc.check_access(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_org_role="developer",
            tenant_id=uuid.uuid4(),
            db=db,
        )

        assert result is True

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_non_member_denied(self, mock_ctx):
        """AC#3: User NOT in project_members and not Owner/Admin → False."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        # Simulate no row found
        db.execute.return_value = _mock_result(row=None)

        svc = ProjectMemberService()
        result = await svc.check_access(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_org_role="viewer",
            tenant_id=uuid.uuid4(),
            db=db,
        )

        assert result is False

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_pm_csm_not_in_project_denied(self, mock_ctx):
        """AC#3: PM/CSM role with no project membership → False."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        db.execute.return_value = _mock_result(row=None)

        svc = ProjectMemberService()
        result = await svc.check_access(
            project_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_org_role="pm-csm",
            tenant_id=uuid.uuid4(),
            db=db,
        )

        assert result is False


# ---------------------------------------------------------------------------
# add_member — AC#2, AC#7
# ---------------------------------------------------------------------------

class TestAddMember:
    """AC#2: Validate org membership + no-duplicate. AC#7: errors on invalid states."""

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_user_not_in_org_raises(self, mock_ctx):
        """AC#7: UserNotInOrgError when user not in public.tenants_users."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        # First execute: org check returns None (user not in org)
        db.execute.return_value = _mock_result(row=None)

        svc = ProjectMemberService()
        with pytest.raises(UserNotInOrgError):
            await svc.add_member(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                added_by=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                db=db,
            )

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_already_member_raises(self, mock_ctx):
        """AC#7: AlreadyMemberError when user already in project_members."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        # First call: org check → found; Second call: dup check → found
        db.execute.side_effect = [
            _mock_result(row=(1,)),  # org check → user in org
            _mock_result(row=(1,)),  # dup check → already member
        ]

        svc = ProjectMemberService()
        with pytest.raises(AlreadyMemberError):
            await svc.add_member(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                added_by=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                db=db,
            )


# ---------------------------------------------------------------------------
# remove_member — AC#4
# ---------------------------------------------------------------------------

class TestRemoveMember:
    """AC#4: Remove raises MemberNotFoundError if not in project_members."""

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_not_in_project_raises(self, mock_ctx):
        """AC#4: MemberNotFoundError when user not in project_members."""
        mock_ctx.get.return_value = "test-org"
        db = _make_db_mock()
        db.execute.return_value = _mock_result(row=None)

        svc = ProjectMemberService()
        with pytest.raises(MemberNotFoundError):
            await svc.remove_member(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                removed_by=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                db=db,
            )


# ---------------------------------------------------------------------------
# No tenant context
# ---------------------------------------------------------------------------

class TestNoTenantContext:
    """Service raises ProjectMemberError when no tenant context is set."""

    @patch("src.services.project_member_service.current_tenant_slug")
    async def test_no_context_raises(self, mock_ctx):
        mock_ctx.get.return_value = None
        db = _make_db_mock()

        svc = ProjectMemberService()
        with pytest.raises(ProjectMemberError, match="No tenant context"):
            await svc.check_access(
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                user_org_role="developer",
                tenant_id=uuid.uuid4(),
                db=db,
            )
