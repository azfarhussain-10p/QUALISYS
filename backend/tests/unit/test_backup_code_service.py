"""
Unit Tests — Backup Code Service
Story: 1-7-two-factor-authentication-totp (Task 8.2)
AC: AC4 (generate 10 codes, bcrypt hashes), AC6 (verify, mark used), AC8 (regenerate)

Uses the in-memory SQLite test database provided by conftest.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user_backup_code import UserBackupCode
from src.services.backup_code_service import (
    _CODE_LENGTH,
    _NUM_BACKUP_CODES,
    _code_context,
    generate_codes,
    get_remaining_count,
    regenerate_codes,
    verify_code,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest_asyncio.fixture
async def codes_in_db(db_session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """Generate 10 backup codes for user_id; returns plaintext codes."""
    return await generate_codes(db_session, user_id)


# ---------------------------------------------------------------------------
# Task 8.2: Code generation (AC4)
# ---------------------------------------------------------------------------

class TestGenerateCodes:
    async def test_returns_ten_codes(self, db_session: AsyncSession, user_id: uuid.UUID):
        codes = await generate_codes(db_session, user_id)
        assert len(codes) == _NUM_BACKUP_CODES

    async def test_codes_are_8_chars(self, db_session: AsyncSession, user_id: uuid.UUID):
        codes = await generate_codes(db_session, user_id)
        for code in codes:
            assert len(code) == _CODE_LENGTH

    async def test_codes_are_alphanumeric_uppercase(self, db_session: AsyncSession, user_id: uuid.UUID):
        codes = await generate_codes(db_session, user_id)
        import string
        valid_chars = set(string.ascii_uppercase + string.digits)
        for code in codes:
            assert all(c in valid_chars for c in code), f"Code {code!r} contains invalid chars"

    async def test_codes_are_unique(self, db_session: AsyncSession, user_id: uuid.UUID):
        codes = await generate_codes(db_session, user_id)
        assert len(set(codes)) == len(codes), "All generated codes must be unique"

    async def test_hashes_stored_in_db(self, db_session: AsyncSession, user_id: uuid.UUID):
        codes = await generate_codes(db_session, user_id)
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = result.scalars().all()
        assert len(rows) == len(codes)

    async def test_hashes_are_bcrypt(self, db_session: AsyncSession, user_id: uuid.UUID):
        """Stored hashes must be bcrypt format (AC9: not plaintext)."""
        codes = await generate_codes(db_session, user_id)
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = result.scalars().all()
        for row in rows:
            assert row.code_hash.startswith("$2b$") or row.code_hash.startswith("$2a$"), (
                f"code_hash {row.code_hash!r} is not bcrypt — must never store plaintext"
            )

    async def test_codes_not_stored_as_plaintext(self, db_session: AsyncSession, user_id: uuid.UUID):
        """No plaintext code must appear in any stored hash."""
        codes = await generate_codes(db_session, user_id)
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = result.scalars().all()
        stored_hashes = {row.code_hash for row in rows}
        for code in codes:
            assert code not in stored_hashes, (
                f"Plaintext code {code!r} found verbatim in stored hashes"
            )

    async def test_used_at_is_null_initially(self, db_session: AsyncSession, user_id: uuid.UUID):
        await generate_codes(db_session, user_id)
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = result.scalars().all()
        for row in rows:
            assert row.used_at is None


# ---------------------------------------------------------------------------
# Task 8.2: Verification (AC6)
# ---------------------------------------------------------------------------

class TestVerifyCode:
    async def test_valid_code_returns_true(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        result = await verify_code(db_session, user_id, codes_in_db[0])
        assert result is True

    async def test_valid_code_marked_used(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        code = codes_in_db[0]
        await verify_code(db_session, user_id, code)
        # Re-query and verify used_at is set
        q = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = q.scalars().all()
        used_rows = [r for r in rows if r.used_at is not None]
        assert len(used_rows) == 1

    async def test_used_code_returns_false(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        code = codes_in_db[1]
        first = await verify_code(db_session, user_id, code)
        assert first is True
        # Second attempt must fail (single-use)
        second = await verify_code(db_session, user_id, code)
        assert second is False

    async def test_invalid_code_returns_false(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        result = await verify_code(db_session, user_id, "INVALID1")
        assert result is False

    async def test_wrong_user_returns_false(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        other_user = uuid.uuid4()
        result = await verify_code(db_session, other_user, codes_in_db[2])
        assert result is False

    async def test_multiple_codes_independent(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        """Using one code must not affect the validity of others."""
        await verify_code(db_session, user_id, codes_in_db[0])
        # Second code from the batch must still work
        result = await verify_code(db_session, user_id, codes_in_db[1])
        assert result is True


# ---------------------------------------------------------------------------
# Task 8.2: Remaining count + warning threshold (AC6)
# ---------------------------------------------------------------------------

class TestGetRemainingCount:
    async def test_full_count_after_generation(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        count = await get_remaining_count(db_session, user_id)
        assert count == _NUM_BACKUP_CODES

    async def test_decrements_after_use(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        await verify_code(db_session, user_id, codes_in_db[0])
        count = await get_remaining_count(db_session, user_id)
        assert count == _NUM_BACKUP_CODES - 1

    async def test_zero_when_no_codes(self, db_session: AsyncSession):
        unknown = uuid.uuid4()
        count = await get_remaining_count(db_session, unknown)
        assert count == 0

    async def test_low_threshold_detection(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        """Simulate using codes until fewer than 3 remain."""
        # Use 8 out of 10 codes
        for code in codes_in_db[:8]:
            await verify_code(db_session, user_id, code)
        count = await get_remaining_count(db_session, user_id)
        assert count == 2
        assert count < 3, "Should trigger frontend warning when < 3"


# ---------------------------------------------------------------------------
# Task 8.2: Regeneration (AC8)
# ---------------------------------------------------------------------------

class TestRegenerateCodes:
    async def test_returns_ten_new_codes(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        new_codes = await regenerate_codes(db_session, user_id)
        assert len(new_codes) == _NUM_BACKUP_CODES

    async def test_new_codes_differ_from_old(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        old_set = set(codes_in_db)
        new_codes = await regenerate_codes(db_session, user_id)
        # At least some new codes must differ (practically all should differ)
        overlap = old_set & set(new_codes)
        assert len(overlap) < len(old_set), "Regenerated codes should not match old codes"

    async def test_old_codes_no_longer_valid(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        old_code = codes_in_db[0]
        await regenerate_codes(db_session, user_id)
        result = await verify_code(db_session, user_id, old_code)
        assert result is False, "Old codes must be invalidated after regeneration"

    async def test_new_codes_are_valid(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        new_codes = await regenerate_codes(db_session, user_id)
        result = await verify_code(db_session, user_id, new_codes[0])
        assert result is True

    async def test_db_only_has_new_rows(
        self, db_session: AsyncSession, user_id: uuid.UUID, codes_in_db: list[str]
    ):
        """After regeneration, DB should have exactly _NUM_BACKUP_CODES rows."""
        await regenerate_codes(db_session, user_id)
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user_id)
        )
        rows = result.scalars().all()
        assert len(rows) == _NUM_BACKUP_CODES
