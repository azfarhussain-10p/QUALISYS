"""
QUALISYS — Invitation API Schemas (Pydantic v2)
Story: 1-3-team-member-invitation
AC: AC1 — BulkInviteRequest validates email list (max 20) and role
AC: AC2 — InvitationResponse maps invitation record
AC: AC4/AC5 — AcceptInviteRequest handles existing and new user paths
AC: AC8 — HTTP 429 shape consistent with existing error schema
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Roles allowed via invitation (AC1: owner/admin NOT assignable via invite)
_INVITEABLE_ROLES = frozenset({"pm-csm", "qa-manual", "qa-automation", "developer", "viewer"})

# Password policy (AC5: reuse Story 1.1 rules)
_PASSWORD_MIN_LEN = 12
_PASSWORD_RE = re.compile(
    r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;':\",./<>?])"
)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class InviteItemRequest(BaseModel):
    """Single invitation item within a bulk invite request."""

    email: EmailStr = Field(..., description="RFC 5322 validated email address")
    role: str = Field(..., description="Role to assign: pm-csm, qa-manual, qa-automation, developer, viewer")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _INVITEABLE_ROLES:
            raise ValueError(
                f"Invalid role '{v}'. Allowed roles via invitation: "
                + ", ".join(sorted(_INVITEABLE_ROLES))
            )
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip() if isinstance(v, str) else v


class BulkInviteRequest(BaseModel):
    """
    POST /api/v1/orgs/{org_id}/invitations — AC1
    Supports 1–20 invitations per request.
    """

    invitations: list[InviteItemRequest] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of invitations (max 20 per batch)",
    )

    @model_validator(mode="after")
    def check_duplicate_emails(self) -> "BulkInviteRequest":
        """AC1: reject duplicate emails within the same batch (client-side equivalent)."""
        emails = [item.email for item in self.invitations]
        if len(emails) != len(set(emails)):
            raise ValueError("Duplicate email addresses in the same invitation batch are not allowed.")
        return self


class AcceptInviteRequest(BaseModel):
    """
    POST /api/v1/invitations/accept

    Supports two paths:
      - Existing user: provide only token (requires Bearer auth for identity)
      - New user: provide token + full_name + password (no Bearer needed)
    """

    token: str = Field(..., min_length=1, description="Invitation token from accept URL")
    # New user fields (optional — only required for new user path)
    full_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=255,
        description="Full name (required for new user registration)",
    )
    password: Optional[str] = Field(
        None,
        description="Password (required for new user registration, min 12 chars)",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if len(v) < _PASSWORD_MIN_LEN:
                raise ValueError(f"Password must be at least {_PASSWORD_MIN_LEN} characters.")
            if not _PASSWORD_RE.match(v):
                raise ValueError(
                    "Password must contain uppercase, lowercase, digit, and special character."
                )
        return v


# ---------------------------------------------------------------------------
# Response Schemas
# ---------------------------------------------------------------------------

class InvitationResponse(BaseModel):
    """Single invitation record for listing/creation responses — AC2, AC6."""

    id: uuid.UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InviteItemError(BaseModel):
    """Per-email error in a bulk invite response."""

    email: str
    reason: str


class BulkInviteResponse(BaseModel):
    """
    POST /api/v1/orgs/{org_id}/invitations response.
    Returns successfully created invitations + per-email errors (AC2).
    """

    data: list[InvitationResponse]
    errors: list[InviteItemError]


class AcceptInviteDetailsResponse(BaseModel):
    """
    GET /api/v1/invitations/accept?token=... response.
    Used by frontend to decide which accept path to render (AC4 vs AC5).
    """

    org_name: str
    role: str
    email: str
    user_exists: bool
    expires_at: datetime


class AcceptInviteResponse(BaseModel):
    """
    POST /api/v1/invitations/accept response.
    For new users: also includes JWT tokens. For existing users: just membership info.
    """

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: str
    # Tokens issued for new users only (AC5: email auto-verified via trusted invite)
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
