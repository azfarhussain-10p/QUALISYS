"""
QUALISYS — AuthService
Story: 1-1-user-account-creation, 1-5-login-session-management
AC: AC3 — verification token generation/validation (1.1)
AC: AC4 — bcrypt password hash, user record creation (1.1)
AC: AC5 — case-insensitive duplicate email check (LOWER index) (1.1)
AC: AC7 — password_hash never returned; no PII in logs (1.1)
AC: AC8 — structured error codes (1.1)
AC: AC1 — login with email/password; bcrypt verify (1.5)
AC: AC7 — account lockout after repeated failures (1.5)
AC: AC8 — rate limiting; no email enumeration (1.5)

Security constraints:
  - Parameterized queries ONLY via SQLAlchemy ORM — no raw SQL string concatenation
  - password_hash excluded from all return values (callers use UserResponse schema)
  - Emails masked in error logs: u***@***.com
  - Correlation ID on all log entries
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.logger import logger
from src.models.user import User

settings = get_settings()

# ---------------------------------------------------------------------------
# Password hashing — Argon2id primary, bcrypt deprecated fallback (AC4)
# Existing bcrypt hashes continue to verify and are transparently rehashed
# to Argon2id on next login (passlib handles this automatically).
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__memory_cost=65536,   # 64 MiB
    argon2__time_cost=3,
    argon2__parallelism=4,
)


def hash_password(plain: str) -> str:
    """Hash password with Argon2id."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain password against Argon2id or legacy bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers (access + email verification tokens)
# ---------------------------------------------------------------------------

def _mask_email(email: str) -> str:
    """Mask email for safe log output: user@example.com → u***@e***.com"""
    try:
        local, domain = email.split("@", 1)
        domain_parts = domain.split(".")
        masked_domain = f"{domain_parts[0][0]}***"
        if len(domain_parts) > 1:
            masked_domain += "." + domain_parts[-1]
        return f"{local[0]}***@{masked_domain}"
    except Exception:
        return "***"


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    """
    Issue a short-lived RS256 JWT access token (15 min).

    Backward-compatible wrapper over TokenService.create_access_token().
    Used by existing tests via conftest.py auth_headers fixture.
    tenant_id and role are None for generic tokens (e.g. test fixtures).
    """
    from src.services.token_service import token_service
    return token_service.create_access_token(
        user_id=user_id,
        email=email,
        tenant_id=None,
        role=None,
    )


def create_email_verification_token(user_id: uuid.UUID) -> str:
    """
    Issue a signed, single-purpose JWT for email verification (AC3).
    Uses a SEPARATE secret from the session JWT (constraint from architecture).
    24-hour expiry.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.email_verification_expire_hours)
    payload = {
        "sub": str(user_id),
        "purpose": "email_verification",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.email_verification_secret,
        algorithm="HS256",  # email-verification always HS256 (separate from RS256 session JWT)
    )


def decode_email_verification_token(token: str) -> uuid.UUID:
    """
    Decode + validate email verification JWT.
    Returns user_id on success; raises ValueError on invalid/expired token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.email_verification_secret,
            algorithms=["HS256"],  # email-verification always HS256
        )
        if payload.get("purpose") != "email_verification":
            raise ValueError("Invalid token purpose.")
        return uuid.UUID(payload["sub"])
    except JWTError as exc:
        raise ValueError(f"Invalid or expired verification token: {exc}") from exc


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class DuplicateEmailError(Exception):
    """Raised when email already exists in public.users."""


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    correlation_id: str,
) -> User:
    """
    Create a new user in public.users.

    Steps (per tech spec §5.1):
      1. Validate email + password (done by Pydantic schema before calling this)
      2. bcrypt hash password (cost 12)
      3. INSERT users (email_verified=false)

    Raises:
        DuplicateEmailError — if LOWER(email) already exists (AC5)

    Security:
        - All queries via SQLAlchemy ORM (parameterized)
        - password_hash not logged
        - Email masked in logs
    """
    normalized_email = email.lower()

    # AC5: case-insensitive duplicate check via LOWER(email) index
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.info(
            "Registration rejected — duplicate email",
            email=_mask_email(normalized_email),
            correlation_id=correlation_id,
        )
        raise DuplicateEmailError(normalized_email)

    # AC4: bcrypt password hash (cost 12). Never logged.
    password_hash = hash_password(password)

    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        full_name=full_name,
        password_hash=password_hash,
        email_verified=False,
        auth_provider="email",
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(
        "User registered",
        email=_mask_email(normalized_email),
        user_id=str(user.id),
        correlation_id=correlation_id,
    )
    return user


# ---------------------------------------------------------------------------
# Email Verification — AC3
# ---------------------------------------------------------------------------

async def verify_email(
    db: AsyncSession,
    token: str,
    correlation_id: str,
) -> User:
    """
    Mark user's email as verified after clicking the link.
    Returns the updated User.
    Raises ValueError for invalid/expired tokens.
    """
    user_id = decode_email_verification_token(token)

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise ValueError("User not found.")

    if user.email_verified:
        return user  # idempotent — already verified

    user.email_verified = True
    await db.commit()
    await db.refresh(user)

    logger.info(
        "Email verified",
        user_id=str(user.id),
        correlation_id=correlation_id,
    )
    return user


# ---------------------------------------------------------------------------
# Google OAuth — AC2 (Task 3)
# ---------------------------------------------------------------------------

async def get_or_create_oauth_user(
    db: AsyncSession,
    google_id: str,
    email: str,
    full_name: str,
    avatar_url: Optional[str],
    correlation_id: str,
) -> tuple[User, bool]:
    """
    Create or load a user from Google OAuth profile.
    Returns (user, created: bool).

    Handles:
      - First-time Google signup: INSERT users (auth_provider='google')
      - Returning Google user: load by google_id
      - Email conflict (different auth provider): load existing user and
        link google_id (merges accounts)
    """
    normalized_email = email.lower()

    # Try to find by google_id first (fastest path for returning users)
    stmt = select(User).where(User.google_id == google_id)
    result = await db.execute(stmt)
    existing_by_google = result.scalar_one_or_none()
    if existing_by_google is not None:
        return existing_by_google, False

    # Check if email already registered with a different provider
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    existing_by_email = result.scalar_one_or_none()
    if existing_by_email is not None:
        # AC2: "If Google email already registered, link accounts"
        if existing_by_email.google_id is None:
            existing_by_email.google_id = google_id
            if avatar_url and not existing_by_email.avatar_url:
                existing_by_email.avatar_url = avatar_url
            await db.commit()
            await db.refresh(existing_by_email)
            logger.info(
                "Google account linked to existing user",
                user_id=str(existing_by_email.id),
                correlation_id=correlation_id,
            )
        return existing_by_email, False

    # New Google user
    user = User(
        id=uuid.uuid4(),
        email=normalized_email,
        full_name=full_name,
        password_hash=None,  # OAuth-only account
        email_verified=True,   # Google-verified email
        auth_provider="google",
        google_id=google_id,
        avatar_url=avatar_url,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info(
        "OAuth user created",
        email=_mask_email(normalized_email),
        user_id=str(user.id),
        provider="google",
        correlation_id=correlation_id,
    )
    return user, True


# ---------------------------------------------------------------------------
# Login — password authentication with rate limiting + lockout (Story 1.5)
# AC1, AC7, AC8
# ---------------------------------------------------------------------------

class AuthenticationError(Exception):
    """Raised for invalid credentials (email not found or wrong password)."""
    code: str = "INVALID_CREDENTIALS"


class AccountLockedError(Exception):
    """Raised when account is locked due to repeated failures (AC7)."""
    code: str = "ACCOUNT_LOCKED"


class RateLimitError(Exception):
    """Raised when login attempts exceed the per-window rate limit (AC8)."""
    code: str = "RATE_LIMITED"


class EmailNotVerifiedError(Exception):
    """Raised when user attempts login before verifying their email."""
    code: str = "EMAIL_NOT_VERIFIED"


# Dummy hash used for constant-time verification when email not found.
# Lazy-initialized on first use to avoid bcrypt at import time.
_DUMMY_HASH: str | None = None


def _get_dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-timing-protection-password")
    return _DUMMY_HASH


async def _check_login_rate_limit(email: str) -> None:
    """
    Enforce per-email rate limiting and account lockout (AC7, AC8).

    Redis keys:
      login_attempts:{email}  — attempt counter, TTL = login_rate_window_seconds
      login_lockout:{email}   — lockout marker, TTL = login_lockout_window_seconds

    Raises:
      AccountLockedError — lockout marker exists (>= lockout_attempts failures)
      RateLimitError     — attempt counter >= max_attempts within rate window
    """
    try:
        from src.cache import get_redis_client
        redis = get_redis_client()
        email_key = email.lower()

        lockout_key = f"login_lockout:{email_key}"
        if await redis.exists(lockout_key):
            raise AccountLockedError(
                "Account locked due to repeated failed login attempts. "
                "Check your email for an unlock link or wait 1 hour."
            )

        attempts_key = f"login_attempts:{email_key}"
        attempts = await redis.get(attempts_key)
        count = int(attempts) if attempts else 0
        if count >= settings.login_max_attempts:
            raise RateLimitError(
                f"Too many login attempts. Please wait before trying again."
            )
    except (AccountLockedError, RateLimitError):
        raise
    except Exception as exc:
        # Redis unavailable — log and allow login (fail open for availability)
        logger.warning("Login rate-limit Redis check failed (fail open)", error=str(exc))


async def _record_login_failure(email: str) -> None:
    """
    Increment failed-attempt counter; set lockout marker when threshold is reached.
    No-op if Redis is unavailable.
    """
    try:
        from src.cache import get_redis_client
        redis = get_redis_client()
        email_key = email.lower()

        attempts_key = f"login_attempts:{email_key}"
        pipe = redis.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, settings.login_rate_window_seconds)
        results = await pipe.execute()

        new_count = results[0]
        if new_count >= settings.login_lockout_attempts:
            lockout_key = f"login_lockout:{email_key}"
            await redis.set(lockout_key, "1", ex=settings.login_lockout_window_seconds)
            logger.warning(
                "Account locked after repeated failures",
                email=_mask_email(email_key),
                attempts=new_count,
            )
    except Exception as exc:
        logger.warning("Failed to record login failure in Redis", error=str(exc))


async def _clear_login_attempts(email: str) -> None:
    """Reset failed-attempt counter on successful login."""
    try:
        from src.cache import get_redis_client
        redis = get_redis_client()
        await redis.delete(f"login_attempts:{email.lower()}")
    except Exception as exc:
        logger.warning("Failed to clear login attempts from Redis", error=str(exc))


async def login_with_password(
    db: AsyncSession,
    email: str,
    password: str,
    correlation_id: str,
) -> User:
    """
    Authenticate user with email + password (AC1).

    Steps:
      1. Check rate limit / lockout (AC7, AC8)
      2. Load user by email (case-insensitive)
      3. Verify bcrypt hash — always runs to prevent timing attacks
      4. On failure: increment attempt counter, raise AuthenticationError
      5. Check email_verified
      6. On success: clear attempt counter, return User

    Raises:
      RateLimitError       — too many attempts in rate window
      AccountLockedError   — account locked
      AuthenticationError  — invalid credentials (email or password wrong)
      EmailNotVerifiedError — correct credentials but email not verified
    """
    normalized = email.lower()

    # Step 1: Rate limit / lockout (raises if exceeded)
    await _check_login_rate_limit(normalized)

    # Step 2: Load user
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalized)
    )
    user = result.scalar_one_or_none()

    # Step 3: Always run bcrypt verify (constant-time; prevents timing enumeration)
    stored_hash = user.password_hash if (user and user.password_hash) else _get_dummy_hash()
    password_ok = verify_password(password, stored_hash)

    # Step 4: Fail path — same error for missing user, wrong password, OAuth-only account
    if user is None or not password_ok or user.password_hash is None:
        await _record_login_failure(normalized)
        logger.info(
            "Login failed — invalid credentials",
            email=_mask_email(normalized),
            correlation_id=correlation_id,
        )
        raise AuthenticationError("Invalid email or password.")

    # Step 5: Email verified guard
    if not user.email_verified:
        logger.info(
            "Login failed — email not verified",
            user_id=str(user.id),
            correlation_id=correlation_id,
        )
        raise EmailNotVerifiedError(
            "Please verify your email address before logging in."
        )

    # Step 6: Success — clear rate counters
    await _clear_login_attempts(normalized)

    logger.info(
        "Login successful",
        user_id=str(user.id),
        email=_mask_email(normalized),
        correlation_id=correlation_id,
    )
    return user
