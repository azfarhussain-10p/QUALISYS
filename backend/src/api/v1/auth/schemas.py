"""
Auth API — Pydantic Request/Response Schemas
Story: 1-1-user-account-creation, 1-5-login-session-management
AC: AC1 — email RFC 5322 + password policy validation (1.1)
AC: AC4 — UserResponse EXCLUDES password_hash (1.1)
AC: AC7 — password_hash never in any response schema (1.1)
AC: AC8 — structured error response {error: {code, message}} (1.1)
AC: AC1 — LoginRequest/LoginResponse (1.5)
AC: AC6 — multi-org session SelectOrgRequest/SwitchOrgRequest (1.5)
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# ---------------------------------------------------------------------------
# Password policy constants — AC1
# Min 12 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special char
# ---------------------------------------------------------------------------
_PASSWORD_MIN_LENGTH = 12
_SPECIAL_CHARS = r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`\']'
_PASSWORD_REGEX = re.compile(
    r"^"
    r"(?=.*[A-Z])"          # at least 1 uppercase
    r"(?=.*[a-z])"          # at least 1 lowercase
    r"(?=.*\d)"             # at least 1 digit
    r"(?=.*[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\\/~`'])"  # at least 1 special char
    r".{12,}$"              # min 12 chars
)


def validate_password_policy(password: str) -> str:
    """Validate password meets complexity requirements. Raises ValueError on failure."""
    if len(password) < _PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {_PASSWORD_MIN_LENGTH} characters.")
    if not _PASSWORD_REGEX.match(password):
        raise ValueError(
            "Password must contain at least 1 uppercase letter, 1 lowercase letter, "
            "1 digit, and 1 special character."
        )
    return password


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """POST /api/v1/auth/register — AC1, AC4"""

    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        return validate_password_policy(v)

    @field_validator("full_name")
    @classmethod
    def full_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required.")
        if len(v) > 255:
            raise ValueError("Full name must be at most 255 characters.")
        return v

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class UserResponse(BaseModel):
    """Safe user representation — password_hash EXCLUDED (AC7)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    auth_provider: str
    avatar_url: Optional[str] = None
    created_at: datetime


class RegisterResponse(BaseModel):
    """201 response for POST /api/v1/auth/register"""

    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Email Verification — AC3
# ---------------------------------------------------------------------------

class VerifyEmailRequest(BaseModel):
    """POST /api/v1/auth/verify-email"""
    token: str


class ResendVerificationRequest(BaseModel):
    """POST /api/v1/auth/resend-verification"""
    email: EmailStr

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class MessageResponse(BaseModel):
    """Generic success message response"""
    success: bool = True
    message: str


# ---------------------------------------------------------------------------
# Error Response — AC8
# Structured JSON: {"error": {"code": str, "message": str}}
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Login — Story 1.5 AC1, AC6, AC8
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """POST /api/v1/auth/login"""
    email: EmailStr
    password: str
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class TenantOrgInfo(BaseModel):
    """Tenant summary returned on login (multi-org support)."""
    id: uuid.UUID
    name: str
    slug: str
    role: str


class LoginResponse(BaseModel):
    """200 response for POST /api/v1/auth/login. Tokens are in httpOnly cookies."""
    user: UserResponse
    orgs: list[TenantOrgInfo]
    has_multiple_orgs: bool


# ---------------------------------------------------------------------------
# Token refresh — Story 1.5 AC4
# ---------------------------------------------------------------------------

class RefreshResponse(BaseModel):
    """200 response for POST /api/v1/auth/refresh. New access token in cookie."""
    success: bool = True


# ---------------------------------------------------------------------------
# Session management — Story 1.5 AC5
# ---------------------------------------------------------------------------

class SessionInfo(BaseModel):
    """Single session record for GET /api/v1/auth/sessions."""
    session_id: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    created_at: str
    is_current: bool
    remember_me: bool = False
    tenant_id: Optional[uuid.UUID] = None


class SessionListResponse(BaseModel):
    """200 response for GET /api/v1/auth/sessions."""
    sessions: list[SessionInfo]


# ---------------------------------------------------------------------------
# Multi-org session — Story 1.5 AC6
# ---------------------------------------------------------------------------

class SelectOrgRequest(BaseModel):
    """POST /api/v1/auth/select-org — choose org after multi-org login."""
    tenant_id: uuid.UUID


class SwitchOrgRequest(BaseModel):
    """POST /api/v1/auth/switch-org — switch to a different org mid-session."""
    tenant_id: uuid.UUID
