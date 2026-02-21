"""
Unit tests — TokenService
Story: 1-5-login-session-management
ACs: AC3 (RS256 JWT), AC4 (refresh rotation + reuse detection), AC5 (session storage)
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import JWTError

from src.services.token_service import TokenService, _token_hash, _tenant_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service() -> TokenService:
    return TokenService()


def _make_redis(mapping_value: bytes | None = None, session_json: bytes | None = None):
    """Build a minimal async Redis mock for token operations."""
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.set = MagicMock(return_value=pipeline)
    pipeline.sadd = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.srem = MagicMock(return_value=pipeline)
    pipeline.delete = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[True, True, True, True])
    mock.pipeline.return_value = pipeline
    mock.get = AsyncMock(return_value=mapping_value)
    mock.set = AsyncMock(return_value=True)
    mock.getdel = AsyncMock(return_value=mapping_value)
    mock.delete = AsyncMock(return_value=1)
    mock.smembers = AsyncMock(return_value=set())
    mock.srem = AsyncMock(return_value=1)
    mock.sadd = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


# ---------------------------------------------------------------------------
# AC3 — Access token (RS256 JWT)
# ---------------------------------------------------------------------------

class TestCreateAccessToken:
    def test_returns_string(self):
        svc = _make_service()
        token = svc.create_access_token(
            user_id=uuid.uuid4(),
            email="test@example.com",
            tenant_id=None,
            role=None,
        )
        assert isinstance(token, str)
        assert len(token) > 20

    def test_claims_present(self):
        svc = _make_service()
        uid = uuid.uuid4()
        tid = uuid.uuid4()
        token = svc.create_access_token(
            user_id=uid,
            email="user@example.com",
            tenant_id=tid,
            role="admin",
            tenant_slug="my-org",
        )
        payload = svc.validate_access_token(token)
        assert payload["sub"] == str(uid)
        assert payload["email"] == "user@example.com"
        assert payload["tenant_id"] == str(tid)
        assert payload["tenant_slug"] == "my-org"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_null_tenant_in_claims(self):
        svc = _make_service()
        token = svc.create_access_token(
            user_id=uuid.uuid4(),
            email="test@example.com",
            tenant_id=None,
            role=None,
        )
        payload = svc.validate_access_token(token)
        assert payload["tenant_id"] is None
        assert payload["role"] is None

    def test_tampered_token_raises(self):
        svc = _make_service()
        token = svc.create_access_token(
            user_id=uuid.uuid4(),
            email="test@example.com",
            tenant_id=None,
            role=None,
        )
        # Tamper with the middle of the signature section (third JWT part)
        parts = token.split(".")
        sig = parts[2]
        # Replace chars in the middle of the sig to ensure it differs meaningfully
        mid = len(sig) // 2
        corrupt_sig = sig[:mid] + ("AAAA" if sig[mid:mid+4] != "AAAA" else "ZZZZ") + sig[mid+4:]
        tampered = ".".join([parts[0], parts[1], corrupt_sig])
        with pytest.raises(JWTError):
            svc.validate_access_token(tampered)

    def test_expired_token_raises(self):
        """Token with exp in the past raises JWTError."""
        svc = _make_service()
        from unittest.mock import patch
        from datetime import timedelta

        with patch("src.services.token_service.settings") as mock_settings:
            mock_settings.jwt_access_token_expire_minutes = -1  # already expired
            mock_settings.jwt_refresh_token_expire_days = 7
            mock_settings.jwt_refresh_token_expire_days_remember_me = 30
            expired_token = svc.create_access_token(
                user_id=uuid.uuid4(),
                email="x@example.com",
                tenant_id=None,
                role=None,
            )

        with pytest.raises(JWTError):
            svc.validate_access_token(expired_token)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_token_hash_deterministic(self):
        raw = "my-test-token"
        assert _token_hash(raw) == _token_hash(raw)

    def test_token_hash_is_sha256(self):
        raw = "my-test-token"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert _token_hash(raw) == expected

    def test_tenant_key_none(self):
        assert _tenant_key(None) == "none"

    def test_tenant_key_uuid(self):
        uid = uuid.uuid4()
        assert _tenant_key(uid) == str(uid)


# ---------------------------------------------------------------------------
# AC5 — Refresh token creation (Redis session storage)
# ---------------------------------------------------------------------------

class TestCreateRefreshToken:
    @pytest.mark.asyncio
    async def test_returns_string_token(self):
        svc = _make_service()
        redis_mock = _make_redis()
        user_id = uuid.uuid4()

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            token = await svc.create_refresh_token(
                user_id=user_id,
                tenant_id=None,
                session_info={"ip": "127.0.0.1", "user_agent": "pytest"},
            )

        assert isinstance(token, str)
        assert len(token) > 20

    @pytest.mark.asyncio
    async def test_stores_in_redis_pipeline(self):
        svc = _make_service()
        redis_mock = _make_redis()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            await svc.create_refresh_token(
                user_id=user_id,
                tenant_id=tenant_id,
                session_info={"ip": "1.2.3.4"},
            )

        # Pipeline.execute should have been called (atomic writes)
        redis_mock.pipeline.return_value.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_remember_me_uses_longer_ttl(self):
        """remember_me=True should use jwt_refresh_token_expire_days_remember_me."""
        svc = _make_service()
        redis_mock = _make_redis()
        user_id = uuid.uuid4()
        calls = []

        original_set = redis_mock.pipeline.return_value.set

        def capture_set(key, value, **kwargs):
            calls.append(kwargs.get("ex"))
            return redis_mock.pipeline.return_value

        redis_mock.pipeline.return_value.set = capture_set

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            await svc.create_refresh_token(
                user_id=user_id,
                tenant_id=None,
                session_info={},
                remember_me=True,
            )

        # TTL should be 30-day in seconds (or 7-day) — at least one call with ex > 7 days
        assert any(ex is not None and ex > 7 * 86400 for ex in calls if ex)


# ---------------------------------------------------------------------------
# AC4 — Refresh token rotation
# ---------------------------------------------------------------------------

class TestRotateRefreshToken:
    @pytest.mark.asyncio
    async def test_valid_rotation_issues_new_token(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        old_token = "old-raw-token-123"
        old_hash = _token_hash(old_token)
        tenant_key = str(tenant_id)
        mapping = f"{user_id}:{tenant_key}".encode()
        session_data = json.dumps({
            "user_id": str(user_id),
            "tenant_id": str(tenant_id),
            "remember_me": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).encode()

        redis_mock = _make_redis(mapping_value=mapping, session_json=session_data)
        # getdel returns mapping (simulating found + deleted)
        redis_mock.getdel = AsyncMock(return_value=mapping)
        # get for primary key returns session_data
        redis_mock.get = AsyncMock(return_value=session_data)

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            new_token, returned_uid, returned_tid, _ = await svc.rotate_refresh_token(
                old_raw_token=old_token,
                session_info={"ip": "127.0.0.1"},
            )

        assert isinstance(new_token, str)
        assert new_token != old_token
        assert returned_uid == user_id
        assert returned_tid == tenant_id

    @pytest.mark.asyncio
    async def test_expired_token_raises_value_error(self):
        svc = _make_service()
        redis_mock = _make_redis()
        redis_mock.getdel = AsyncMock(return_value=None)   # not found
        redis_mock.get = AsyncMock(return_value=None)       # no revoke tombstone either

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            with pytest.raises(ValueError, match="expired or invalid"):
                await svc.rotate_refresh_token(
                    old_raw_token="some-expired-token",
                    session_info={},
                )

    @pytest.mark.asyncio
    async def test_reuse_detected_raises_and_invalidates_all(self):
        """If revoke_map exists but refresh_map is gone → reuse → revoke all."""
        svc = _make_service()
        user_id = uuid.uuid4()
        redis_mock = _make_redis()
        redis_mock.getdel = AsyncMock(return_value=None)        # token already consumed
        redis_mock.get = AsyncMock(return_value=str(user_id).encode())  # revoke_map found
        redis_mock.smembers = AsyncMock(return_value=set())     # no active sessions to delete

        invalidate_called = []

        original = svc.invalidate_all_user_tokens

        async def mock_invalidate(uid):
            invalidate_called.append(uid)
            return 0

        svc.invalidate_all_user_tokens = mock_invalidate

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            with pytest.raises(ValueError, match="REUSE"):
                await svc.rotate_refresh_token(
                    old_raw_token="already-rotated-token",
                    session_info={},
                )

        assert len(invalidate_called) == 1
        assert invalidate_called[0] == user_id


# ---------------------------------------------------------------------------
# AC5 — Session invalidation
# ---------------------------------------------------------------------------

class TestInvalidateTokens:
    @pytest.mark.asyncio
    async def test_invalidate_refresh_token_returns_true_when_found(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        raw = "valid-token-to-revoke"
        mapping = f"{user_id}:{tenant_id}".encode()

        redis_mock = _make_redis()
        redis_mock.getdel = AsyncMock(return_value=mapping)

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            result = await svc.invalidate_refresh_token(raw)

        assert result is True

    @pytest.mark.asyncio
    async def test_invalidate_refresh_token_returns_false_when_not_found(self):
        svc = _make_service()
        redis_mock = _make_redis()
        redis_mock.getdel = AsyncMock(return_value=None)

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            result = await svc.invalidate_refresh_token("no-such-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_all_deletes_all_sessions(self):
        svc = _make_service()
        user_id = uuid.uuid4()
        tenant_key = str(uuid.uuid4())
        thash = "abc123" * 10 + "abcd"  # 64 chars

        member = f"{tenant_key}:{thash}".encode()
        redis_mock = _make_redis()
        redis_mock.smembers = AsyncMock(return_value={member})

        with patch("src.cache.get_redis_client", return_value=redis_mock):
            count = await svc.invalidate_all_user_tokens(user_id)

        assert count == 1
        redis_mock.pipeline.return_value.execute.assert_called_once()
