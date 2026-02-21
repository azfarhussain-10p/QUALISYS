"""
QUALISYS — InvitationService
Story: 1-3-team-member-invitation
AC: AC1 — role guard: owner/admin NOT assignable via invite
AC: AC2 — create_invitation() with token generation, duplicate check, membership check
AC: AC4/AC5 — accept_invitation() creates TenantUser, marks invite accepted
AC: AC6 — revoke_invitation() and resend_invitation()
AC: AC7 — validate_token() with lazy expiry update
AC: AC9 — secrets.token_urlsafe(32), single-use, email match validation

Security constraints:
  - All DB queries via SQLAlchemy ORM (no raw SQL)
  - Token never logged; email masked in info logs
  - Tokens use secrets.token_urlsafe(32) — 256 bits of entropy
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.models.invitation import Invitation
from src.models.tenant import TenantUser
from src.models.user import User

# AC1: owner/admin role CANNOT be assigned via invite (security constraint)
_INVITEABLE_ROLES = frozenset({"pm-csm", "qa-manual", "qa-automation", "developer", "viewer"})
_INVITATION_EXPIRY_DAYS = 7


def _hash_token(raw_token: str) -> str:
    """
    SHA-256 hash a raw invitation token for safe DB storage.
    Tech spec §5.4: store token_hash, never the plaintext token.
    The plaintext token is sent to the user via email; the DB only holds the hash.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Domain exceptions — each maps to a specific HTTP status code in the router
# ---------------------------------------------------------------------------

class InvitationError(Exception):
    """Base for invitation domain errors."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DuplicatePendingInviteError(InvitationError):
    def __init__(self, email: str) -> None:
        super().__init__(
            "DUPLICATE_INVITE",
            f"A pending invitation already exists for this email address.",
        )


class AlreadyMemberError(InvitationError):
    def __init__(self) -> None:
        super().__init__(
            "ALREADY_MEMBER",
            "This email address is already a member of this organization.",
        )


class InvalidRoleError(InvitationError):
    def __init__(self, role: str) -> None:
        super().__init__(
            "INVALID_ROLE",
            f"Role '{role}' cannot be assigned via invitation. "
            "Allowed roles: pm-csm, qa-manual, qa-automation, developer, viewer.",
        )


class TokenNotFoundError(InvitationError):
    def __init__(self) -> None:
        # AC9: generic message — no information leakage about token state
        super().__init__(
            "INVITATION_NOT_FOUND",
            "Invitation not found or has already been used.",
        )


class TokenExpiredError(InvitationError):
    def __init__(self) -> None:
        super().__init__(
            "INVITATION_EXPIRED",
            "This invitation has expired. Please ask your administrator to resend the invitation.",
        )


class TokenRevokedError(InvitationError):
    def __init__(self) -> None:
        # AC9: use same generic message as expired (no leakage of reason)
        super().__init__(
            "INVITATION_REVOKED",
            "This invitation is no longer valid.",
        )


class EmailMismatchError(InvitationError):
    def __init__(self) -> None:
        # AC9: generic message — do not reveal which email the invite was for
        super().__init__(
            "EMAIL_MISMATCH",
            "This invitation is not valid for your account.",
        )


class InvitationNotRevocableError(InvitationError):
    def __init__(self) -> None:
        super().__init__(
            "INVITATION_NOT_REVOCABLE",
            "Only pending invitations can be revoked.",
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class InvitationService:
    """
    Domain service for invitation lifecycle management.

    All public methods accept an AsyncSession and operate via SQLAlchemy ORM.
    Callers are responsible for db.commit() after calling service methods
    (service uses db.flush() to get IDs without committing).
    """

    async def create_invitation(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        email: str,
        role: str,
        invited_by: uuid.UUID,
    ) -> tuple["Invitation", str]:
        """
        Create a single invitation record.

        Validates:
          - Role is inviteable (not owner/admin) — AC1
          - No existing pending invite for (tenant, email) — AC2 partial unique index
          - Target email is not already an active member — AC2

        Returns (Invitation, raw_token). The raw_token must be sent to the user
        via email — it is NOT stored in the DB (only the SHA-256 hash is stored).
        Caller is responsible for db.commit().

        Raises: InvalidRoleError, DuplicatePendingInviteError, AlreadyMemberError
        """
        normalized_email = email.lower().strip()

        # AC1: role guard
        if role not in _INVITEABLE_ROLES:
            raise InvalidRoleError(role)

        # AC2: existing pending invite check (mirrors the partial unique index)
        stmt = select(Invitation).where(
            Invitation.tenant_id == tenant_id,
            func.lower(Invitation.email) == normalized_email,
            Invitation.status == "pending",
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise DuplicatePendingInviteError(normalized_email)

        # AC2: already-member check
        user_stmt = select(User).where(func.lower(User.email) == normalized_email)
        user_result = await db.execute(user_stmt)
        existing_user = user_result.scalar_one_or_none()
        if existing_user is not None:
            membership_stmt = select(TenantUser).where(
                TenantUser.tenant_id == tenant_id,
                TenantUser.user_id == existing_user.id,
            )
            membership_result = await db.execute(membership_stmt)
            if membership_result.scalar_one_or_none() is not None:
                raise AlreadyMemberError()

        # AC9: cryptographically random token — 32 bytes → 43 URL-safe base64 chars
        # M1: store SHA-256 hash only; return raw token to caller for email delivery
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)

        invitation = Invitation(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email=normalized_email,
            role=role,
            invited_by=invited_by,
            token=token_hash,  # DB stores hash, not plaintext
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=_INVITATION_EXPIRY_DAYS),
        )
        db.add(invitation)
        await db.flush()

        logger.info(
            "Invitation created",
            tenant_id=str(tenant_id),
            role=role,
            invited_by=str(invited_by),
            invitation_id=str(invitation.id),
        )
        return invitation, raw_token

    async def validate_token(
        self,
        *,
        db: AsyncSession,
        token: str,
    ) -> Invitation:
        """
        Validate an invitation token and return the Invitation if valid.

        Implements lazy expiry: sets status='expired' if pending and past expires_at.
        AC7: server-side expiry validation.
        AC9: generic errors (no information leakage about reason for invalidity).

        Raises: TokenNotFoundError, TokenExpiredError, TokenRevokedError
        """
        # M1: look up by SHA-256 hash — plaintext token is never stored
        token_hash = _hash_token(token)
        stmt = select(Invitation).where(Invitation.token == token_hash)
        result = await db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if invitation is None:
            raise TokenNotFoundError()

        # Lazy expiry update — AC7
        if invitation.status == "pending" and invitation.expires_at < datetime.now(timezone.utc):
            invitation.status = "expired"
            await db.flush()

        if invitation.status == "expired":
            raise TokenExpiredError()

        if invitation.status == "revoked":
            raise TokenRevokedError()

        if invitation.status != "pending":
            # 'accepted' or unexpected state — treat as not found
            raise TokenNotFoundError()

        return invitation

    async def get_invite_details(
        self,
        *,
        db: AsyncSession,
        token: str,
    ) -> dict:
        """
        Return public info about an invitation for the accept page (AC4/AC5).
        Includes org_name, role, email, user_exists flag.
        Raises: TokenNotFoundError, TokenExpiredError, TokenRevokedError
        """
        from sqlalchemy import select as sa_select
        from src.models.tenant import Tenant

        invitation = await self.validate_token(db=db, token=token)

        # Load tenant name
        tenant_stmt = sa_select(Tenant).where(Tenant.id == invitation.tenant_id)
        tenant_result = await db.execute(tenant_stmt)
        tenant = tenant_result.scalar_one_or_none()
        org_name = tenant.name if tenant else "Unknown Organization"

        # Check if user already exists in public.users
        user_stmt = sa_select(User).where(func.lower(User.email) == invitation.email.lower())
        user_result = await db.execute(user_stmt)
        existing_user = user_result.scalar_one_or_none()

        return {
            "org_name": org_name,
            "role": invitation.role,
            "email": invitation.email,
            "user_exists": existing_user is not None,
            "expires_at": invitation.expires_at,
        }

    async def accept_invitation(
        self,
        *,
        db: AsyncSession,
        token: str,
        user_id: uuid.UUID,
        accepting_email: str,
    ) -> TenantUser:
        """
        Accept an invitation. Creates public.tenants_users record, marks invite accepted.
        AC4/AC5: supports both existing and new users.
        AC9: validates token + email match; single-use (sets status=accepted).

        Raises: TokenNotFoundError, TokenExpiredError, TokenRevokedError, EmailMismatchError
        """
        invitation = await self.validate_token(db=db, token=token)

        # AC9: email match — prevent accepting invite sent to a different address
        if invitation.email.lower() != accepting_email.lower().strip():
            raise EmailMismatchError()

        # Create tenants_users record (AC4, AC5)
        membership = TenantUser(
            tenant_id=invitation.tenant_id,
            user_id=user_id,
            role=invitation.role,
        )
        db.add(membership)

        # AC9: mark single-use (invalidate token)
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(
            "Invitation accepted",
            invitation_id=str(invitation.id),
            user_id=str(user_id),
            tenant_id=str(invitation.tenant_id),
            role=invitation.role,
        )
        return membership

    async def revoke_invitation(
        self,
        *,
        db: AsyncSession,
        invite_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Invitation:
        """
        Revoke a pending invitation. Sets status='revoked', invalidating the token. AC6.
        Raises: TokenNotFoundError, InvitationNotRevocableError
        """
        stmt = select(Invitation).where(
            Invitation.id == invite_id,
            Invitation.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if invitation is None:
            raise TokenNotFoundError()

        if invitation.status != "pending":
            raise InvitationNotRevocableError()

        invitation.status = "revoked"
        await db.flush()

        logger.info(
            "Invitation revoked",
            invitation_id=str(invite_id),
            tenant_id=str(tenant_id),
        )
        return invitation

    async def resend_invitation(
        self,
        *,
        db: AsyncSession,
        invite_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> tuple["Invitation", str]:
        """
        Resend an expired (or pending) invitation.
        Generates a new token and resets the 7-day expiry. AC6.
        M1: stores SHA-256 hash; returns (Invitation, raw_token) for email delivery.
        Raises: TokenNotFoundError
        """
        stmt = select(Invitation).where(
            Invitation.id == invite_id,
            Invitation.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        invitation = result.scalar_one_or_none()

        if invitation is None or invitation.status not in ("pending", "expired"):
            raise TokenNotFoundError()

        # M1: new raw token → hash → store hash; raw token returned for email URL
        raw_token = secrets.token_urlsafe(32)
        invitation.token = _hash_token(raw_token)
        invitation.status = "pending"
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=_INVITATION_EXPIRY_DAYS)
        await db.flush()

        logger.info(
            "Invitation resent",
            invitation_id=str(invite_id),
            tenant_id=str(tenant_id),
        )
        return invitation, raw_token

    async def list_invitations(
        self,
        *,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        status_filter: Optional[str] = None,
    ) -> list[Invitation]:
        """
        List invitations for a tenant. Optionally filter by status. AC6.
        Defaults to returning pending and expired (not accepted/revoked).
        """
        stmt = select(Invitation).where(Invitation.tenant_id == tenant_id)
        if status_filter:
            stmt = stmt.where(Invitation.status == status_filter)
        else:
            stmt = stmt.where(Invitation.status.in_(["pending", "expired"]))
        stmt = stmt.order_by(Invitation.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())
