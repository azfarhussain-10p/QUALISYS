"""
QUALISYS — Backup Code Service
Story: 1-7-two-factor-authentication-totp
AC: AC4 — Generate 10 single-use backup codes, store as bcrypt hashes
AC: AC6 — Verify code (bcrypt compare), mark used on match, warn when < 3 remain
AC: AC8 — Regenerate: delete all (used + unused), generate 10 new
AC: AC9 — Codes stored as bcrypt hashes (not plaintext or reversible encryption)

Backup code format: 8 alphanumeric characters (4 random hex bytes formatted upper)
Example: "A1B2C3D4" — 32 bits entropy per code (acceptable for single-use codes)
"""

import secrets
import string
from datetime import datetime, timezone

from passlib.context import CryptContext
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.models.user_backup_code import UserBackupCode

import uuid

# ---------------------------------------------------------------------------
# Backup code configuration
# ---------------------------------------------------------------------------

_NUM_BACKUP_CODES = 10       # Generate 10 codes per setup / regeneration
_CODE_LENGTH = 8             # 8 alphanumeric characters
_WARN_REMAINING_THRESHOLD = 3  # Show warning when fewer than 3 remain (AC6)

# Argon2id for backup codes — single-use so slightly lower params for speed.
# bcrypt deprecated fallback for existing codes generated before this migration.
_code_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__memory_cost=32768,   # 32 MiB (lighter than main auth — single-use codes)
    argon2__time_cost=2,
    argon2__parallelism=2,
)

# Alphanumeric character set (uppercase letters + digits)
_CODE_CHARS = string.ascii_uppercase + string.digits


def _generate_raw_code() -> str:
    """Generate one 8-character alphanumeric backup code using secrets module."""
    return "".join(secrets.choice(_CODE_CHARS) for _ in range(_CODE_LENGTH))


def _hash_code(raw_code: str) -> str:
    """Hash a backup code with bcrypt."""
    return _code_context.hash(raw_code)


def _verify_code_hash(raw_code: str, hashed: str) -> bool:
    """Verify raw code against stored bcrypt hash."""
    return _code_context.verify(raw_code, hashed)


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def generate_codes(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """
    Generate 10 new single-use backup codes and store their bcrypt hashes.

    The plaintext codes are returned ONCE for display to the user.
    They cannot be retrieved again — only verified.

    Args:
        db:      Database session
        user_id: User to generate codes for

    Returns:
        List of 10 plaintext backup codes (display once only)
    """
    raw_codes = [_generate_raw_code() for _ in range(_NUM_BACKUP_CODES)]

    backup_codes = [
        UserBackupCode(
            id=uuid.uuid4(),
            user_id=user_id,
            code_hash=_hash_code(code),
            used_at=None,
        )
        for code in raw_codes
    ]
    db.add_all(backup_codes)
    await db.flush()

    logger.info(
        "Backup codes generated",
        user_id=str(user_id),
        count=len(raw_codes),
    )
    return raw_codes


async def verify_code(
    db: AsyncSession,
    user_id: uuid.UUID,
    raw_code: str,
) -> bool:
    """
    Verify a backup code against stored bcrypt hashes.

    - Searches unused codes for the given user
    - bcrypt-compares raw_code against each hash (single correct match)
    - On match: marks the code as used (used_at = now) — single-use enforcement
    - Returns True if valid unused code was found and consumed; False otherwise

    Args:
        db:       Database session
        user_id:  User attempting backup code login
        raw_code: 8-character code entered by user

    Returns:
        True on valid + unused code (consumed); False on invalid / already used
    """
    # Load all unused backup codes for this user
    result = await db.execute(
        select(UserBackupCode).where(
            UserBackupCode.user_id == user_id,
            UserBackupCode.used_at.is_(None),
        )
    )
    unused_codes = result.scalars().all()

    for backup_code in unused_codes:
        if _verify_code_hash(raw_code, backup_code.code_hash):
            # Mark as used — single-use enforcement (AC6)
            backup_code.used_at = datetime.now(timezone.utc)
            await db.flush()
            logger.info(
                "Backup code used",
                user_id=str(user_id),
                code_id=str(backup_code.id),
            )
            return True

    logger.info(
        "Backup code verification failed",
        user_id=str(user_id),
    )
    return False


async def regenerate_codes(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[str]:
    """
    Delete ALL existing backup codes (used + unused) and generate 10 new ones.

    AC8: Regeneration invalidates old codes completely, including unused ones.
    Use case: user suspects compromise or has used most codes.

    Args:
        db:      Database session
        user_id: User to regenerate codes for

    Returns:
        List of 10 new plaintext backup codes (display once only)
    """
    # Delete all existing codes (used + unused)
    await db.execute(
        delete(UserBackupCode).where(UserBackupCode.user_id == user_id)
    )

    # Generate fresh set
    new_codes = await generate_codes(db, user_id)

    logger.info(
        "Backup codes regenerated",
        user_id=str(user_id),
    )
    return new_codes


async def get_remaining_count(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """
    Count unused backup codes for a user.

    AC6: When count < 3, frontend should warn user to regenerate.

    Args:
        db:      Database session
        user_id: User to query

    Returns:
        Number of unused backup codes remaining
    """
    result = await db.execute(
        select(func.count(UserBackupCode.id)).where(
            UserBackupCode.user_id == user_id,
            UserBackupCode.used_at.is_(None),
        )
    )
    return result.scalar_one() or 0
