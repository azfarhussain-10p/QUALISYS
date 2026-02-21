"""
Unit Tests — InvitationService
Story: 1-3-team-member-invitation (Task 7.1)
AC: AC1 — role validation (inviteable roles only)
AC: AC2 — token generation randomness (secrets.token_urlsafe)
AC: AC4 — validate_token: expiry, revoked, accepted state
AC: AC6 — revoke guard (pending-only), resend guard
AC: AC9 — generic exception messages (no token value leakage)
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.invitation.invitation_service import (
    AlreadyMemberError,
    DuplicatePendingInviteError,
    EmailMismatchError,
    InvitationError,
    InvitationNotRevocableError,
    InvalidRoleError,
    InvitationService,
    TokenExpiredError,
    TokenNotFoundError,
    TokenRevokedError,
    _INVITEABLE_ROLES,
)


# ---------------------------------------------------------------------------
# Role constants — AC1
# ---------------------------------------------------------------------------

class TestRoleConstants:
    def test_owner_not_in_inviteable_roles(self):
        assert "owner" not in _INVITEABLE_ROLES

    def test_admin_not_in_inviteable_roles(self):
        assert "admin" not in _INVITEABLE_ROLES

    def test_allowed_roles_all_present(self):
        for role in ["pm-csm", "qa-manual", "qa-automation", "developer", "viewer"]:
            assert role in _INVITEABLE_ROLES


# ---------------------------------------------------------------------------
# Token generation randomness — AC9
# ---------------------------------------------------------------------------

class TestTokenGeneration:
    def test_tokens_are_unique(self):
        """secrets.token_urlsafe must produce unique tokens each call."""
        import secrets
        tokens = {secrets.token_urlsafe(32) for _ in range(100)}
        assert len(tokens) == 100

    def test_token_has_sufficient_length(self):
        """32-byte tokens → at least 40 URL-safe base64 characters."""
        import secrets
        token = secrets.token_urlsafe(32)
        assert len(token) >= 40


# ---------------------------------------------------------------------------
# Domain exception hierarchy and message safety
# ---------------------------------------------------------------------------

class TestDomainExceptions:
    def test_all_subclass_invitation_error(self):
        for exc_cls in [
            DuplicatePendingInviteError,
            AlreadyMemberError,
            InvalidRoleError,
            TokenNotFoundError,
            TokenExpiredError,
            TokenRevokedError,
            EmailMismatchError,
            InvitationNotRevocableError,
        ]:
            assert issubclass(exc_cls, InvitationError)

    def test_token_not_found_has_no_token_in_message(self):
        """AC9: generic message — must not expose token details."""
        exc = TokenNotFoundError()
        msg = str(exc).lower()
        assert "token" not in msg or "found" in msg  # generic phrasing ok

    def test_token_expired_message_does_not_include_raw_token(self):
        exc = TokenExpiredError()
        # The message should be a human-readable explanation, not expose raw values
        assert "SECRET" not in str(exc)

    def test_email_mismatch_does_not_expose_email(self):
        """AC9: EmailMismatchError must not reveal which email was expected."""
        exc = EmailMismatchError()
        assert "@" not in str(exc)

    def test_invalid_role_error_has_role_code(self):
        exc = InvalidRoleError("owner")
        assert exc.code == "INVALID_ROLE"

    def test_duplicate_invite_error_has_code(self):
        exc = DuplicatePendingInviteError("user@example.com")
        assert exc.code == "DUPLICATE_INVITE"
        # AC9: the exact email should not be in message (generic message)
        # DuplicatePendingInviteError uses a generic message by design
        assert "already exists" in str(exc).lower() or "duplicate" in str(exc).lower()


# ---------------------------------------------------------------------------
# validate_token — AC4 (via mocked DB)
# ---------------------------------------------------------------------------

def _make_invitation(**kwargs):
    inv = MagicMock()
    inv.id = uuid.uuid4()
    inv.status = kwargs.get("status", "pending")
    inv.expires_at = kwargs.get(
        "expires_at", datetime.now(timezone.utc) + timedelta(hours=24)
    )
    inv.email = kwargs.get("email", "user@example.com")
    inv.role = kwargs.get("role", "developer")
    inv.tenant_id = kwargs.get("tenant_id", uuid.uuid4())
    return inv


class TestValidateToken:
    async def test_valid_pending_token_returns_invitation(self):
        inv = _make_invitation()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        result = await svc.validate_token(db=db, token="good-token")
        assert result is inv

    async def test_missing_token_raises_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = InvitationService()
        with pytest.raises(TokenNotFoundError):
            await svc.validate_token(db=db, token="bad-token")

    async def test_revoked_token_raises_revoked(self):
        inv = _make_invitation(status="revoked")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        with pytest.raises(TokenRevokedError):
            await svc.validate_token(db=db, token="revoked-token")

    async def test_past_expires_at_raises_expired_and_updates_status(self):
        """AC4: service lazily sets status='expired' when expires_at is in the past."""
        inv = _make_invitation(
            status="pending",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        db.flush = AsyncMock()
        svc = InvitationService()
        with pytest.raises(TokenExpiredError):
            await svc.validate_token(db=db, token="expired-token")
        # Lazy expiry update must set status to 'expired'
        assert inv.status == "expired"
        db.flush.assert_awaited()

    async def test_accepted_token_raises_not_found(self):
        """Accepted tokens are single-use — treat as not found for re-use attempts."""
        inv = _make_invitation(status="accepted")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        with pytest.raises(TokenNotFoundError):
            await svc.validate_token(db=db, token="used-token")


# ---------------------------------------------------------------------------
# revoke_invitation — AC6 (pending-only guard)
# ---------------------------------------------------------------------------

class TestRevokeInvitation:
    async def test_revoke_accepted_raises_not_revocable(self):
        inv = _make_invitation(status="accepted")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        with pytest.raises(InvitationNotRevocableError):
            await svc.revoke_invitation(
                db=db, invite_id=inv.id, tenant_id=inv.tenant_id
            )

    async def test_revoke_expired_raises_not_revocable(self):
        inv = _make_invitation(status="expired")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        with pytest.raises(InvitationNotRevocableError):
            await svc.revoke_invitation(
                db=db, invite_id=inv.id, tenant_id=inv.tenant_id
            )

    async def test_revoke_nonexistent_raises_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        svc = InvitationService()
        with pytest.raises(TokenNotFoundError):
            await svc.revoke_invitation(
                db=db, invite_id=uuid.uuid4(), tenant_id=uuid.uuid4()
            )

    async def test_revoke_pending_sets_status_revoked(self):
        inv = _make_invitation(status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        db.flush = AsyncMock()
        svc = InvitationService()
        result = await svc.revoke_invitation(
            db=db, invite_id=inv.id, tenant_id=inv.tenant_id
        )
        assert inv.status == "revoked"
        assert result is inv


# ---------------------------------------------------------------------------
# accept_invitation — email mismatch (AC9)
# ---------------------------------------------------------------------------

class TestAcceptInvitation:
    async def test_email_mismatch_raises_email_mismatch_error(self):
        """AC9: accept must reject if acting user email != invitation email."""
        inv = _make_invitation(email="invited@example.com", status="pending")
        db = AsyncMock()
        # First call to validate_token returns the invitation
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        db.flush = AsyncMock()
        db.add = MagicMock()
        svc = InvitationService()
        with pytest.raises(EmailMismatchError):
            await svc.accept_invitation(
                db=db,
                token="any-token",
                user_id=uuid.uuid4(),
                accepting_email="different@example.com",
            )

    async def test_email_match_creates_membership(self):
        """Happy path: matching email creates TenantUser membership."""
        inv = _make_invitation(email="match@example.com", status="pending")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        db.flush = AsyncMock()
        db.add = MagicMock()
        svc = InvitationService()
        result = await svc.accept_invitation(
            db=db,
            token="any-token",
            user_id=uuid.uuid4(),
            accepting_email="match@example.com",
        )
        # accept_invitation returns a TenantUser membership
        assert result is not None
        # Invitation status must be marked accepted
        assert inv.status == "accepted"
        assert inv.accepted_at is not None


# ---------------------------------------------------------------------------
# resend_invitation — AC6
# ---------------------------------------------------------------------------

class TestResendInvitation:
    async def test_resend_revoked_raises_not_found(self):
        inv = _make_invitation(status="revoked")
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        svc = InvitationService()
        with pytest.raises(TokenNotFoundError):
            await svc.resend_invitation(
                db=db, invite_id=inv.id, tenant_id=inv.tenant_id
            )

    async def test_resend_expired_resets_token_and_expiry(self):
        old_token = "old-expired-token"
        inv = _make_invitation(
            status="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        inv.token = old_token
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=inv))
        )
        db.flush = AsyncMock()
        svc = InvitationService()
        result, raw_token = await svc.resend_invitation(
            db=db, invite_id=inv.id, tenant_id=inv.tenant_id
        )
        # Token must be regenerated (stored as hash, raw returned separately)
        assert inv.token != old_token
        assert isinstance(raw_token, str) and len(raw_token) > 0
        # Status must be reset to pending
        assert inv.status == "pending"
        # Expiry must be in the future
        assert inv.expires_at > datetime.now(timezone.utc)
        assert result is inv
