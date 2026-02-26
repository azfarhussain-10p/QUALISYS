"""
QUALISYS — Users API Router
Story: 1-8-profile-notification-preferences
ACs: AC2–AC9

Endpoints:
  GET    /api/v1/users/me                    — full profile (AC8)
  PATCH  /api/v1/users/me/profile            — update name + timezone (AC2, AC4)
  POST   /api/v1/users/me/avatar             — presigned S3 upload URL (AC3)
  PATCH  /api/v1/users/me/avatar             — register uploaded avatar URL (AC3)
  DELETE /api/v1/users/me/avatar             — remove avatar (AC3)
  GET    /api/v1/users/me/notifications      — get notification preferences (AC6)
  PUT    /api/v1/users/me/notifications      — save notification preferences (AC6, AC7)
  POST   /api/v1/users/me/change-password    — change password (AC5)

Security:
  - All endpoints require JWT auth (get_current_user)
  - change-password: 3/user/hour rate limit (AC5, AC: 8.7)
  - profile updates: 30/user/hour rate limit (AC: 4.8)
  - avatar: PNG/JPG/WebP only, max 5MB (AC: 8.1, 8.2)
"""

import uuid
from datetime import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.schemas import MessageResponse
from src.api.v1.users.schemas import (
    AvatarPresignedUrlRequest,
    AvatarPresignedUrlResponse,
    ChangePasswordRequest,
    NotificationPreferencesResponse,
    UpdateAvatarUrlRequest,
    UpdateNotificationPreferencesRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from src.cache import get_redis_client
from src.config import get_settings
from src.db import get_db
from src.logger import logger
from src.middleware.rbac import get_current_user, require_project_role
from src.models.user import User
from src.services import notification_preferences_service, profile_service

settings = get_settings()
router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _request_meta(request: Request) -> tuple[str, str]:
    """Extract IP and User-Agent from request headers."""
    ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
        or ""
    )
    ua = request.headers.get("User-Agent", "")
    return ip, ua


# Atomic Lua script for rate limiting (prevents permanent lockout on dropped connections)
_RATE_LIMIT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


async def _check_profile_update_rate_limit(user_id: uuid.UUID, request: Request) -> None:
    """30 profile updates per user per hour (AC: 4.8)."""
    redis = get_redis_client()
    key = f"rate:profile_update:{user_id}"
    count, ttl = await redis.eval(_RATE_LIMIT_SCRIPT, 1, key, 3600)
    if count > 30:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Profile update limit reached. Retry after {retry_after} seconds.",
            }},
            headers={"Retry-After": str(retry_after)},
        )


async def _check_pw_rate_limit(redis, user_id: uuid.UUID) -> None:
    """
    Enforce change-password rate limit: 3 attempts per user per hour (AC5, AC: 8.7).
    Raises HTTPException(429) if exceeded.
    """
    key = f"pw_change:{user_id}"
    count_raw = await redis.get(key)
    count = int(count_raw) if count_raw else 0
    if count >= settings.change_password_rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many password change attempts. Please wait and try again.",
            }},
        )
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, settings.change_password_rate_window_seconds)
    await pipe.execute()


# ---------------------------------------------------------------------------
# GET /api/v1/users/me — AC8
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfileResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    auth: tuple = require_project_role(),  # any active org member — gets role from JWT
) -> UserProfileResponse:
    """Return full profile for the authenticated user, including current org role."""
    _, membership = auth
    return UserProfileResponse.from_user(current_user, org_role=membership.role)


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/me/profile — AC2, AC4
# ---------------------------------------------------------------------------

@router.patch("/me/profile", response_model=UserProfileResponse)
async def update_profile(
    payload: UpdateProfileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Update full_name and/or timezone (AC2, AC4).
    Validates name length and IANA timezone format.
    Rate-limited: 30/user/hour (AC: 4.8).
    """
    await _check_profile_update_rate_limit(current_user.id, request)
    ip, ua = _request_meta(request)
    try:
        user = await profile_service.update_profile(
            db=db,
            user=current_user,
            full_name=payload.full_name,
            timezone=payload.timezone,
            ip=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        )
    await db.commit()
    await db.refresh(user)
    return UserProfileResponse.from_user(user)


# ---------------------------------------------------------------------------
# POST /api/v1/users/me/avatar — get presigned upload URL (AC3)
# ---------------------------------------------------------------------------

@router.post("/me/avatar", response_model=AvatarPresignedUrlResponse)
async def get_avatar_upload_url(
    payload: AvatarPresignedUrlRequest,
    current_user: User = Depends(get_current_user),
) -> AvatarPresignedUrlResponse:
    """
    Generate a presigned S3 PUT URL for avatar upload (AC3).
    Client uploads directly to S3, then calls PATCH /me/avatar with the resulting key.
    """
    try:
        result = profile_service.get_avatar_presigned_url(
            user_id=current_user.id,
            filename=payload.filename,
            content_type=payload.content_type,
            file_size=payload.file_size,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_AVATAR", "message": str(exc)}},
        )
    except RuntimeError as exc:
        if "S3_NOT_CONFIGURED" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail={"error": {"code": "S3_NOT_CONFIGURED", "message": "Object storage is not configured."}},
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "S3_ERROR", "message": "Failed to generate upload URL."}},
        )
    return AvatarPresignedUrlResponse(**result)


# ---------------------------------------------------------------------------
# PATCH /api/v1/users/me/avatar — register uploaded URL (AC3)
# ---------------------------------------------------------------------------

@router.patch("/me/avatar", response_model=UserProfileResponse)
async def set_avatar_url(
    payload: UpdateAvatarUrlRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Register the uploaded avatar URL after successful S3 upload (AC3).
    Optionally deletes the previous avatar from S3.
    """
    ip, ua = _request_meta(request)
    user = await profile_service.update_avatar_url(
        db=db,
        user=current_user,
        avatar_url=payload.avatar_url,
        ip=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(user)
    return UserProfileResponse.from_user(user)


# ---------------------------------------------------------------------------
# DELETE /api/v1/users/me/avatar — remove avatar (AC3)
# ---------------------------------------------------------------------------

@router.delete("/me/avatar", response_model=UserProfileResponse)
async def remove_avatar(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    """
    Remove user avatar, falling back to initials display (AC3).
    Deletes from S3 (best-effort) and clears avatar_url.
    """
    ip, ua = _request_meta(request)
    user = await profile_service.remove_avatar(
        db=db,
        user=current_user,
        ip=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(user)
    return UserProfileResponse.from_user(user)


# ---------------------------------------------------------------------------
# GET /api/v1/users/me/notifications — AC6
# ---------------------------------------------------------------------------

@router.get("/me/notifications", response_model=NotificationPreferencesResponse)
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    """
    Return notification preferences. Creates defaults on first access (AC6).
    """
    prefs = await notification_preferences_service.get_preferences(db, current_user.id)
    return NotificationPreferencesResponse.from_prefs(prefs)


# ---------------------------------------------------------------------------
# PUT /api/v1/users/me/notifications — AC6, AC7
# ---------------------------------------------------------------------------

@router.put("/me/notifications", response_model=NotificationPreferencesResponse)
async def update_notifications(
    payload: UpdateNotificationPreferencesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationPreferencesResponse:
    """
    Save notification preferences (AC6).
    AC7: security_alerts=False is overridden to True (non-disableable).
    """
    ip, ua = _request_meta(request)

    # Parse digest_time string "HH:MM" if provided
    parsed_time: Optional[time] = None
    if payload.digest_time is not None:
        try:
            h, m = payload.digest_time.split(":")
            parsed_time = time(int(h), int(m))
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "VALIDATION_ERROR", "message": "digest_time must be in HH:MM format."}},
            )

    try:
        prefs = await notification_preferences_service.update_preferences(
            db=db,
            user_id=current_user.id,
            email_test_completions=payload.email_test_completions,
            email_test_failures=payload.email_test_failures,
            email_team_changes=payload.email_team_changes,
            email_security_alerts=payload.email_security_alerts,
            email_frequency=payload.email_frequency,
            digest_time=parsed_time,
            digest_day=payload.digest_day,
            ip=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}},
        )

    await db.commit()
    await db.refresh(prefs)
    return NotificationPreferencesResponse.from_prefs(prefs)


# ---------------------------------------------------------------------------
# POST /api/v1/users/me/change-password — AC5
# ---------------------------------------------------------------------------

@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Change password from settings (AC5).

    Requires current password. Invalidates all sessions on success.
    Rate-limited: 3 attempts per user per hour (AC: 4.8, 8.7).

    On success: client must redirect to /login (sessions invalidated).
    """
    ip, ua = _request_meta(request)
    redis = get_redis_client()

    # Rate limit check
    await _check_pw_rate_limit(redis, current_user.id)

    try:
        await profile_service.change_password(
            db=db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            ip=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "PASSWORD_CHANGE_ERROR", "message": str(exc)}},
        )

    await db.commit()

    # Clear cookies (sessions already invalidated in token_service)
    from src.api.v1.auth.router import _clear_auth_cookies
    _clear_auth_cookies(response)

    return MessageResponse(
        message="Password changed successfully. Please log in with your new password."
    )
