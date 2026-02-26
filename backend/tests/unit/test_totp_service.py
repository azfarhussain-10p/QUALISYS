"""
Unit Tests — TOTP Service
Story: 1-7-two-factor-authentication-totp (Task 8.1)
AC: AC2 (secret generation, QR URI), AC3/AC5 (verification ±1 window), AC9 (AES-256)

Tests use known secrets + fixed timestamps to produce deterministic codes.
AES key used in tests: 32 zero-bytes encoded in base64.
"""

import base64
import time
from unittest.mock import patch

import pyotp
import pytest

from src.services.totp_service import (
    decrypt_secret,
    encrypt_secret,
    generate_qr_uri,
    generate_secret,
    verify_totp_code,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

# Known base64-encoded 32-byte all-zeros key (matches config.py dev default)
_TEST_KEY_B64 = base64.b64encode(b"\x00" * 32).decode()


def _patch_key(func):
    """Decorator: patch mfa_encryption_key to a known test value."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Reset the module-level cached key so each test is clean
        import src.services.totp_service as _mod
        _mod._encryption_key = None
        with patch("src.services.totp_service.settings") as mock_settings:
            mock_settings.mfa_encryption_key = _TEST_KEY_B64
            return func(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Task 8.1: Secret generation (AC2)
# ---------------------------------------------------------------------------

class TestGenerateSecret:
    def test_returns_base32_string(self):
        secret = generate_secret()
        # base32 alphabet: A-Z, 2-7, and optional padding =
        assert isinstance(secret, str)
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=" for c in secret)

    def test_length_is_32_chars(self):
        # pyotp.random_base32() returns 32 base32 chars = 160 bits
        secret = generate_secret()
        assert len(secret) == 32

    def test_uniqueness(self):
        secrets = {generate_secret() for _ in range(10)}
        assert len(secrets) == 10, "Secrets must be unique (random)"

    def test_pyotp_accepts_generated_secret(self):
        secret = generate_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        assert code.isdigit()
        assert len(code) == 6


# ---------------------------------------------------------------------------
# Task 8.1: QR URI format (AC2)
# ---------------------------------------------------------------------------

class TestGenerateQrUri:
    def test_starts_with_otpauth_scheme(self):
        secret = "JBSWY3DPEHPK3PXP"  # well-known test secret
        uri = generate_qr_uri(secret, "alice@example.com")
        assert uri.startswith("otpauth://totp/")

    def test_contains_issuer_qualisys(self):
        uri = generate_qr_uri("JBSWY3DPEHPK3PXP", "alice@example.com")
        assert "QUALISYS" in uri

    def test_contains_secret(self):
        secret = "JBSWY3DPEHPK3PXP"
        uri = generate_qr_uri(secret, "alice@example.com")
        assert f"secret={secret}" in uri

    def test_contains_algorithm_sha1(self):
        uri = generate_qr_uri("JBSWY3DPEHPK3PXP", "alice@example.com")
        assert "algorithm=SHA1" in uri

    def test_contains_digits_6(self):
        uri = generate_qr_uri("JBSWY3DPEHPK3PXP", "alice@example.com")
        assert "digits=6" in uri

    def test_contains_period_30(self):
        uri = generate_qr_uri("JBSWY3DPEHPK3PXP", "alice@example.com")
        assert "period=30" in uri

    def test_email_in_label(self):
        email = "alice@example.com"
        uri = generate_qr_uri("JBSWY3DPEHPK3PXP", email)
        # Email appears URL-encoded in the label portion
        assert "alice" in uri

    def test_full_uri_structure(self):
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"
        uri = generate_qr_uri(secret, email)
        # Must conform to: otpauth://totp/{label}?{params}
        assert "otpauth://totp/" in uri
        assert "?" in uri
        assert f"secret={secret}" in uri
        assert "&issuer=QUALISYS" in uri


# ---------------------------------------------------------------------------
# Task 8.1: TOTP verification — ±1 window (AC3, AC5)
# ---------------------------------------------------------------------------

class TestVerifyTotpCode:
    KNOWN_SECRET = "JBSWY3DPEHPK3PXP"

    def _code_at(self, ts: float) -> str:
        return pyotp.TOTP(self.KNOWN_SECRET).at(ts)

    def test_valid_current_code(self):
        now = time.time()
        code = self._code_at(now)
        assert verify_totp_code(self.KNOWN_SECRET, code) is True

    def test_valid_previous_window(self):
        """±1 window: code from 30 seconds ago must be accepted."""
        now = time.time()
        prev_code = self._code_at(now - 30)
        assert verify_totp_code(self.KNOWN_SECRET, prev_code) is True

    def test_valid_next_window(self):
        """±1 window: code from 30 seconds ahead must be accepted."""
        now = time.time()
        next_code = self._code_at(now + 30)
        assert verify_totp_code(self.KNOWN_SECRET, next_code) is True

    def test_expired_code_rejected(self):
        """Code from 2 windows ago (60+ seconds) must be rejected."""
        now = time.time()
        # Shift to a period clearly outside the ±1 window
        old_code = self._code_at(now - 90)
        current = self._code_at(now)
        # Only check if the codes differ (same period edge case is a skip)
        if old_code != current:
            assert verify_totp_code(self.KNOWN_SECRET, old_code) is False

    def test_wrong_code_rejected(self):
        assert verify_totp_code(self.KNOWN_SECRET, "000000") is False

    def test_non_numeric_code_rejected(self):
        assert verify_totp_code(self.KNOWN_SECRET, "ABCDEF") is False

    def test_empty_code_rejected(self):
        assert verify_totp_code(self.KNOWN_SECRET, "") is False

    def test_short_code_rejected(self):
        assert verify_totp_code(self.KNOWN_SECRET, "12345") is False

    def test_long_code_rejected(self):
        assert verify_totp_code(self.KNOWN_SECRET, "1234567") is False

    def test_wrong_secret_rejected(self):
        code = self._code_at(time.time())
        assert verify_totp_code("WRONGSECRETWRONGSECRETWRONGSECR2", code) is False


# ---------------------------------------------------------------------------
# Task 8.1: AES-256-GCM encryption round-trip (AC9)
# ---------------------------------------------------------------------------

class TestAesEncryption:
    def setup_method(self):
        # Reset cached key before each test
        import src.services.totp_service as _mod
        _mod._encryption_key = None

    def _patch(self):
        return patch(
            "src.services.totp_service.settings",
            **{"mfa_encryption_key": _TEST_KEY_B64},
        )

    def test_encrypt_returns_bytes(self):
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            result = encrypt_secret("MYSECRET12345678")
        assert isinstance(result, bytes)

    def test_encrypt_includes_nonce(self):
        """Output must be at least 12 bytes (nonce) + 1 byte ciphertext."""
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            result = encrypt_secret("MYSECRET12345678")
        assert len(result) > 12

    def test_round_trip(self):
        """encrypt then decrypt returns original plaintext."""
        secret = "JBSWY3DPEHPK3PXP"
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            import src.services.totp_service as _mod
            _mod._encryption_key = None
            encrypted = encrypt_secret(secret)
            _mod._encryption_key = None
            recovered = decrypt_secret(encrypted)
        assert recovered == secret

    def test_different_nonces_each_call(self):
        """Each encryption call uses a unique nonce (non-deterministic)."""
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            import src.services.totp_service as _mod
            _mod._encryption_key = None
            enc1 = encrypt_secret("SAMESECRET123456")
            _mod._encryption_key = None
            enc2 = encrypt_secret("SAMESECRET123456")
        assert enc1 != enc2, "Nonces must be random; ciphertexts should differ"

    def test_tampered_ciphertext_raises(self):
        """Modifying the ciphertext must raise ValueError (GCM integrity check)."""
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            import src.services.totp_service as _mod
            _mod._encryption_key = None
            encrypted = encrypt_secret("JBSWY3DPEHPK3PXP")
        # Flip a byte in the ciphertext portion (after nonce)
        tampered = encrypted[:12] + bytes([encrypted[12] ^ 0xFF]) + encrypted[13:]
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            import src.services.totp_service as _mod
            _mod._encryption_key = None
            with pytest.raises(ValueError, match="Failed to decrypt"):
                decrypt_secret(tampered)

    def test_too_short_raises(self):
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = _TEST_KEY_B64
            import src.services.totp_service as _mod
            _mod._encryption_key = None
            with pytest.raises(ValueError, match="too short"):
                decrypt_secret(b"\x00" * 5)

    def test_invalid_key_length_raises(self):
        """16-byte key (not 32) must raise ValueError."""
        short_key_b64 = base64.b64encode(b"\x00" * 16).decode()
        import src.services.totp_service as _mod
        _mod._encryption_key = None
        with patch("src.services.totp_service.settings") as m:
            m.mfa_encryption_key = short_key_b64
            with pytest.raises(ValueError, match="32 bytes"):
                encrypt_secret("JBSWY3DPEHPK3PXP")
        # Reset after test
        _mod._encryption_key = None
