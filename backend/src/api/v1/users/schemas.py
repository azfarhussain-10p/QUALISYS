"""
QUALISYS — Users API Schemas
Story: 1-8-profile-notification-preferences
AC: AC2 — UpdateProfileRequest (name validation)
AC: AC4 — timezone validation
AC: AC5 — ChangePasswordRequest
AC: AC6 — NotificationPreferencesRequest/Response
AC: AC8 — all request/response shapes
"""

from datetime import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from src.api.v1.auth.schemas import validate_password_policy


# ---------------------------------------------------------------------------
# User profile response (AC8)
# ---------------------------------------------------------------------------

class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    avatar_url: Optional[str]
    timezone: str
    auth_provider: str
    email_verified: bool
    created_at: str
    org_role: Optional[str] = None  # Current tenant role from JWT (owner/admin/etc.)

    @classmethod
    def from_user(cls, user, org_role: Optional[str] = None) -> "UserProfileResponse":
        return cls(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            timezone=user.timezone,
            auth_provider=user.auth_provider,
            email_verified=user.email_verified,
            created_at=user.created_at.isoformat() if user.created_at else "",
            org_role=org_role,
        )


# ---------------------------------------------------------------------------
# Profile update (AC2, AC4)
# ---------------------------------------------------------------------------

class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    timezone: Optional[str] = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) < 2 or len(stripped) > 100:
            raise ValueError("Name must be between 2 and 100 characters.")
        if stripped != v:
            raise ValueError("Name must not have leading or trailing whitespace.")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > 50:
            raise ValueError("Timezone string too long.")
        return v


# ---------------------------------------------------------------------------
# Avatar presigned URL (AC3)
# ---------------------------------------------------------------------------

class AvatarPresignedUrlRequest(BaseModel):
    filename: str
    content_type: str
    file_size: int

    @field_validator("content_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"image/png", "image/jpeg", "image/webp"}
        if v not in allowed:
            raise ValueError(f"content_type must be one of: {', '.join(sorted(allowed))}")
        return v

    @field_validator("file_size")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("file_size must be positive.")
        if v > 5 * 1024 * 1024:
            raise ValueError("file_size exceeds 5MB limit.")
        return v


class AvatarPresignedUrlResponse(BaseModel):
    upload_url: str
    key: str
    expires_in_seconds: int


class UpdateAvatarUrlRequest(BaseModel):
    """Called after successful S3 upload to register the new URL."""
    avatar_url: str


# ---------------------------------------------------------------------------
# Change password (AC5)
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_policy(cls, v: str) -> str:
        return validate_password_policy(v)

    @field_validator("confirm_new_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        new_pw = info.data.get("new_password")
        if new_pw is not None and v != new_pw:
            raise ValueError("Passwords do not match.")
        return v


# ---------------------------------------------------------------------------
# Notification preferences (AC6)
# ---------------------------------------------------------------------------

class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email_test_completions: bool
    email_test_failures: bool
    email_team_changes: bool
    email_security_alerts: bool
    email_frequency: str
    digest_time: str        # HH:MM format
    digest_day: str

    @classmethod
    def from_prefs(cls, prefs) -> "NotificationPreferencesResponse":
        dt = prefs.digest_time
        digest_time_str = (
            f"{dt.hour:02d}:{dt.minute:02d}"
            if hasattr(dt, "hour")
            else str(dt)
        )
        return cls(
            email_test_completions=prefs.email_test_completions,
            email_test_failures=prefs.email_test_failures,
            email_team_changes=prefs.email_team_changes,
            email_security_alerts=True,  # AC7: always true in response
            email_frequency=prefs.email_frequency,
            digest_time=digest_time_str,
            digest_day=prefs.digest_day,
        )


class UpdateNotificationPreferencesRequest(BaseModel):
    email_test_completions: Optional[bool] = None
    email_test_failures: Optional[bool] = None
    email_team_changes: Optional[bool] = None
    email_security_alerts: Optional[bool] = None  # AC7: silently ignored if false
    email_frequency: Optional[str] = None
    digest_time: Optional[str] = None  # "HH:MM"
    digest_day: Optional[str] = None
