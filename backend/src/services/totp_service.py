"""
QUALISYS — TOTP Service
Story: 1-7-two-factor-authentication-totp
AC: AC2 — TOTP secret generation (160-bit base32), QR URI format
AC: AC3 — TOTP setup confirmation with ±1 window tolerance
AC: AC5 — Login TOTP verification with ±1 window tolerance
AC: AC9 — AES-256-GCM encryption at rest (key from Secrets Manager/env)

TOTP specification (RFC 6238):
  - Algorithm: SHA1
  - Digits: 6
  - Period: 30 seconds
  - Window: ±1 period (accepts previous, current, next code)
  Compatible with: Google Authenticator, Authy, Microsoft Authenticator, 1Password

AES-256-GCM encryption:
  - 32-byte key from settings.mfa_encryption_key (base64-encoded)
  - 12-byte random nonce prepended to ciphertext
  - Storage format: bytes(12-byte nonce + GCM ciphertext + tag)
"""

import base64
import os
import secrets
from urllib.parse import quote

import pyotp
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import get_settings
from src.logger import logger

settings = get_settings()

# TOTP configuration constants (RFC 6238)
_TOTP_ISSUER = "QUALISYS"
_TOTP_ALGORITHM = "SHA1"
_TOTP_DIGITS = 6
_TOTP_PERIOD = 30
_TOTP_WINDOW = 1  # ±1 period tolerance (accepts -30s, 0, +30s)

# AES-256-GCM nonce size (96 bits)
_NONCE_SIZE = 12


# ---------------------------------------------------------------------------
# Encryption key — lazy-loaded, base64 decoded from settings
# ---------------------------------------------------------------------------

_encryption_key: bytes | None = None


def _get_encryption_key() -> bytes:
    """
    Load AES-256 key from settings (base64-encoded 32 bytes).
    In production this is sourced from AWS Secrets Manager / Azure Key Vault.
    Raises ValueError if key is invalid.
    """
    global _encryption_key
    if _encryption_key is not None:
        return _encryption_key

    try:
        key = base64.b64decode(settings.mfa_encryption_key)
        if len(key) != 32:
            raise ValueError(f"MFA encryption key must be 32 bytes; got {len(key)}")
        _encryption_key = key
        return _encryption_key
    except Exception as exc:
        raise ValueError(f"Invalid MFA encryption key: {exc}") from exc


# ---------------------------------------------------------------------------
# Secret generation (AC2)
# ---------------------------------------------------------------------------

def generate_secret() -> str:
    """
    Generate a cryptographically random 160-bit TOTP secret (RFC 6238).
    Returns a base32-encoded string compatible with all authenticator apps.
    pyotp.random_base32() generates 160 bits (32 base32 chars).
    """
    return pyotp.random_base32()


# ---------------------------------------------------------------------------
# QR code URI (AC2)
# ---------------------------------------------------------------------------

def generate_qr_uri(secret: str, email: str) -> str:
    """
    Generate the otpauth:// URI for QR code display.

    Format (Google Authenticator Key URI):
      otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}&algorithm={alg}&digits={d}&period={p}

    Note: We do NOT render the QR image here — caller is responsible for
    converting URI to SVG/PNG via qrcode library (no external API call).
    """
    label = quote(f"{_TOTP_ISSUER}:{email}", safe="@:")
    params = (
        f"secret={secret}"
        f"&issuer={_TOTP_ISSUER}"
        f"&algorithm={_TOTP_ALGORITHM}"
        f"&digits={_TOTP_DIGITS}"
        f"&period={_TOTP_PERIOD}"
    )
    return f"otpauth://totp/{label}?{params}"


# ---------------------------------------------------------------------------
# TOTP verification (AC3, AC5)
# ---------------------------------------------------------------------------

def verify_totp_code(secret: str, code: str) -> bool:
    """
    Verify a 6-digit TOTP code against the plaintext base32 secret.
    Uses ±1 window tolerance for clock drift (accepts ±30 seconds).

    Args:
        secret: Plaintext base32-encoded TOTP secret (NOT encrypted)
        code:   6-digit code from the authenticator app

    Returns:
        True if valid; False otherwise
    """
    if not code or not code.isdigit() or len(code) != _TOTP_DIGITS:
        return False
    try:
        totp = pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_PERIOD)
        return totp.verify(code, valid_window=_TOTP_WINDOW)
    except Exception as exc:
        logger.warning("TOTP verification error", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Secret encryption / decryption (AC9 — C1: AES-256 at rest)
# ---------------------------------------------------------------------------

def encrypt_secret(secret: str) -> bytes:
    """
    Encrypt a plaintext TOTP secret with AES-256-GCM.

    Returns bytes: 12-byte nonce || GCM ciphertext+tag
    Nonce is randomly generated per encryption — never reused.
    """
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, secret.encode("utf-8"), None)
    return nonce + ciphertext


def decrypt_secret(encrypted: bytes) -> str:
    """
    Decrypt AES-256-GCM encrypted TOTP secret.

    Args:
        encrypted: bytes from encrypt_secret() — nonce || ciphertext

    Returns:
        Plaintext base32-encoded TOTP secret

    Raises:
        ValueError: if decryption fails (invalid ciphertext, wrong key, tampered data)
    """
    if len(encrypted) <= _NONCE_SIZE:
        raise ValueError("Invalid encrypted secret: too short")
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = encrypted[:_NONCE_SIZE]
    ciphertext = encrypted[_NONCE_SIZE:]
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Failed to decrypt TOTP secret: {exc}") from exc
