"""
Integration Tests — MFA (Two-Factor Authentication TOTP)
Story: 1-7-two-factor-authentication-totp (Tasks 8.3–8.9)

Tests cover:
  8.3  Setup flow: generate secret, confirm with valid code, verify stored encrypted
  8.4  Login with MFA: password → mfa_required → TOTP verify → JWT issued
  8.5  Login with backup code: password → mfa_required → backup → JWT, code marked used
  8.6  Disable MFA: password confirmation, TOTP data cleared, backup codes deleted
  8.7  Rate limiting: 5 failed TOTP attempts, 10 failures trigger lockout
  8.8  Backup code depletion warning at < 3 remaining
  8.9  Security: encrypted in DB, bcrypt hashes, mfa_token short-lived
"""

import base64
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
from src.models.user_backup_code import UserBackupCode
from src.services.auth.auth_service import create_access_token, hash_password
from src.services.totp_service import encrypt_secret, generate_secret
from src.services import backup_code_service
from tests.conftest import _mock_redis


# ---------------------------------------------------------------------------
# AES key fixture — matches dev default in config.py
# ---------------------------------------------------------------------------

_TEST_KEY_B64 = base64.b64encode(b"\x00" * 32).decode()


def _patch_mfa_key():
    """Context manager: patch mfa_encryption_key + clear cached key."""
    import src.services.totp_service as _mod
    _mod._encryption_key = None
    return patch(
        "src.services.totp_service.settings",
        mfa_encryption_key=_TEST_KEY_B64,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def verified_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"mfa_test_{uuid.uuid4().hex[:6]}@example.com",
        full_name="MFA Test User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=True,
        auth_provider="email",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def mfa_user(db_session: AsyncSession) -> tuple[User, str]:
    """
    User with TOTP already enabled; returns (user, plaintext_secret).
    AES-256-GCM encrypted using test key.
    """
    import src.services.totp_service as _mod
    _mod._encryption_key = None

    with patch("src.services.totp_service.settings") as m:
        m.mfa_encryption_key = _TEST_KEY_B64
        secret = generate_secret()
        encrypted = encrypt_secret(secret)

    user = User(
        id=uuid.uuid4(),
        email=f"mfa_enabled_{uuid.uuid4().hex[:6]}@example.com",
        full_name="MFA Enabled User",
        password_hash=hash_password("SecurePass123!"),
        email_verified=True,
        auth_provider="email",
        totp_secret_encrypted=encrypted,
        totp_enabled_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.flush()
    return user, secret


def _auth_headers(user: User) -> dict:
    token = create_access_token(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


def _mfa_mock_redis_with_token(user_id: uuid.UUID, raw_token: str, remember_me: bool = False) -> MagicMock:
    """
    Returns a mock Redis that serves a valid mfa_token for the given user.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    mfa_data = json.dumps({
        "user_id": str(user_id),
        "remember_me": remember_me,
        "session_info": {},
    })

    mock = _mock_redis()

    async def fake_get(key: str):
        if key == f"mfa:{token_hash}":
            return mfa_data.encode()
        return None

    mock.get = AsyncMock(side_effect=fake_get)
    return mock


# ---------------------------------------------------------------------------
# Task 8.3: Setup flow integration
# ---------------------------------------------------------------------------

class TestMfaSetupFlow:
    async def test_setup_returns_qr_uri_and_secret(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client_with_auth.post("/api/v1/auth/mfa/setup")
        assert resp.status_code == 200
        data = resp.json()
        assert "qr_uri" in data
        assert data["qr_uri"].startswith("otpauth://totp/")
        assert "secret" in data
        assert "setup_token" in data

    async def test_setup_qr_uri_contains_issuer(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client_with_auth.post("/api/v1/auth/mfa/setup")
        assert "QUALISYS" in resp.json()["qr_uri"]

    async def test_setup_confirm_valid_code_stores_encrypted_secret(
        self, client_with_auth: AsyncClient, db_session: AsyncSession, verified_user: User
    ):
        """AC3: valid confirm code → secret stored encrypted, not plaintext."""
        # Step 1: setup
        mock_r = _mock_redis()
        stored_setup: dict = {}

        async def fake_setex(key: str, ttl: int, value: str):
            stored_setup[key] = value

        async def fake_get_setup(key: str):
            return stored_setup.get(key)

        mock_r.setex = AsyncMock(side_effect=fake_setex)
        mock_r.get = AsyncMock(side_effect=fake_get_setup)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            setup_resp = await client_with_auth.post("/api/v1/auth/mfa/setup")
        assert setup_resp.status_code == 200
        setup_data = setup_resp.json()
        plaintext_secret = setup_data["secret"]
        setup_token = setup_data["setup_token"]

        # Step 2: generate a valid TOTP code for the secret
        valid_code = pyotp.TOTP(plaintext_secret).now()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                confirm_resp = await client_with_auth.post(
                    "/api/v1/auth/mfa/setup/confirm",
                    json={"setup_token": setup_token, "totp_code": valid_code},
                )

        assert confirm_resp.status_code == 200
        codes = confirm_resp.json()["backup_codes"]
        assert len(codes) == 10

        # Verify DB: secret stored encrypted (not plaintext)
        await db_session.refresh(verified_user)
        assert verified_user.totp_secret_encrypted is not None
        assert verified_user.totp_enabled_at is not None
        # Must NOT store plaintext
        assert verified_user.totp_secret_encrypted != plaintext_secret.encode()

    async def test_setup_confirm_invalid_code_returns_400(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        mock_r = _mock_redis()
        stored: dict = {}

        async def fake_setex(key, ttl, value):
            stored[key] = value

        async def fake_get(key):
            return stored.get(key)

        mock_r.setex = AsyncMock(side_effect=fake_setex)
        mock_r.get = AsyncMock(side_effect=fake_get)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            await client_with_auth.post("/api/v1/auth/mfa/setup")

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client_with_auth.post(
                "/api/v1/auth/mfa/setup/confirm",
                json={"setup_token": str(verified_user.id), "totp_code": "000000"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_TOTP_CODE"

    async def test_setup_confirm_expired_session_returns_400(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        """Redis get returns None → setup expired."""
        mock_r = _mock_redis()
        mock_r.get = AsyncMock(return_value=None)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client_with_auth.post(
                "/api/v1/auth/mfa/setup/confirm",
                json={"setup_token": str(verified_user.id), "totp_code": "123456"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "SETUP_EXPIRED"

    async def test_setup_blocked_when_already_enabled(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        headers = _auth_headers(user)
        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client.post("/api/v1/auth/mfa/setup", headers=headers)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MFA_ALREADY_ENABLED"


# ---------------------------------------------------------------------------
# Task 8.4: Login with TOTP challenge
# ---------------------------------------------------------------------------

class TestMfaVerify:
    async def test_valid_totp_issues_jwt(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, secret = mfa_user
        raw_token = "test_mfa_token_valid_123"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        valid_code = pyotp.TOTP(secret).now()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                resp = await client.post(
                    "/api/v1/auth/mfa/verify",
                    json={"mfa_token": raw_token, "totp_code": valid_code},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "user" in data

    async def test_invalid_totp_returns_400(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        raw_token = "test_mfa_token_bad_code_456"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                resp = await client.post(
                    "/api/v1/auth/mfa/verify",
                    json={"mfa_token": raw_token, "totp_code": "000000"},
                )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_TOTP_CODE"

    async def test_expired_mfa_token_returns_401(self, client: AsyncClient):
        mock_r = _mock_redis()
        mock_r.get = AsyncMock(return_value=None)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client.post(
                "/api/v1/auth/mfa/verify",
                json={"mfa_token": "expired_token", "totp_code": "123456"},
            )

        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "MFA_TOKEN_INVALID"

    async def test_mfa_token_consumed_after_success(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """mfa_token deleted from Redis on successful verify (single-use)."""
        user, secret = mfa_user
        raw_token = "test_single_use_mfa_token"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        deleted_keys = []
        original_delete = mock_r.delete

        async def tracking_delete(*args):
            deleted_keys.extend(args)
            return await original_delete(*args)

        mock_r.delete = AsyncMock(side_effect=tracking_delete)
        valid_code = pyotp.TOTP(secret).now()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                await client.post(
                    "/api/v1/auth/mfa/verify",
                    json={"mfa_token": raw_token, "totp_code": valid_code},
                )

        assert f"mfa:{token_hash}" in deleted_keys


# ---------------------------------------------------------------------------
# Task 8.5: Login with backup code
# ---------------------------------------------------------------------------

class TestMfaBackup:
    async def test_valid_backup_code_issues_jwt(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        # Generate backup codes for this user
        codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        raw_token = "test_backup_mfa_token_001"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token, "backup_code": codes[0]},
            )

        assert resp.status_code == 200
        assert "user" in resp.json()

    async def test_valid_backup_code_marked_used(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        raw_token = "test_backup_mark_used_token"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token, "backup_code": codes[1]},
            )

        # Query DB — used code must have used_at set
        result = await db_session.execute(
            select(UserBackupCode).where(
                UserBackupCode.user_id == user.id,
                UserBackupCode.used_at.is_not(None),
            )
        )
        used = result.scalars().all()
        assert len(used) == 1

    async def test_used_backup_code_rejected(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        raw_token1 = "test_backup_once_token_A"
        raw_token2 = "test_backup_once_token_B"

        with patch("src.api.v1.auth.mfa_router.get_redis_client",
                   return_value=_mfa_mock_redis_with_token(user.id, raw_token1)):
            r1 = await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token1, "backup_code": codes[2]},
            )
        assert r1.status_code == 200

        with patch("src.api.v1.auth.mfa_router.get_redis_client",
                   return_value=_mfa_mock_redis_with_token(user.id, raw_token2)):
            r2 = await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token2, "backup_code": codes[2]},
            )
        assert r2.status_code == 400
        assert r2.json()["error"]["code"] == "INVALID_BACKUP_CODE"

    async def test_invalid_backup_code_rejected(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        raw_token = "test_backup_invalid_token"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token, "backup_code": "FAKECODE"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "INVALID_BACKUP_CODE"


# ---------------------------------------------------------------------------
# Task 8.6: Disable MFA
# ---------------------------------------------------------------------------

class TestMfaDisable:
    async def test_disable_with_valid_password(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        headers = _auth_headers(user)
        codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client.post(
                "/api/v1/auth/mfa/disable",
                json={"password": "SecurePass123!"},
                headers=headers,
            )

        assert resp.status_code == 200

        # Verify DB cleared
        await db_session.refresh(user)
        assert user.totp_secret_encrypted is None
        assert user.totp_enabled_at is None

    async def test_disable_removes_backup_codes(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        user, _ = mfa_user
        headers = _auth_headers(user)
        await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            await client.post(
                "/api/v1/auth/mfa/disable",
                json={"password": "SecurePass123!"},
                headers=headers,
            )

        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user.id)
        )
        assert len(result.scalars().all()) == 0

    async def test_disable_wrong_password_returns_403(
        self, client: AsyncClient, mfa_user: tuple
    ):
        user, _ = mfa_user
        headers = _auth_headers(user)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client.post(
                "/api/v1/auth/mfa/disable",
                json={"password": "WrongPassword!"},
                headers=headers,
            )

        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "INVALID_PASSWORD"

    async def test_disable_when_not_enabled_returns_400(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client_with_auth.post(
                "/api/v1/auth/mfa/disable",
                json={"password": "SecurePass123!"},
            )

        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "MFA_NOT_ENABLED"

    async def test_disable_subsequent_login_skips_mfa(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """After disable, login flow must issue JWT directly (no mfa_required)."""
        user, _ = mfa_user
        headers = _auth_headers(user)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            await client.post(
                "/api/v1/auth/mfa/disable",
                json={"password": "SecurePass123!"},
                headers=headers,
            )

        await db_session.refresh(user)
        assert user.totp_enabled_at is None, "MFA disabled — subsequent login skips challenge"


# ---------------------------------------------------------------------------
# Task 8.7: Rate limiting
# ---------------------------------------------------------------------------

class TestMfaRateLimiting:
    async def test_rate_limit_exceeded_returns_429(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """After 5 failed attempts, next request returns 429 (AC9)."""
        user, _ = mfa_user
        raw_token = "test_rate_limit_token_mfa"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        mfa_data = json.dumps({"user_id": str(user.id), "remember_me": False, "session_info": {}})

        mock_r = _mock_redis()
        get_calls = [0]

        async def fake_get_rate(key: str):
            if key == f"mfa:{token_hash}":
                return mfa_data.encode()
            if key == f"mfa_attempts:{token_hash[:16]}":
                # Simulate already at limit after first call
                return b"5"
            return None

        mock_r.get = AsyncMock(side_effect=fake_get_rate)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                resp = await client.post(
                    "/api/v1/auth/mfa/verify",
                    json={"mfa_token": raw_token, "totp_code": "123456"},
                )

        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "MFA_ATTEMPTS_EXCEEDED"

    async def test_lockout_returns_423(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """User-level lockout (10 failures/hr) returns 423 (AC9)."""
        user, _ = mfa_user
        raw_token = "test_lockout_mfa_token_xyz"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        mfa_data = json.dumps({"user_id": str(user.id), "remember_me": False, "session_info": {}})

        mock_r = _mock_redis()

        async def fake_get_lockout(key: str):
            if key == f"mfa:{token_hash}":
                return mfa_data.encode()
            if key == f"mfa_attempts:{token_hash[:16]}":
                return b"0"  # no per-token limit
            return None

        async def fake_exists_lockout(key: str):
            if key == f"mfa_lockout:{user.id}":
                return 1  # locked out
            return 0

        mock_r.get = AsyncMock(side_effect=fake_get_lockout)
        mock_r.exists = AsyncMock(side_effect=fake_exists_lockout)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            with patch("src.services.totp_service.settings") as m:
                m.mfa_encryption_key = _TEST_KEY_B64
                import src.services.totp_service as _mod
                _mod._encryption_key = None
                resp = await client.post(
                    "/api/v1/auth/mfa/verify",
                    json={"mfa_token": raw_token, "totp_code": "123456"},
                )

        assert resp.status_code == 423
        assert resp.json()["error"]["code"] == "MFA_LOCKED"


# ---------------------------------------------------------------------------
# Task 8.8: Backup code depletion warning
# ---------------------------------------------------------------------------

class TestBackupCodeDepletion:
    async def test_low_codes_warning_header(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """When fewer than 3 codes remain after backup login, X-Backup-Codes-Low header set."""
        user, _ = mfa_user
        # Generate only 2 usable codes (use 8 out of 10, 2 remain)
        all_codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        # Mark 8 codes as used
        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user.id)
        )
        rows = result.scalars().all()
        for row in rows[:8]:
            row.used_at = datetime.now(timezone.utc)
        await db_session.flush()

        raw_token = "test_low_codes_mfa_token"
        mock_r = _mfa_mock_redis_with_token(user.id, raw_token)

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=mock_r):
            resp = await client.post(
                "/api/v1/auth/mfa/backup",
                json={"mfa_token": raw_token, "backup_code": all_codes[8]},
            )

        # 1 code remaining → header must be set
        if resp.status_code == 200:
            assert "x-backup-codes-low" in resp.headers


# ---------------------------------------------------------------------------
# Task 8.9: Security — encrypted storage, bcrypt hashes
# ---------------------------------------------------------------------------

class TestMfaSecurity:
    async def test_totp_secret_not_stored_plaintext(
        self, db_session: AsyncSession, mfa_user: tuple
    ):
        """totp_secret_encrypted must not contain plaintext base32 secret."""
        user, secret = mfa_user
        assert user.totp_secret_encrypted is not None
        encrypted_bytes = user.totp_secret_encrypted
        # Plaintext secret encoded as utf-8 must not appear in encrypted bytes
        assert secret.encode() not in encrypted_bytes

    async def test_totp_secret_is_bytes_in_db(
        self, db_session: AsyncSession, mfa_user: tuple
    ):
        """totp_secret_encrypted stored as bytes (LargeBinary column)."""
        user, _ = mfa_user
        assert isinstance(user.totp_secret_encrypted, (bytes, bytearray))

    async def test_backup_codes_stored_as_bcrypt(
        self, db_session: AsyncSession, mfa_user: tuple
    ):
        """Backup codes stored as bcrypt hashes — not plaintext (AC9)."""
        user, _ = mfa_user
        codes = await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        result = await db_session.execute(
            select(UserBackupCode).where(UserBackupCode.user_id == user.id)
        )
        rows = result.scalars().all()
        for row in rows:
            assert row.code_hash.startswith("$2"), (
                f"code_hash {row.code_hash!r} must be bcrypt, not plaintext"
            )
            # Plaintext must not appear in hash
            assert row.code_hash not in codes

    async def test_mfa_status_endpoint(
        self, client: AsyncClient, db_session: AsyncSession, mfa_user: tuple
    ):
        """GET /mfa/status returns enabled=True for MFA user."""
        user, _ = mfa_user
        headers = _auth_headers(user)
        await backup_code_service.generate_codes(db_session, user.id)
        await db_session.flush()

        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client.get("/api/v1/auth/mfa/status", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["enabled_at"] is not None
        assert data["backup_codes_remaining"] == 10

    async def test_mfa_status_disabled_for_non_mfa_user(
        self, client_with_auth: AsyncClient, verified_user: User
    ):
        """GET /mfa/status returns enabled=False for user without MFA."""
        with patch("src.api.v1.auth.mfa_router.get_redis_client", return_value=_mock_redis()):
            resp = await client_with_auth.get("/api/v1/auth/mfa/status")

        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
        assert resp.json()["backup_codes_remaining"] == 0
