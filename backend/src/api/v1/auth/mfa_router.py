"""
QUALISYS MFA API Router
Story: 1-7-two-factor-authentication-totp
ACs: AC1–AC10

Endpoints:
  POST /api/v1/auth/mfa/setup                    — generate TOTP secret + QR URI (AC2)
  POST /api/v1/auth/mfa/setup/confirm            — confirm with 6-digit code (AC3)
  POST /api/v1/auth/mfa/verify                   — complete login with TOTP code (AC5)
  POST /api/v1/auth/mfa/backup                   — complete login with backup code (AC6)
  POST /api/v1/auth/mfa/disable                  — disable 2FA (AC7)
  POST /api/v1/auth/mfa/backup-codes/regenerate  — regenerate backup codes (AC8)
  GET  /api/v1/auth/mfa/status                   — current MFA state (AC1)

Security constraints:
  - MFA management endpoints (setup, confirm, disable, regenerate, status) require JWT auth
  - MFA login endpoints (verify, backup) use mfa_token (not JWT) — user not yet authenticated
  - mfa_token is short-lived (5 min), stored as SHA-256 hash in Redis
  - TOTP secrets never stored in plaintext — AES-256-GCM encrypted at rest (AC9)
  - Backup codes stored as bcrypt hashes (AC9)
  - Rate limiting: 5 attempts/mfa_token before invalidation (AC9)
  - MFA lockout: 10 failures/user/hr → 1-hr lockout (AC9)
  - All MFA events logged to audit trail (AC10)
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.router import (
    _correlation_id,
    _get_user_orgs,
    _session_info_from_request,
    _set_auth_cookies,
)
from src.api.v1.auth.schemas import (
    LoginResponse,
    MFABackupRequest,
    MFADisableRequest,
    MFARegenerateCodesRequest,
    MFARegenerateCodesResponse,
    MFASetupConfirmRequest,
    MFASetupConfirmResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
    MessageResponse,
    TenantOrgInfo,
    UserResponse,
)
from src.cache import get_redis_client
from src.config import get_settings
from src.db import get_db
from src.logger import logger
from src.middleware.rbac import get_current_user
from src.models.user import User
from src.services.auth.auth_service import verify_password
from src.services import backup_code_service
from src.services.totp_service import (
    decrypt_secret,
    encrypt_secret,
    generate_qr_uri,
    generate_secret,
    verify_totp_code,
)
from src.services.token_service import token_service

settings = get_settings()

mfa_router = APIRouter(prefix="/api/v1/auth/mfa", tags=["mfa"])


def _mfa_token_hash(raw_token: str) -> str:
    """SHA-256 hash of mfa_token for Redis lookup."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


async def _get_mfa_payload(
    redis,
    raw_mfa_token: str,
) -> dict:
    """
    Load and validate mfa_token from Redis.
    Raises HTTPException(401) if token not found or expired.
    """
    token_hash = _mfa_token_hash(raw_mfa_token)
    raw = await redis.get(f"mfa:{token_hash}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {
                "code": "MFA_TOKEN_INVALID",
                "message": "MFA session expired. Please log in again.",
            }},
        )
    return json.loads(raw), token_hash


async def _check_mfa_rate_limit(redis, token_hash: str, user_id: uuid.UUID) -> None:
    """
    Enforce per-mfa_token attempt limit (5) and per-user hourly failure limit (10).
    Raises HTTPException(429) or (423) if limits exceeded.
    AC9: 5 failed TOTP/backup attempts per mfa_token → token invalidated.
    AC9: 10 failed MFA per user per hour → 1-hour lockout.
    """
    attempts_key = f"mfa_attempts:{token_hash[:16]}"
    count_raw = await redis.get(attempts_key)
    count = int(count_raw) if count_raw else 0

    if count >= settings.mfa_max_attempts_per_token:
        # Invalidate the mfa_token (delete from Redis)
        await redis.delete(f"mfa:{token_hash}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {
                "code": "MFA_ATTEMPTS_EXCEEDED",
                "message": "Too many failed MFA attempts. Please log in again.",
            }},
        )

    # Check user-level lockout
    lockout_key = f"mfa_lockout:{user_id}"
    if await redis.exists(lockout_key):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error": {
                "code": "MFA_LOCKED",
                "message": "MFA is temporarily locked due to too many failed attempts. Try again in 1 hour.",
            }},
        )


async def _record_mfa_failure(redis, token_hash: str, user_id: uuid.UUID, db: AsyncSession) -> None:
    """
    Increment attempt counter + user failure counter.
    Sets 1-hour lockout if user failure counter reaches threshold.
    """
    # Per-token attempt counter
    attempts_key = f"mfa_attempts:{token_hash[:16]}"
    pipe = redis.pipeline()
    pipe.incr(attempts_key)
    pipe.expire(attempts_key, settings.mfa_token_ttl_seconds)
    await pipe.execute()

    # Per-user failure counter (for lockout — AC9)
    failures_key = f"mfa_failures:{user_id}"
    pipe2 = redis.pipeline()
    pipe2.incr(failures_key)
    pipe2.expire(failures_key, settings.mfa_lockout_seconds)
    results = await pipe2.execute()
    new_count = results[0]

    if new_count >= settings.mfa_max_failures_per_hour:
        # Trigger 1-hour lockout
        await redis.setex(f"mfa_lockout:{user_id}", settings.mfa_lockout_seconds, "1")
        # Update DB mfa_lockout_until for persistence across Redis restarts
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.mfa_lockout_until = datetime.now(timezone.utc).replace(
                second=0, microsecond=0
            )
            await db.commit()
        logger.warning(
            "MFA lockout triggered",
            user_id=str(user_id),
            failures=new_count,
        )


async def _complete_mfa_login(
    db: AsyncSession,
    response: Response,
    user: User,
    session_info: dict,
    remember_me: bool,
) -> LoginResponse:
    """
    Issue JWT + refresh token cookies after successful MFA verification.
    Shared by both /mfa/verify and /mfa/backup.
    """
    memberships = await _get_user_orgs(db, user.id)
    orgs = [
        TenantOrgInfo(id=t.id, name=t.name, slug=t.slug, role=tu.role)
        for tu, t in memberships
    ]

    if len(orgs) == 1:
        active_tenant_id = orgs[0].id
        active_tenant_slug = orgs[0].slug
        active_role = orgs[0].role
    else:
        active_tenant_id = None
        active_tenant_slug = None
        active_role = None

    access_token = token_service.create_access_token(
        user_id=user.id,
        email=user.email,
        tenant_id=active_tenant_id,
        role=active_role,
        tenant_slug=active_tenant_slug,
    )
    refresh_token = await token_service.create_refresh_token(
        user_id=user.id,
        tenant_id=active_tenant_id,
        session_info=session_info,
        remember_me=remember_me,
    )

    _set_auth_cookies(response, access_token, refresh_token, remember_me=remember_me)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        orgs=orgs,
        has_multiple_orgs=len(orgs) > 1,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/setup — AC2: generate secret + QR URI
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/setup",
    response_model=MFASetupResponse,
    responses={
        400: {"description": "MFA already enabled"},
    },
)
async def mfa_setup(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> MFASetupResponse:
    """
    Initiate 2FA setup: generate TOTP secret + QR URI (AC2).

    Stores secret temporarily in Redis (10-min TTL) — NOT persisted to DB until
    user confirms with a valid TOTP code (AC3: prevents partial setup).

    Returns QR URI for authenticator app and plaintext secret for manual entry.
    """
    correlation_id = _correlation_id(request)

    if current_user.totp_enabled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {
                "code": "MFA_ALREADY_ENABLED",
                "message": "Two-factor authentication is already enabled.",
            }},
        )

    # Generate new TOTP secret (160-bit base32 — RFC 6238)
    secret = generate_secret()
    qr_uri = generate_qr_uri(secret, current_user.email)

    # Store temp in Redis with 10-min TTL (AC constraint C7)
    redis = get_redis_client()
    setup_data = json.dumps({"secret": secret})
    await redis.setex(
        f"mfa_setup:{current_user.id}",
        settings.mfa_setup_ttl_seconds,
        setup_data,
    )

    # setup_token is just the user_id — used to correlate with the confirm request
    # (authentication is still enforced via JWT on /setup/confirm)
    setup_token = str(current_user.id)

    logger.info(
        "MFA setup initiated",
        user_id=str(current_user.id),
        correlation_id=correlation_id,
    )

    return MFASetupResponse(
        qr_uri=qr_uri,
        secret=secret,
        setup_token=setup_token,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/setup/confirm — AC3: validate TOTP + store secret
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/setup/confirm",
    response_model=MFASetupConfirmResponse,
    responses={
        400: {"description": "Invalid TOTP code or setup expired"},
    },
)
async def mfa_setup_confirm(
    payload: MFASetupConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFASetupConfirmResponse:
    """
    Confirm 2FA setup with a valid TOTP code (AC3).

    Steps:
      1. Load temp secret from Redis (validates setup hasn't expired)
      2. Verify TOTP code against temp secret (±1 window)
      3. Encrypt secret with AES-256-GCM
      4. Store encrypted secret in public.users
      5. Generate 10 backup codes
      6. Delete temp Redis key
      7. Return backup codes (shown once only — AC4)
    """
    correlation_id = _correlation_id(request)
    redis = get_redis_client()

    # Step 1: Load temp secret
    raw = await redis.get(f"mfa_setup:{current_user.id}")
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {
                "code": "SETUP_EXPIRED",
                "message": "Setup session expired. Please start 2FA setup again.",
            }},
        )
    setup_data = json.loads(raw)
    temp_secret = setup_data["secret"]

    # Rate limit: track failed confirm attempts (5 max before deleting setup)
    confirm_attempts_key = f"mfa_setup_attempts:{current_user.id}"
    attempt_count_raw = await redis.get(confirm_attempts_key)
    attempt_count = int(attempt_count_raw) if attempt_count_raw else 0

    if attempt_count >= settings.mfa_max_attempts_per_token:
        # Invalidate setup — user must restart
        await redis.delete(f"mfa_setup:{current_user.id}")
        await redis.delete(confirm_attempts_key)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {
                "code": "SETUP_ATTEMPTS_EXCEEDED",
                "message": "Too many failed attempts. Please restart 2FA setup.",
            }},
        )

    # Step 2: Verify TOTP code
    if not verify_totp_code(temp_secret, payload.totp_code):
        # Increment attempt counter
        pipe = redis.pipeline()
        pipe.incr(confirm_attempts_key)
        pipe.expire(confirm_attempts_key, settings.mfa_setup_ttl_seconds)
        await pipe.execute()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {
                "code": "INVALID_TOTP_CODE",
                "message": "Invalid code. Please try again.",
            }},
        )

    # Step 3: Encrypt secret
    encrypted = encrypt_secret(temp_secret)

    # Step 4: Persist to DB
    current_user.totp_secret_encrypted = encrypted
    current_user.totp_enabled_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)

    # Step 5: Generate backup codes
    backup_codes = await backup_code_service.generate_codes(db, current_user.id)
    await db.commit()

    # Step 6: Clean up Redis
    pipe = redis.pipeline()
    pipe.delete(f"mfa_setup:{current_user.id}")
    pipe.delete(confirm_attempts_key)
    await pipe.execute()

    # AC10: Audit
    logger.info(
        "2FA enabled",
        user_id=str(current_user.id),
        ip=request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        ),
        user_agent=request.headers.get("User-Agent"),
        correlation_id=correlation_id,
    )

    return MFASetupConfirmResponse(backup_codes=backup_codes)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/verify — AC5: complete login with TOTP code
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/verify",
    response_model=LoginResponse,
    responses={
        401: {"description": "Invalid or expired mfa_token"},
        400: {"description": "Invalid TOTP code"},
        423: {"description": "MFA locked"},
        429: {"description": "Too many attempts"},
    },
)
async def mfa_verify(
    payload: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Complete login with TOTP code after mfa_required response (AC5).

    Steps:
      1. Validate mfa_token from Redis
      2. Check rate limits + lockout (AC9)
      3. Load user from DB
      4. Decrypt TOTP secret, verify code (±1 window)
      5. On success: delete mfa_token, issue JWT + refresh cookies
      6. On failure: record failure, check lockout threshold
    """
    correlation_id = _correlation_id(request)
    redis = get_redis_client()

    # Step 1: Validate mfa_token
    mfa_data, token_hash = await _get_mfa_payload(redis, payload.mfa_token)
    user_id = uuid.UUID(mfa_data["user_id"])
    remember_me = mfa_data.get("remember_me", False)
    session_info = mfa_data.get("session_info", {})

    # Step 2: Rate limits
    await _check_mfa_rate_limit(redis, token_hash, user_id)

    # Step 3: Load user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.totp_enabled_at is None or user.totp_secret_encrypted is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MFA_NOT_CONFIGURED", "message": "MFA is not configured for this account."}},
        )

    # Step 4: Verify TOTP
    try:
        plain_secret = decrypt_secret(user.totp_secret_encrypted)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "MFA_SECRET_ERROR", "message": "MFA configuration error. Contact support."}},
        )

    if not verify_totp_code(plain_secret, payload.totp_code):
        await _record_mfa_failure(redis, token_hash, user_id, db)
        logger.info(
            "TOTP verification failed",
            user_id=str(user_id),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_TOTP_CODE", "message": "Invalid code. Please try again."}},
        )

    # Step 5: Success — consume mfa_token and issue JWT
    await redis.delete(f"mfa:{token_hash}")

    logger.info(
        "TOTP verified — login complete",
        user_id=str(user_id),
        correlation_id=correlation_id,
    )

    return await _complete_mfa_login(db, response, user, session_info, remember_me)


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/backup — AC6: complete login with backup code
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/backup",
    response_model=LoginResponse,
    responses={
        401: {"description": "Invalid or expired mfa_token"},
        400: {"description": "Invalid backup code"},
        423: {"description": "MFA locked"},
        429: {"description": "Too many attempts"},
    },
)
async def mfa_backup(
    payload: MFABackupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Complete login with backup code after mfa_required response (AC6).
    Marks the backup code as used (single-use enforcement).
    """
    correlation_id = _correlation_id(request)
    redis = get_redis_client()

    # Validate mfa_token
    mfa_data, token_hash = await _get_mfa_payload(redis, payload.mfa_token)
    user_id = uuid.UUID(mfa_data["user_id"])
    remember_me = mfa_data.get("remember_me", False)
    session_info = mfa_data.get("session_info", {})

    # Rate limits
    await _check_mfa_rate_limit(redis, token_hash, user_id)

    # Load user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.totp_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MFA_NOT_CONFIGURED", "message": "MFA is not configured for this account."}},
        )

    # Verify backup code
    valid = await backup_code_service.verify_code(db, user_id, payload.backup_code)
    if not valid:
        await _record_mfa_failure(redis, token_hash, user_id, db)
        logger.info(
            "Backup code verification failed",
            user_id=str(user_id),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_BACKUP_CODE", "message": "Invalid backup code. Please try again."}},
        )

    await db.commit()

    # Success — consume mfa_token
    await redis.delete(f"mfa:{token_hash}")

    # AC6: Warn if fewer than 3 backup codes remain (returned in response header)
    remaining = await backup_code_service.get_remaining_count(db, user_id)

    logger.info(
        "Backup code used — login complete",
        user_id=str(user_id),
        remaining_codes=remaining,
        correlation_id=correlation_id,
    )

    login_response = await _complete_mfa_login(db, response, user, session_info, remember_me)

    # Signal low backup codes via custom header (frontend can detect this)
    if remaining < 3:
        response.headers["X-Backup-Codes-Low"] = str(remaining)

    return login_response


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/disable — AC7: disable 2FA
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/disable",
    response_model=MessageResponse,
    responses={
        400: {"description": "MFA not enabled"},
        403: {"description": "Invalid password"},
    },
)
async def mfa_disable(
    payload: MFADisableRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """
    Disable 2FA — requires current password confirmation (AC7, C10).

    Clears totp_secret_encrypted, nulls totp_enabled_at,
    deletes all backup codes. Existing sessions remain valid.
    """
    correlation_id = _correlation_id(request)

    if current_user.totp_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MFA_NOT_ENABLED", "message": "Two-factor authentication is not enabled."}},
        )

    # Verify current password (AC7 + C10: prevents CSRF-style attacks)
    if not current_user.password_hash or not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "INVALID_PASSWORD", "message": "Incorrect password."}},
        )

    # Clear TOTP data
    current_user.totp_secret_encrypted = None
    current_user.totp_enabled_at = None
    current_user.mfa_lockout_until = None
    await db.commit()

    # Delete all backup codes
    from sqlalchemy import delete as sa_delete
    from src.models.user_backup_code import UserBackupCode
    await db.execute(
        sa_delete(UserBackupCode).where(UserBackupCode.user_id == current_user.id)
    )
    await db.commit()

    # Clear any Redis lockout/failure keys
    redis = get_redis_client()
    pipe = redis.pipeline()
    pipe.delete(f"mfa_lockout:{current_user.id}")
    pipe.delete(f"mfa_failures:{current_user.id}")
    await pipe.execute()

    # AC10: Audit
    logger.info(
        "2FA disabled",
        user_id=str(current_user.id),
        ip=request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        ),
        user_agent=request.headers.get("User-Agent"),
        correlation_id=correlation_id,
    )

    return MessageResponse(message="Two-factor authentication has been disabled.")


# ---------------------------------------------------------------------------
# POST /api/v1/auth/mfa/backup-codes/regenerate — AC8: regenerate backup codes
# ---------------------------------------------------------------------------

@mfa_router.post(
    "/backup-codes/regenerate",
    response_model=MFARegenerateCodesResponse,
    responses={
        400: {"description": "MFA not enabled"},
        403: {"description": "Invalid password"},
    },
)
async def mfa_regenerate_backup_codes(
    payload: MFARegenerateCodesRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFARegenerateCodesResponse:
    """
    Regenerate backup codes — deletes all existing (used + unused), generates 10 new (AC8).
    Requires current password confirmation (C10).
    """
    correlation_id = _correlation_id(request)

    if current_user.totp_enabled_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "MFA_NOT_ENABLED", "message": "Two-factor authentication is not enabled."}},
        )

    # Verify current password
    if not current_user.password_hash or not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "INVALID_PASSWORD", "message": "Incorrect password."}},
        )

    new_codes = await backup_code_service.regenerate_codes(db, current_user.id)
    await db.commit()

    # AC10: Audit
    logger.info(
        "Backup codes regenerated",
        user_id=str(current_user.id),
        ip=request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        ),
        user_agent=request.headers.get("User-Agent"),
        correlation_id=correlation_id,
    )

    return MFARegenerateCodesResponse(backup_codes=new_codes)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/mfa/status — AC1: current MFA state
# ---------------------------------------------------------------------------

@mfa_router.get(
    "/status",
    response_model=MFAStatusResponse,
)
async def mfa_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MFAStatusResponse:
    """
    Return current MFA status for the authenticated user (AC1).

    Returns:
      - enabled: bool
      - enabled_at: datetime or null
      - backup_codes_remaining: int (0 if MFA not enabled)
    """
    remaining = 0
    if current_user.totp_enabled_at is not None:
        remaining = await backup_code_service.get_remaining_count(db, current_user.id)

    return MFAStatusResponse(
        enabled=current_user.totp_enabled_at is not None,
        enabled_at=current_user.totp_enabled_at,
        backup_codes_remaining=remaining,
    )
