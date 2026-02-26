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


# ---------------------------------------------------------------------------
# Password Reset — Story 1.6 AC2, AC5, AC6
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    """POST /api/v1/auth/forgot-password — AC2: no email enumeration."""
    email: EmailStr

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()


class ValidateResetTokenResponse(BaseModel):
    """GET /api/v1/auth/reset-password?token=... — AC5: token validation."""
    valid: bool
    # Partially masked email for UX confirmation (u***@example.com)
    email: Optional[str] = None
    error: Optional[str] = None  # "token_invalid" | "token_expired" | "token_used"


class ResetPasswordRequest(BaseModel):
    """POST /api/v1/auth/reset-password — AC6: consume token, update password."""
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_policy(cls, v: str) -> str:
        return validate_password_policy(v)


# ---------------------------------------------------------------------------
# Login response — extended for MFA challenge (Story 1.7 AC5)
# ---------------------------------------------------------------------------

# LoginResponse already defined above — we extend it with optional MFA fields.
# When mfa_required=True: user/orgs/has_multiple_orgs are None (not yet authenticated)
# When mfa_required=False (default): normal login response
LoginResponse.model_rebuild()  # noqa: no-op, trigger model rebuild if subclassed


class MFAChallengeResponse(BaseModel):
    """
    200 response when MFA-enabled user submits correct password.
    JWT cookies are NOT issued yet — MFA verification required first (AC5).
    """
    mfa_required: bool = True
    mfa_token: str  # Short-lived opaque token (5 min) proving password was validated


# ---------------------------------------------------------------------------
# MFA management — Story 1.7
# ---------------------------------------------------------------------------

class MFASetupResponse(BaseModel):
    """POST /api/v1/auth/mfa/setup — AC2: QR code + manual secret."""
    qr_uri: str      # otpauth://totp/QUALISYS:{email}?secret=...
    secret: str      # Plaintext base32 secret for manual entry
    setup_token: str  # Opaque token linking this setup session (10-min TTL)


class MFASetupConfirmRequest(BaseModel):
    """POST /api/v1/auth/mfa/setup/confirm — AC3: validate TOTP code."""
    setup_token: str
    totp_code: str

    @field_validator("totp_code")
    @classmethod
    def code_format(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("TOTP code must be exactly 6 digits.")
        return v


class MFASetupConfirmResponse(BaseModel):
    """200 response with backup codes after successful 2FA setup (AC4)."""
    backup_codes: list[str]
    message: str = "Two-factor authentication enabled. Save your backup codes."


class MFAVerifyRequest(BaseModel):
    """POST /api/v1/auth/mfa/verify — AC5: complete login with TOTP code."""
    mfa_token: str
    totp_code: str

    @field_validator("totp_code")
    @classmethod
    def code_format(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("TOTP code must be exactly 6 digits.")
        return v


class MFABackupRequest(BaseModel):
    """POST /api/v1/auth/mfa/backup — AC6: complete login with backup code."""
    mfa_token: str
    backup_code: str

    @field_validator("backup_code")
    @classmethod
    def code_format(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 8:
            raise ValueError("Backup code must be exactly 8 characters.")
        return v


class MFADisableRequest(BaseModel):
    """POST /api/v1/auth/mfa/disable — AC7: requires current password."""
    password: str


class MFARegenerateCodesRequest(BaseModel):
    """POST /api/v1/auth/mfa/backup-codes/regenerate — AC8: requires current password."""
    password: str


class MFARegenerateCodesResponse(BaseModel):
    """200 response with new backup codes (AC8)."""
    backup_codes: list[str]
    message: str = "Backup codes regenerated. Save these new codes — the old ones are now invalid."


class MFAStatusResponse(BaseModel):
    """GET /api/v1/auth/mfa/status — AC1: current MFA state."""
    enabled: bool
    enabled_at: Optional[datetime] = None
    backup_codes_remaining: int
