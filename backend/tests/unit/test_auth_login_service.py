"""
Unit tests — login_with_password (AuthService Story 1.5)
ACs: AC1 (credential verification), AC7 (account lockout), AC8 (rate limiting)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.auth.auth_service import (
    AccountLockedError,
    AuthenticationError,
    EmailNotVerifiedError,
    RateLimitError,
    hash_password,
    login_with_password,
)
from src.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(
    email_verified: bool = True,
    password: str = "SecurePass123!",
    auth_provider: str = "email",
) -> User:
    user = User(
        id=uuid.uuid4(),
        email="login@example.com",
        full_name="Login User",
        password_hash=hash_password(password) if password else None,
        email_verified=email_verified,
        auth_provider=auth_provider,
    )
    return user


def _make_db(user: User | None) -> AsyncSession:
    """Mock DB that returns the given user on query execution."""
    mock_db = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = user
    mock_db.execute = AsyncMock(return_value=result_mock)
    return mock_db


def _make_redis_no_limits():
    """Redis mock that never triggers rate limits or lockout."""
    redis = MagicMock()
    redis.exists = AsyncMock(return_value=0)     # no lockout
    redis.get = AsyncMock(return_value=None)      # zero attempts
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, True])
    redis.pipeline.return_value = pipeline
    return redis


# ---------------------------------------------------------------------------
# AC1 — Successful login
# ---------------------------------------------------------------------------

class TestLoginSuccess:
    @pytest.mark.asyncio
    async def test_returns_user_on_valid_credentials(self):
        user = _make_user(email_verified=True)
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            result = await login_with_password(
                db=db,
                email="login@example.com",
                password="SecurePass123!",
                correlation_id="test-corr-id",
            )

        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_clears_attempt_counter_on_success(self):
        user = _make_user(email_verified=True)
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            await login_with_password(
                db=db,
                email="login@example.com",
                password="SecurePass123!",
                correlation_id="test",
            )

        redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_case_insensitive(self):
        user = _make_user(email_verified=True)
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            result = await login_with_password(
                db=db,
                email="LOGIN@EXAMPLE.COM",  # uppercase
                password="SecurePass123!",
                correlation_id="test",
            )

        assert result.id == user.id


# ---------------------------------------------------------------------------
# AC8 — Authentication failures (no enumeration)
# ---------------------------------------------------------------------------

class TestLoginFailures:
    @pytest.mark.asyncio
    async def test_wrong_password_raises_auth_error(self):
        user = _make_user(email_verified=True)
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(AuthenticationError):
                await login_with_password(
                    db=db,
                    email="login@example.com",
                    password="WrongPassword999!",
                    correlation_id="test",
                )

    @pytest.mark.asyncio
    async def test_unknown_email_raises_auth_error(self):
        db = _make_db(None)  # user not found
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(AuthenticationError):
                await login_with_password(
                    db=db,
                    email="nobody@example.com",
                    password="SomePassword123!",
                    correlation_id="test",
                )

    @pytest.mark.asyncio
    async def test_oauth_only_user_raises_auth_error(self):
        """User with auth_provider='google' (no password_hash) → same error, no enumeration."""
        user = _make_user(email_verified=True, password=None, auth_provider="google")
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(AuthenticationError):
                await login_with_password(
                    db=db,
                    email="login@example.com",
                    password="AnyPassword123!",
                    correlation_id="test",
                )

    @pytest.mark.asyncio
    async def test_unverified_email_raises_specific_error(self):
        user = _make_user(email_verified=False)
        db = _make_db(user)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(EmailNotVerifiedError):
                await login_with_password(
                    db=db,
                    email="login@example.com",
                    password="SecurePass123!",
                    correlation_id="test",
                )

    @pytest.mark.asyncio
    async def test_failure_increments_attempt_counter(self):
        db = _make_db(None)
        redis = _make_redis_no_limits()

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(AuthenticationError):
                await login_with_password(
                    db=db,
                    email="nobody@example.com",
                    password="Wrong123!",
                    correlation_id="test",
                )

        redis.pipeline.return_value.execute.assert_called()


# ---------------------------------------------------------------------------
# AC7 — Account lockout
# ---------------------------------------------------------------------------

class TestAccountLockout:
    @pytest.mark.asyncio
    async def test_lockout_raises_before_db_query(self):
        """Account lockout check happens before any DB query (fail fast)."""
        user = _make_user()
        db = _make_db(user)
        redis = _make_redis_no_limits()
        redis.exists = AsyncMock(return_value=1)  # lockout active

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(AccountLockedError):
                await login_with_password(
                    db=db,
                    email="locked@example.com",
                    password="SecurePass123!",
                    correlation_id="test",
                )

        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_raises_before_db_query(self):
        user = _make_user()
        db = _make_db(user)
        redis = _make_redis_no_limits()
        redis.get = AsyncMock(return_value=b"5")  # 5 attempts → at max_attempts

        with patch("src.cache.get_redis_client", return_value=redis):
            with pytest.raises(RateLimitError):
                await login_with_password(
                    db=db,
                    email="limited@example.com",
                    password="SecurePass123!",
                    correlation_id="test",
                )

        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_failure_allows_login(self):
        """If Redis is unavailable, login should proceed (fail-open for availability)."""
        user = _make_user(email_verified=True)
        db = _make_db(user)
        redis = _make_redis_no_limits()
        # Simulate Redis connection error
        redis.exists = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("src.cache.get_redis_client", return_value=redis):
            result = await login_with_password(
                db=db,
                email="login@example.com",
                password="SecurePass123!",
                correlation_id="test",
            )

        assert result.id == user.id
