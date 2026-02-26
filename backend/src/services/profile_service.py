"""
QUALISYS — Profile Service
Story: 1-8-profile-notification-preferences
AC: AC2 — update full_name (validation: 2-100 chars, no leading/trailing whitespace)
AC: AC3 — avatar upload presigned URL (S3, users/{id}/avatar/{uuid}.{ext}), remove avatar
AC: AC4 — timezone update (IANA validation via zoneinfo)
AC: AC5 — change_password (verify current, validate policy, update hash, invalidate sessions)
AC: AC9 — audit log for all profile changes (name, avatar, timezone, password)
"""

import re
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.schemas import validate_password_policy
from src.config import get_settings
from src.logger import logger
from src.models.user import User
from src.services.auth.auth_service import hash_password, verify_password
from src.services.token_service import token_service

settings = get_settings()

# Allowed avatar content types (AC: PNG/JPG/WebP only — no executables)
_ALLOWED_AVATAR_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
# Max avatar file size: 5MB
_MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024

# IANA timezone validation pattern (rough check; zoneinfo is the definitive source)
_IANA_TZ_RE = re.compile(r"^[A-Za-z_]+(/[A-Za-z0-9_+\-]+)*$")


def _validate_timezone(tz: str) -> bool:
    """
    Validate IANA timezone string using Python's zoneinfo module (Python 3.9+).
    Falls back to regex check if zoneinfo is unavailable.
    """
    if not tz or len(tz) > 50:
        return False
    if tz == "UTC":
        return True
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(tz)
            return True
        except (ZoneInfoNotFoundError, KeyError):
            return False
    except ImportError:
        # Fallback: rough pattern check
        return bool(_IANA_TZ_RE.match(tz))


# ---------------------------------------------------------------------------
# Profile — name + timezone update (AC2, AC4)
# ---------------------------------------------------------------------------

async def update_profile(
    db: AsyncSession,
    user: User,
    full_name: Optional[str] = None,
    timezone: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """
    Update user's full_name and/or timezone.

    Args:
        db:        Database session
        user:      User object to update
        full_name: New display name (2-100 chars, no leading/trailing whitespace)
        timezone:  IANA timezone string (e.g. "America/New_York", "UTC")
        ip:        For audit log
        user_agent: For audit log

    Returns:
        Updated User object

    Raises:
        ValueError: If validation fails
    """
    changes = {}

    if full_name is not None:
        stripped = full_name.strip()
        if len(stripped) < 2 or len(stripped) > 100:
            raise ValueError("Name must be between 2 and 100 characters.")
        if stripped != full_name:
            raise ValueError("Name must not have leading or trailing whitespace.")
        if user.full_name != stripped:
            changes["full_name"] = (user.full_name, stripped)
            user.full_name = stripped

    if timezone is not None:
        if not _validate_timezone(timezone):
            raise ValueError(f"Invalid timezone: '{timezone}'. Must be a valid IANA timezone.")
        if user.timezone != timezone:
            changes["timezone"] = (user.timezone, timezone)
            user.timezone = timezone

    if changes:
        await db.flush()
        logger.info(
            "Profile updated",
            user_id=str(user.id),
            changes=list(changes.keys()),
            ip=ip,
            user_agent=user_agent,
        )

    return user


# ---------------------------------------------------------------------------
# Avatar upload — presigned S3 URL (AC3)
# ---------------------------------------------------------------------------

def get_avatar_presigned_url(
    user_id: uuid_mod.UUID,
    filename: str,
    content_type: str,
    file_size: int,
) -> dict:
    """
    Generate a presigned S3 PUT URL for direct browser-to-S3 avatar upload.

    Key path: users/{user_id}/avatar/{uuid}.{ext}
    URL expires in settings.avatar_presigned_url_expires seconds (5 min).

    Returns:
        dict with {upload_url, key, expires_in_seconds}

    Raises:
        ValueError: If content type or file size is invalid
        RuntimeError: If S3 is not configured
    """
    if content_type not in _ALLOWED_AVATAR_TYPES:
        raise ValueError(
            f"Unsupported file type '{content_type}'. Allowed: PNG, JPEG, WebP."
        )
    if file_size > _MAX_AVATAR_SIZE_BYTES:
        raise ValueError(
            f"File size {file_size} bytes exceeds 5MB limit."
        )
    if not settings.s3_bucket_name:
        raise RuntimeError("S3_NOT_CONFIGURED")

    ext = _ALLOWED_AVATAR_TYPES[content_type]
    file_key = f"{settings.s3_avatar_key_prefix}/{user_id}/avatar/{uuid_mod.uuid4()}.{ext}"

    try:
        s3 = boto3.client(
            "s3",
            region_name=settings.s3_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket_name,
                "Key": file_key,
                "ContentType": content_type,
                "ContentLength": file_size,
            },
            ExpiresIn=settings.avatar_presigned_url_expires,
        )
        return {
            "upload_url": upload_url,
            "key": file_key,
            "expires_in_seconds": settings.avatar_presigned_url_expires,
        }
    except ClientError as exc:
        logger.error("S3 presigned URL generation failed", error=str(exc), user_id=str(user_id))
        raise RuntimeError("S3_ERROR") from exc


async def _generate_thumbnail(user_id: uuid_mod.UUID, avatar_url: str) -> None:
    """
    Background task: download avatar, resize to 128×128, re-upload thumbnail to S3.
    Skips silently if Pillow is not installed or download fails.
    """
    if not settings.s3_bucket_name:
        return
    try:
        import io as _io

        import httpx
        try:
            from PIL import Image
        except ImportError:
            logger.warning("Pillow not installed — avatar thumbnail skipped")
            return

        # Determine extension from URL
        url_path = avatar_url.split("?")[0]  # strip query params
        ext = url_path.rsplit(".", 1)[-1].lower() if "." in url_path else "jpg"
        if ext not in ("png", "jpg", "jpeg", "webp"):
            ext = "jpg"
        content_type_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
        content_type = content_type_map.get(ext, "image/jpeg")

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(avatar_url)
            resp.raise_for_status()
            img_data = resp.content

        img = Image.open(_io.BytesIO(img_data))
        img = img.convert("RGBA" if ext == "png" else "RGB")
        img.thumbnail((128, 128), Image.LANCZOS)

        buf = _io.BytesIO()
        fmt = "PNG" if ext == "png" else ("WEBP" if ext == "webp" else "JPEG")
        img.save(buf, format=fmt)
        buf.seek(0)

        thumb_key = f"{settings.s3_avatar_key_prefix}/{user_id}/avatar/thumb.{ext}"
        s3 = boto3.client(
            "s3",
            region_name=settings.s3_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=thumb_key,
            Body=buf.read(),
            ContentType=content_type,
        )
        logger.info("Avatar thumbnail generated", user_id=str(user_id), key=thumb_key)
    except Exception as exc:
        logger.warning("Avatar thumbnail generation failed (non-fatal)", user_id=str(user_id), error=str(exc))


async def update_avatar_url(
    db: AsyncSession,
    user: User,
    avatar_url: str,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """
    Store the avatar URL after successful S3 upload. Optionally deletes old avatar.
    Called by the client after completing the presigned PUT.
    Spawns a background task to generate a 128×128 thumbnail.
    """
    import asyncio
    old_url = user.avatar_url
    user.avatar_url = avatar_url
    await db.flush()

    # Attempt to delete old avatar from S3 (best-effort, don't fail if S3 unavailable)
    if old_url and settings.s3_bucket_name:
        _delete_s3_avatar(old_url)

    # Generate thumbnail in background (non-blocking, non-fatal)
    asyncio.create_task(_generate_thumbnail(user.id, avatar_url))

    logger.info("Avatar uploaded", user_id=str(user.id), ip=ip, user_agent=user_agent)
    return user


async def remove_avatar(
    db: AsyncSession,
    user: User,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> User:
    """
    Remove user avatar: deletes from S3 (best-effort) and clears avatar_url.
    User falls back to initials display.
    """
    if user.avatar_url and settings.s3_bucket_name:
        _delete_s3_avatar(user.avatar_url)

    user.avatar_url = None
    await db.flush()
    logger.info("Avatar removed", user_id=str(user.id), ip=ip, user_agent=user_agent)
    return user


def _delete_s3_avatar(avatar_url: str) -> None:
    """Best-effort S3 object deletion. Errors are logged but not raised."""
    if not settings.s3_bucket_name:
        return
    # avatar_url may be a full URL or just the key
    key = avatar_url
    if "amazonaws.com/" in avatar_url:
        # Extract key from URL: https://bucket.s3.region.amazonaws.com/{key}
        key = avatar_url.split("amazonaws.com/", 1)[-1]
    try:
        s3 = boto3.client(
            "s3",
            region_name=settings.s3_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        s3.delete_object(Bucket=settings.s3_bucket_name, Key=key)
    except Exception as exc:
        logger.warning("Failed to delete old avatar from S3", key=key, error=str(exc))


# ---------------------------------------------------------------------------
# Change password (AC5)
# ---------------------------------------------------------------------------

async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Change password from settings (AC5).

    Validates:
      - current_password is correct (bcrypt)
      - new_password meets policy (min 12 chars, complexity)
      - new_password != current_password
      - user has a password (local auth only; raises ValueError for OAuth-only)

    On success:
      - Updates password_hash in DB
      - Invalidates ALL existing sessions (AuthService.logout_all pattern)
      - Logs audit event (no password values — AC: 8.6)

    Raises:
        ValueError: On validation failure (current wrong, policy violation, same password)
    """
    if not user.password_hash:
        raise ValueError("Password change is not available for accounts using social login.")

    if not verify_password(current_password, user.password_hash):
        raise ValueError("Current password is incorrect.")

    # Policy validation (reuse from Story 1.1)
    validate_password_policy(new_password)

    # New password must differ from current
    if verify_password(new_password, user.password_hash):
        raise ValueError("New password must be different from your current password.")

    # Update hash
    user.password_hash = hash_password(new_password)
    await db.flush()

    # Invalidate all sessions (AC5: "redirect to login with new password")
    await token_service.invalidate_all_user_tokens(user.id)

    # AC9: Audit (no password values logged)
    logger.info(
        "Password changed from settings",
        user_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )
