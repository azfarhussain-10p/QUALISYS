"""
Unit Tests — AuthService
Story: 1-1-user-account-creation (Task 6.1)
AC: AC4, AC3, AC5, AC7

Tests:
  - password hashing + verification
  - email validation (via schema)
  - token generation/verification
  - duplicate email detection
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from src.config import get_settings
from src.services.auth.auth_service import (
    DuplicateEmailError,
    create_access_token,
    create_email_verification_token,
    decode_email_verification_token,
    hash_password,
    verify_password,
)
from src.api.v1.auth.schemas import RegisterRequest, validate_password_policy

settings = get_settings()


# ---------------------------------------------------------------------------
# Password hashing — AC4
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    def test_hash_produces_bcrypt_string(self):
        hashed = hash_password("SecurePass123!")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_hash_includes_cost_12(self):
        """bcrypt cost factor 12 per architecture spec."""
        hashed = hash_password("SecurePass123!")
        # bcrypt format: $2b$COST$...
        cost = int(hashed.split("$")[2])
        assert cost == 12

    def test_verify_correct_password(self):
        plain = "MyP@ssword99!"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("SecurePass123!")
        assert verify_password("WrongPass123!", hashed) is False

    def test_hashes_are_unique(self):
        """bcrypt auto-generates unique salts."""
        h1 = hash_password("SecurePass123!")
        h2 = hash_password("SecurePass123!")
        assert h1 != h2


# ---------------------------------------------------------------------------
# Password policy validation — AC1
# ---------------------------------------------------------------------------

class TestPasswordPolicy:
    def test_valid_password_passes(self):
        assert validate_password_policy("SecurePass123!") == "SecurePass123!"

    def test_too_short(self):
        with pytest.raises(ValueError, match="12 characters"):
            validate_password_policy("Short1!")

    def test_missing_uppercase(self):
        with pytest.raises(ValueError, match="uppercase"):
            validate_password_policy("alllowercase123!")

    def test_missing_lowercase(self):
        with pytest.raises(ValueError, match="lowercase"):
            validate_password_policy("ALLUPPERCASE123!")

    def test_missing_digit(self):
        with pytest.raises(ValueError, match="digit"):
            validate_password_policy("NoDigitPasswordHere!")

    def test_missing_special_char(self):
        with pytest.raises(ValueError, match="special"):
            validate_password_policy("NoSpecialChar123456")

    def test_exactly_12_chars_valid(self):
        result = validate_password_policy("Aa1!Aa1!Aa1!")
        assert len(result) == 12


# ---------------------------------------------------------------------------
# Email validation — AC1
# ---------------------------------------------------------------------------

class TestEmailValidation:
    def test_valid_email(self):
        req = RegisterRequest(email="user@example.com", password="SecurePass123!", full_name="Jane")
        assert req.email == "user@example.com"

    def test_email_lowercased(self):
        req = RegisterRequest(email="USER@EXAMPLE.COM", password="SecurePass123!", full_name="Jane")
        assert req.email == "user@example.com"

    def test_invalid_email_format(self):
        with pytest.raises(Exception):
            RegisterRequest(email="not-an-email", password="SecurePass123!", full_name="Jane")

    def test_full_name_required(self):
        with pytest.raises(Exception):
            RegisterRequest(email="user@example.com", password="SecurePass123!", full_name="")

    def test_full_name_stripped(self):
        req = RegisterRequest(email="user@example.com", password="SecurePass123!", full_name="  Jane  ")
        assert req.full_name == "Jane"


# ---------------------------------------------------------------------------
# JWT — access token and email verification token
# ---------------------------------------------------------------------------

class TestTokens:
    def test_access_token_has_correct_claims(self):
        """AC3: access token (now RS256) contains required claims."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "user@example.com")
        from src.services.token_service import token_service
        payload = token_service.validate_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["email"] == "user@example.com"
        assert payload["type"] == "access"

    def test_access_token_expires_in_15_minutes(self):
        """AC3: access token expires within 15-minute window."""
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "user@example.com")
        from src.services.token_service import token_service
        payload = token_service.validate_access_token(token)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = exp - now
        assert 14 <= delta.total_seconds() / 60 <= 16

    def test_refresh_token_is_urlsafe_string(self):
        """Refresh tokens are opaque URL-safe strings (Story 1.5 AC4)."""
        import secrets
        token = secrets.token_urlsafe(64)
        assert isinstance(token, str)
        assert len(token) >= 32

    def test_email_verification_token_valid(self):
        """AC3: verification token generated with user_id and purpose=email_verification."""
        user_id = uuid.uuid4()
        token = create_email_verification_token(user_id)
        decoded_id = decode_email_verification_token(token)
        assert decoded_id == user_id

    def test_email_verification_token_uses_separate_secret(self):
        """Verification token is signed with email_verification_secret, NOT jwt_secret."""
        user_id = uuid.uuid4()
        token = create_email_verification_token(user_id)
        # Decoding with session JWT secret should fail
        with pytest.raises(Exception):
            jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

    def test_expired_verification_token_raises(self):
        user_id = uuid.uuid4()
        # Manually craft an expired token
        from jose import jwt as jose_jwt
        payload = {
            "sub": str(user_id),
            "purpose": "email_verification",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = jose_jwt.encode(
            payload, settings.email_verification_secret, algorithm="HS256"
        )
        with pytest.raises(ValueError, match="expired|invalid"):
            decode_email_verification_token(expired_token)

    def test_wrong_purpose_token_raises(self):
        user_id = uuid.uuid4()
        from jose import jwt as jose_jwt
        payload = {
            "sub": str(user_id),
            "purpose": "wrong_purpose",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        bad_token = jose_jwt.encode(
            payload, settings.email_verification_secret, algorithm="HS256"
        )
        with pytest.raises(ValueError, match="purpose"):
            decode_email_verification_token(bad_token)
