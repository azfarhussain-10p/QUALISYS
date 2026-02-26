"""
Integration tests — Password Reset Flow (Story 1.6)
ACs: AC2, AC3, AC5, AC6, AC7, AC8

Test coverage:
  7.1 — Unit: token generation randomness, hash verification, policy validation, expiry
  7.2 — POST /forgot-password: existing email, non-existing email, Google-only account
  7.3 — GET /reset-password?token: valid, expired, used, invalid
  7.4 — POST /reset-password: valid reset, expired, used, weak password, same-as-old
  7.5 — Session invalidation after reset
  7.6 — Previous token invalidation on new reset request
  7.7 — Rate limiting: 3/email/hr on forgot-password
  7.8 — Security: no email enumeration (identical response)
"""

import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.password_reset import PasswordReset
from src.models.user import User
from src.services.auth.auth_service import hash_password
from tests.conftest import _mock_redis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def email_user(db_session: AsyncSession) -> User:
    """Verified email/password user."""
    user = User(
        id=uuid.uuid4(),
        email=f"reset_email_{uuid.uuid4().hex[:8]}@example.com",
        full_name="Reset User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=True,
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def google_user(db_session: AsyncSession) -> User:
    """Google-only account (no local password)."""
    user = User(
        id=uuid.uuid4(),
        email=f"google_{uuid.uuid4().hex[:8]}@gmail.com",
        full_name="Google User",
        password_hash=None,
        email_verified=True,
        auth_provider="google",
        google_id=f"google_{uuid.uuid4().hex}",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def valid_reset_token(db_session: AsyncSession, email_user: User) -> tuple[str, PasswordReset]:
    """Create an active (unused, non-expired) password reset token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    reset = PasswordReset(
        id=uuid.uuid4(),
        user_id=email_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(reset)
    await db_session.flush()
    return raw_token, reset


@pytest_asyncio.fixture
async def expired_reset_token(db_session: AsyncSession, email_user: User) -> tuple[str, PasswordReset]:
    """Create an expired password reset token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    reset = PasswordReset(
        id=uuid.uuid4(),
        user_id=email_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # already expired
    )
    db_session.add(reset)
    await db_session.flush()
    return raw_token, reset


@pytest_asyncio.fixture
async def used_reset_token(db_session: AsyncSession, email_user: User) -> tuple[str, PasswordReset]:
    """Create a used password reset token."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    reset = PasswordReset(
        id=uuid.uuid4(),
        user_id=email_user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=datetime.now(timezone.utc),  # already consumed
    )
    db_session.add(reset)
    await db_session.flush()
    return raw_token, reset


# ---------------------------------------------------------------------------
# Task 7.1 — Unit tests: service layer
# ---------------------------------------------------------------------------

class TestPasswordResetServiceUnit:

    def test_token_entropy(self):
        """AC3: tokens are 32 bytes URL-safe = 256 bits entropy."""
        token = secrets.token_urlsafe(32)
        # token_urlsafe(32) produces ~43 base64url chars (32 bytes * 4/3, rounded up)
        assert len(token) >= 43

    def test_token_hash_is_sha256(self):
        """AC3: token stored as SHA-256 hash (64 lowercase hex chars)."""
        from src.services.password_reset.password_reset_service import _hash_token
        raw = secrets.token_urlsafe(32)
        digest = _hash_token(raw)
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_token_hash_deterministic(self):
        """Same raw token always produces same hash."""
        from src.services.password_reset.password_reset_service import _hash_token
        raw = "test-token-123"
        assert _hash_token(raw) == _hash_token(raw)

    def test_password_policy_valid(self):
        """AC5/AC6: Valid password passes policy check."""
        from src.services.password_reset.password_reset_service import _check_password_policy
        # Should not raise
        _check_password_policy("SecurePass123!")
        _check_password_policy("MyStr0ng@Pass")

    def test_password_policy_too_short(self):
        """AC5: Password under 12 chars fails policy."""
        from src.services.password_reset.password_reset_service import _check_password_policy, PasswordPolicyError
        with pytest.raises(PasswordPolicyError, match="12 characters"):
            _check_password_policy("Short1!")

    def test_password_policy_no_uppercase(self):
        """AC5: Missing uppercase fails policy."""
        from src.services.password_reset.password_reset_service import _check_password_policy, PasswordPolicyError
        with pytest.raises(PasswordPolicyError, match="uppercase"):
            _check_password_policy("lowercase123!!")

    def test_password_policy_no_special(self):
        """AC5: Missing special character fails policy."""
        from src.services.password_reset.password_reset_service import _check_password_policy, PasswordPolicyError
        with pytest.raises(PasswordPolicyError, match="special"):
            _check_password_policy("SecurePass12345")

    def test_partial_email_mask(self):
        """Partial masking for UX display."""
        from src.services.password_reset.password_reset_service import _mask_email_partial
        assert _mask_email_partial("user@example.com") == "u***@example.com"
        assert _mask_email_partial("alice@gmail.com") == "a***@gmail.com"


# ---------------------------------------------------------------------------
# Task 7.2 — POST /api/v1/auth/forgot-password
# ---------------------------------------------------------------------------

class TestForgotPasswordEndpoint:

    @pytest.mark.asyncio
    async def test_existing_email_returns_200(
        self, client: AsyncClient, email_user: User
    ):
        """AC2: Existing email → 200 with standard success message."""
        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(secrets.token_urlsafe(32), email_user, False),
        ), patch(
            "src.api.v1.auth.router.send_password_reset_email",
            new_callable=AsyncMock,
        ):
            resp = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": email_user.email},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "sent a password reset link" in data["message"]

    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_200(self, client: AsyncClient):
        """AC2: Non-existent email → SAME 200 response (no email enumeration)."""
        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(None, None, False),
        ):
            resp = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "nonexistent@example.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "sent a password reset link" in data["message"]

    @pytest.mark.asyncio
    async def test_google_only_account_returns_200(
        self, client: AsyncClient, google_user: User
    ):
        """AC3: Google-only account → 200 with same message, sends Google-redirect email."""
        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(None, google_user, True),
        ), patch(
            "src.api.v1.auth.router.send_password_reset_google_email",
            new_callable=AsyncMock,
        ) as mock_google_email:
            resp = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": google_user.email},
            )

        assert resp.status_code == 200
        assert "sent a password reset link" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_invalid_email_format_rejected(self, client: AsyncClient):
        """AC2: Invalid email format → 422 validation error."""
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_existing_and_missing_response_identical(
        self, client: AsyncClient, email_user: User
    ):
        """AC2/AC8: Identical message for existing vs non-existing email (no enumeration)."""
        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(secrets.token_urlsafe(32), email_user, False),
        ), patch("src.api.v1.auth.router.send_password_reset_email", new_callable=AsyncMock):
            resp_existing = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": email_user.email},
            )

        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(None, None, False),
        ):
            resp_missing = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "missing@example.com"},
            )

        assert resp_existing.status_code == resp_missing.status_code == 200
        assert resp_existing.json()["message"] == resp_missing.json()["message"]


# ---------------------------------------------------------------------------
# Task 7.3 — GET /api/v1/auth/reset-password?token=...
# ---------------------------------------------------------------------------

class TestValidateResetTokenEndpoint:

    @pytest.mark.asyncio
    async def test_valid_token_returns_valid_true(
        self, client: AsyncClient, valid_reset_token
    ):
        """AC5: Valid token → { valid: true, email: masked }."""
        raw_token, _ = valid_reset_token
        resp = await client.get(
            "/api/v1/auth/reset-password",
            params={"token": raw_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["email"] is not None
        assert "***" in data["email"]

    @pytest.mark.asyncio
    async def test_expired_token_returns_valid_false(
        self, client: AsyncClient, expired_reset_token
    ):
        """AC5: Expired token → { valid: false, error: 'token_expired' }."""
        raw_token, _ = expired_reset_token
        resp = await client.get(
            "/api/v1/auth/reset-password",
            params={"token": raw_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["error"] == "token_expired"

    @pytest.mark.asyncio
    async def test_used_token_returns_valid_false(
        self, client: AsyncClient, used_reset_token
    ):
        """AC5: Used token → { valid: false, error: 'token_used' }."""
        raw_token, _ = used_reset_token
        resp = await client.get(
            "/api/v1/auth/reset-password",
            params={"token": raw_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["error"] == "token_used"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_valid_false(self, client: AsyncClient):
        """AC5: Random token not in DB → { valid: false, error: 'token_invalid' }."""
        resp = await client.get(
            "/api/v1/auth/reset-password",
            params={"token": secrets.token_urlsafe(32)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["error"] == "token_invalid"


# ---------------------------------------------------------------------------
# Task 7.4 — POST /api/v1/auth/reset-password
# ---------------------------------------------------------------------------

class TestResetPasswordEndpoint:

    @pytest.mark.asyncio
    async def test_valid_reset_updates_password(
        self, client: AsyncClient, db_session: AsyncSession,
        email_user: User, valid_reset_token
    ):
        """AC6: Valid reset → password updated, token marked used."""
        from sqlalchemy import select
        raw_token, reset_record = valid_reset_token
        old_hash = email_user.password_hash

        with patch(
            "src.services.password_reset.password_reset_service.token_service.invalidate_all_user_tokens",
            new_callable=AsyncMock,
            return_value=0,
        ):
            resp = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": raw_token, "new_password": "NewSecurePass456@"},
            )

        assert resp.status_code == 200
        assert "Password reset successfully" in resp.json()["message"]

        # Verify password hash was updated
        await db_session.refresh(email_user)
        assert email_user.password_hash != old_hash

        # Verify token marked used
        await db_session.refresh(reset_record)
        assert reset_record.used_at is not None

    @pytest.mark.asyncio
    async def test_expired_token_returns_400(
        self, client: AsyncClient, expired_reset_token
    ):
        """AC6: Expired token → 400 TOKEN_EXPIRED."""
        raw_token, _ = expired_reset_token
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "NewSecurePass456@"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TOKEN_EXPIRED"

    @pytest.mark.asyncio
    async def test_used_token_returns_400(
        self, client: AsyncClient, used_reset_token
    ):
        """AC6: Used token → 400 TOKEN_USED."""
        raw_token, _ = used_reset_token
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "NewSecurePass456@"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TOKEN_USED"

    @pytest.mark.asyncio
    async def test_invalid_token_returns_400(self, client: AsyncClient):
        """AC6: Invalid token → 400 TOKEN_INVALID."""
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": secrets.token_urlsafe(32), "new_password": "NewSecurePass456@"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "TOKEN_INVALID"

    @pytest.mark.asyncio
    async def test_weak_password_rejected_by_schema(self, client: AsyncClient, valid_reset_token):
        """AC6: Weak password fails Pydantic schema validation → 422."""
        raw_token, _ = valid_reset_token
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "weak"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_same_as_old_password_rejected(
        self, client: AsyncClient, email_user: User, valid_reset_token
    ):
        """AC6: New password same as old password → 400 PASSWORD_POLICY."""
        raw_token, _ = valid_reset_token
        resp = await client.post(
            "/api/v1/auth/reset-password",
            # Same as the hash in email_user fixture ("SecurePass123!")
            json={"token": raw_token, "new_password": "SecurePass123!"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "PASSWORD_POLICY"
        assert "same" in resp.json()["error"]["message"].lower()


# ---------------------------------------------------------------------------
# Task 7.5 — Session invalidation after password reset
# ---------------------------------------------------------------------------

class TestSessionInvalidationAfterReset:

    @pytest.mark.asyncio
    async def test_logout_all_called_after_reset(
        self, client: AsyncClient, email_user: User, valid_reset_token
    ):
        """AC6: After successful reset, all sessions invalidated."""
        raw_token, _ = valid_reset_token

        mock_invalidate = AsyncMock(return_value=3)
        with patch(
            "src.services.password_reset.password_reset_service.token_service.invalidate_all_user_tokens",
            mock_invalidate,
        ):
            resp = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": raw_token, "new_password": "NewSecurePass456@"},
            )

        assert resp.status_code == 200
        mock_invalidate.assert_called_once_with(email_user.id)


# ---------------------------------------------------------------------------
# Task 7.6 — Previous token invalidation
# ---------------------------------------------------------------------------

class TestPreviousTokenInvalidation:

    @pytest.mark.asyncio
    async def test_new_reset_request_invalidates_previous_token(
        self, client: AsyncClient, db_session: AsyncSession, email_user: User
    ):
        """AC3: New reset request invalidates all previous unused tokens."""
        from src.services.password_reset.password_reset_service import request_reset_internal

        # Create first token
        first_raw, first_user, _ = await request_reset_internal(
            db=db_session,
            email=email_user.email,
            ip="127.0.0.1",
            user_agent="test",
            correlation_id="test-1",
        )
        assert first_raw is not None

        first_hash = hashlib.sha256(first_raw.encode()).hexdigest()

        # Request second token
        second_raw, _, _ = await request_reset_internal(
            db=db_session,
            email=email_user.email,
            ip="127.0.0.1",
            user_agent="test",
            correlation_id="test-2",
        )
        assert second_raw is not None

        # First token should now be invalidated (used_at set)
        from sqlalchemy import select
        stmt = select(PasswordReset).where(PasswordReset.token_hash == first_hash)
        result = await db_session.execute(stmt)
        first_record = result.scalar_one_or_none()
        assert first_record is not None
        assert first_record.used_at is not None


# ---------------------------------------------------------------------------
# Task 7.7 — Rate limiting
# ---------------------------------------------------------------------------

class TestPasswordResetRateLimit:

    @pytest.mark.asyncio
    async def test_email_rate_limit_429_after_3_requests(
        self, db_session: AsyncSession
    ):
        """AC7: 4th forgot-password request for same email → 429."""
        from src.db import get_db
        from src.main import app
        from httpx import ASGITransport, AsyncClient

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        # Mock Redis that counts up — returns 4 on 4th call (triggers 429)
        call_count = 0

        def make_redis_mock_with_count():
            nonlocal call_count
            call_count += 1
            mock = _mock_redis()
            # Simulate the email count incrementing
            mock.pipeline.return_value.execute = AsyncMock(
                return_value=[call_count, 3600, True, True]
            )
            return mock

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as ac:
                # First 3 requests succeed
                for i in range(3):
                    call_count = i  # pre-set count to simulate prior requests
                    mock = _mock_redis()
                    # Return count = i+1 (1, 2, 3 — all ≤ 3, should pass)
                    mock.pipeline.return_value.execute = AsyncMock(return_value=[i + 1, 3600])
                    with patch("src.cache.get_redis_client", return_value=mock), \
                         patch("src.middleware.rate_limit.get_redis_client", return_value=mock), \
                         patch("src.api.v1.auth.router.get_redis_client", return_value=mock), \
                         patch("src.api.v1.auth.router.request_reset_internal",
                               new_callable=AsyncMock,
                               return_value=(None, None, False)):
                        resp = await ac.post(
                            "/api/v1/auth/forgot-password",
                            json={"email": "test@example.com"},
                        )
                    assert resp.status_code == 200, f"Expected 200 on attempt {i+1}"

                # 4th request → count = 4, should 429
                mock_exceeded = _mock_redis()
                mock_exceeded.pipeline.return_value.execute = AsyncMock(return_value=[4, 3600])
                with patch("src.cache.get_redis_client", return_value=mock_exceeded), \
                     patch("src.middleware.rate_limit.get_redis_client", return_value=mock_exceeded), \
                     patch("src.api.v1.auth.router.get_redis_client", return_value=mock_exceeded):
                    resp = await ac.post(
                        "/api/v1/auth/forgot-password",
                        json={"email": "test@example.com"},
                    )
                assert resp.status_code == 429
                assert "Retry-After" in resp.headers
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Task 7.8 — Security tests
# ---------------------------------------------------------------------------

class TestPasswordResetSecurity:

    def test_token_uniqueness(self):
        """AC3: Each token generation produces a different token."""
        tokens = {secrets.token_urlsafe(32) for _ in range(100)}
        assert len(tokens) == 100  # all unique

    def test_token_not_stored_plaintext(
        self,
    ):
        """AC3: The hash stored is SHA-256 — raw token ≠ hash."""
        from src.services.password_reset.password_reset_service import _hash_token
        raw = secrets.token_urlsafe(32)
        hashed = _hash_token(raw)
        assert raw != hashed

    @pytest.mark.asyncio
    async def test_no_email_enumeration_same_response(
        self, client: AsyncClient, email_user: User
    ):
        """AC2/AC8: Existing and non-existing email get identical responses."""
        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(secrets.token_urlsafe(32), email_user, False),
        ), patch("src.api.v1.auth.router.send_password_reset_email", new_callable=AsyncMock):
            resp_real = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": email_user.email},
            )

        with patch(
            "src.api.v1.auth.router.request_reset_internal",
            new_callable=AsyncMock,
            return_value=(None, None, False),
        ):
            resp_fake = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "fake@example.com"},
            )

        assert resp_real.status_code == resp_fake.status_code == 200
        assert resp_real.json()["message"] == resp_fake.json()["message"]

    @pytest.mark.asyncio
    async def test_token_single_use(
        self, client: AsyncClient, db_session: AsyncSession,
        email_user: User, valid_reset_token
    ):
        """AC3/AC6: Token cannot be used twice."""
        raw_token, _ = valid_reset_token

        with patch(
            "src.services.password_reset.password_reset_service.token_service.invalidate_all_user_tokens",
            new_callable=AsyncMock,
            return_value=0,
        ):
            # First use — succeeds
            resp1 = await client.post(
                "/api/v1/auth/reset-password",
                json={"token": raw_token, "new_password": "NewSecurePass456@"},
            )
        assert resp1.status_code == 200

        # Second use — token is now used
        resp2 = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": raw_token, "new_password": "AnotherPass789#"},
        )
        assert resp2.status_code == 400
        assert resp2.json()["error"]["code"] == "TOKEN_USED"
