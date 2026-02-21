"""
QUALISYS — TokenService
Story: 1-5-login-session-management
ACs: AC3 (RS256 JWT access tokens), AC4 (refresh rotation + reuse detection),
     AC5 (per-tenant session storage), AC6 (multi-org session switch)

Handles:
  - create_access_token()        — RS256 JWT, 15-min expiry (AC3)
  - create_refresh_token()       — opaque token, Redis-stored (AC4, AC5)
  - validate_access_token()      — decode + verify RS256 JWT
  - validate_refresh_token()     — Redis lookup (non-consuming)
  - rotate_refresh_token()       — single-use rotation; reuse → revoke all (AC4)
  - invalidate_refresh_token()   — logout single session
  - invalidate_all_user_tokens() — logout-all sessions
  - list_user_sessions()         — session list for GET /sessions

Redis key schema (compatible with Story 1.4 _invalidate_sessions scan pattern):
  sessions:{user_id}:{tenant_key}:{token_hash}  → JSON session metadata  (TTL = expiry)
  refresh_map:{token_hash}                       → "{user_id}:{tenant_key}"  (TTL = expiry)
  revoke_map:{token_hash}                        → "{user_id}"  (TTL = 24h, reuse detection)
  user_sessions:{user_id}                        → SET of "{tenant_key}:{token_hash}"

tenant_key is str(tenant_id) for org-scoped sessions, or "none" for pre-org-selection.
"""

import hashlib
import json
import secrets
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from src.config import get_settings
from src.logger import logger

settings = get_settings()


# ---------------------------------------------------------------------------
# RS256 key pair — loaded once at module import
# ---------------------------------------------------------------------------

def _load_or_generate_rsa_keys() -> tuple[str, str]:
    """
    Load RSA key pair from settings or auto-generate for development.
    Returns (private_key_pem, public_key_pem).

    Production: set JWT_PRIVATE_KEY_PEM and JWT_PUBLIC_KEY_PEM env vars
                (or populate via AWS Secrets Manager at container startup).
    Development: 2048-bit key pair is generated in-memory at startup.
                 Not suitable for multi-instance deployments.
    """
    if settings.jwt_private_key_pem and settings.jwt_public_key_pem:
        return settings.jwt_private_key_pem, settings.jwt_public_key_pem

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    warnings.warn(
        "RS256 key pair auto-generated for development. "
        "Set JWT_PRIVATE_KEY_PEM / JWT_PUBLIC_KEY_PEM environment variables in production.",
        UserWarning,
        stacklevel=2,
    )
    return private_pem, public_pem


_JWT_PRIVATE_KEY, _JWT_PUBLIC_KEY = _load_or_generate_rsa_keys()


def get_public_key_pem() -> str:
    """Return the RS256 public key PEM (used by JWKS endpoint)."""
    return _JWT_PUBLIC_KEY


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _token_hash(raw_token: str) -> str:
    """SHA-256 of the raw refresh token → 64 lowercase hex chars."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _tenant_key(tenant_id: Optional[uuid.UUID]) -> str:
    """
    Convert tenant_id to the Redis key segment.
    'none' for pre-org-selection (tenant_id is None).
    """
    return "none" if tenant_id is None else str(tenant_id)


# ---------------------------------------------------------------------------
# TokenService
# ---------------------------------------------------------------------------

class TokenService:
    """
    Stateless service — all async methods accept the Redis client via
    src.cache.get_redis_client() (imported lazily to avoid circular imports).
    """

    # ------------------------------------------------------------------
    # Access tokens — RS256 JWT (AC3)
    # ------------------------------------------------------------------

    def create_access_token(
        self,
        user_id: uuid.UUID,
        email: str,
        tenant_id: Optional[uuid.UUID],
        role: Optional[str],
        tenant_slug: Optional[str] = None,
    ) -> str:
        """
        Issue a short-lived RS256 JWT access token (15 min).

        Claims:
          sub          — user UUID
          email        — user email
          tenant_id    — active tenant UUID or null (pre-selection)
          tenant_slug  — tenant slug (used by middleware for search_path without DB lookup)
          role         — user role within tenant or null
          exp/iat      — UNIX timestamps
          jti          — unique token ID
          type         — "access"
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "email": email,
            "tenant_id": str(tenant_id) if tenant_id is not None else None,
            "tenant_slug": tenant_slug,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
        return jwt.encode(payload, _JWT_PRIVATE_KEY, algorithm="RS256")

    def validate_access_token(self, token: str) -> dict:
        """
        Decode and validate an RS256 JWT access token.
        Returns the full claims payload.
        Raises jose.JWTError on invalid signature, expiry, or malformed token.
        """
        return jwt.decode(token, _JWT_PUBLIC_KEY, algorithms=["RS256"])

    # ------------------------------------------------------------------
    # Refresh tokens — opaque, Redis-backed (AC4, AC5)
    # ------------------------------------------------------------------

    async def create_refresh_token(
        self,
        user_id: uuid.UUID,
        tenant_id: Optional[uuid.UUID],
        session_info: dict,
        remember_me: bool = False,
    ) -> str:
        """
        Issue an opaque 64-byte refresh token and persist the session in Redis.

        session_info dict may include: ip, user_agent, device_name.

        Redis writes (all with matching TTL):
          sessions:{user_id}:{tenant_key}:{token_hash}  → JSON metadata
          refresh_map:{token_hash}                       → "user_id:tenant_key"
          user_sessions:{user_id} (SET)                  ADD "tenant_key:token_hash"
        """
        from src.cache import get_redis_client

        raw = secrets.token_urlsafe(64)
        thash = _token_hash(raw)
        tenant_key = _tenant_key(tenant_id)

        expiry_days = (
            settings.jwt_refresh_token_expire_days_remember_me
            if remember_me
            else settings.jwt_refresh_token_expire_days
        )
        ttl = expiry_days * 86400

        session_data = {
            "user_id": str(user_id),
            "tenant_id": str(tenant_id) if tenant_id is not None else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "remember_me": remember_me,
            "ip": session_info.get("ip"),
            "user_agent": session_info.get("user_agent"),
            "device_name": session_info.get("device_name"),
        }

        primary_key = f"sessions:{user_id}:{tenant_key}:{thash}"
        lookup_key = f"refresh_map:{thash}"
        user_sessions_key = f"user_sessions:{user_id}"

        redis = get_redis_client()
        pipe = redis.pipeline()
        pipe.set(primary_key, json.dumps(session_data), ex=ttl)
        pipe.set(lookup_key, f"{user_id}:{tenant_key}", ex=ttl)
        pipe.sadd(user_sessions_key, f"{tenant_key}:{thash}")
        pipe.expire(user_sessions_key, ttl)
        await pipe.execute()

        return raw

    async def validate_refresh_token(
        self,
        raw_token: str,
    ) -> tuple[uuid.UUID, Optional[uuid.UUID], dict]:
        """
        Look up a refresh token in Redis without consuming it.

        Returns (user_id, tenant_id, session_data).
        Raises ValueError if not found or expired.
        """
        from src.cache import get_redis_client

        thash = _token_hash(raw_token)
        lookup_key = f"refresh_map:{thash}"

        redis = get_redis_client()
        mapping = await redis.get(lookup_key)
        if mapping is None:
            raise ValueError("Refresh token not found or expired.")

        mapping_str = mapping.decode() if isinstance(mapping, bytes) else mapping
        user_id_str, tenant_key = mapping_str.split(":", 1)
        user_id = uuid.UUID(user_id_str)
        tenant_id = None if tenant_key == "none" else uuid.UUID(tenant_key)

        primary_key = f"sessions:{user_id}:{tenant_key}:{thash}"
        session_json = await redis.get(primary_key)
        if session_json is None:
            raise ValueError("Session metadata not found.")

        session_data = json.loads(session_json)
        return user_id, tenant_id, session_data

    async def rotate_refresh_token(
        self,
        old_raw_token: str,
        session_info: dict,
    ) -> tuple[str, uuid.UUID, Optional[uuid.UUID], dict]:
        """
        Single-use rotation with reuse detection (AC4).

        Algorithm:
          1. GETDEL refresh_map:{token_hash} — atomic claim (prevents concurrent reuse)
          2. If nil → check revoke_map tombstone:
               - Found: token was already rotated → THEFT DETECTED → revoke all + raise
               - Not found: token naturally expired → raise
          3. Delete old primary session key + user_sessions member
          4. Write revoke_map tombstone (24h TTL) to catch any late reuse attempt
          5. Issue new refresh token

        Returns (new_raw_token, user_id, tenant_id, old_session_data).
        Raises ValueError("REFRESH_TOKEN_REUSE") if reuse detected.
        Raises ValueError on expired/invalid token.
        """
        from src.cache import get_redis_client

        thash = _token_hash(old_raw_token)
        lookup_key = f"refresh_map:{thash}"
        revoke_key = f"revoke_map:{thash}"

        redis = get_redis_client()

        # Atomic get-and-delete — only one concurrent caller wins
        mapping = await redis.getdel(lookup_key)

        if mapping is None:
            # Token not found — check if it was recently rotated
            user_id_bytes = await redis.get(revoke_key)
            if user_id_bytes is not None:
                user_id_str = (
                    user_id_bytes.decode()
                    if isinstance(user_id_bytes, bytes)
                    else user_id_bytes
                )
                user_id = uuid.UUID(user_id_str)
                await self.invalidate_all_user_tokens(user_id)
                logger.warning(
                    "Refresh token reuse detected — all sessions revoked (possible token theft)",
                    user_id=str(user_id),
                    token_hash_prefix=thash[:8],
                )
                raise ValueError("REFRESH_TOKEN_REUSE")
            raise ValueError("Refresh token expired or invalid.")

        # Parse "user_id:tenant_key"
        mapping_str = mapping.decode() if isinstance(mapping, bytes) else mapping
        user_id_str, tenant_key = mapping_str.split(":", 1)
        user_id = uuid.UUID(user_id_str)
        tenant_id = None if tenant_key == "none" else uuid.UUID(tenant_key)

        # Fetch session metadata before deleting the primary key
        primary_key = f"sessions:{user_id}:{tenant_key}:{thash}"
        session_json = await redis.get(primary_key)
        session_data = json.loads(session_json) if session_json else {}
        remember_me = session_data.get("remember_me", False)

        # Write revoke tombstone + clean up old session atomically
        user_sessions_key = f"user_sessions:{user_id}"
        pipe = redis.pipeline()
        pipe.set(revoke_key, str(user_id), ex=86400)          # 24h tombstone
        pipe.delete(primary_key)
        pipe.srem(user_sessions_key, f"{tenant_key}:{thash}")
        await pipe.execute()

        # Issue new refresh token
        new_raw = await self.create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id,
            session_info=session_info,
            remember_me=remember_me,
        )

        return new_raw, user_id, tenant_id, session_data

    async def invalidate_refresh_token(self, raw_token: str) -> bool:
        """
        Revoke a single session (logout current device).
        Returns True if the token was found and deleted, False if already expired.
        """
        from src.cache import get_redis_client

        thash = _token_hash(raw_token)
        lookup_key = f"refresh_map:{thash}"

        redis = get_redis_client()
        mapping = await redis.getdel(lookup_key)
        if mapping is None:
            return False

        mapping_str = mapping.decode() if isinstance(mapping, bytes) else mapping
        user_id_str, tenant_key = mapping_str.split(":", 1)
        user_id = uuid.UUID(user_id_str)

        primary_key = f"sessions:{user_id}:{tenant_key}:{thash}"
        user_sessions_key = f"user_sessions:{user_id}"
        pipe = redis.pipeline()
        pipe.delete(primary_key)
        pipe.srem(user_sessions_key, f"{tenant_key}:{thash}")
        await pipe.execute()

        return True

    async def invalidate_all_user_tokens(self, user_id: uuid.UUID) -> int:
        """
        Revoke all sessions for a user across all tenants (logout-all / theft recovery).
        Returns count of sessions deleted.
        """
        from src.cache import get_redis_client

        redis = get_redis_client()
        user_sessions_key = f"user_sessions:{user_id}"
        members = await redis.smembers(user_sessions_key)
        if not members:
            return 0

        deleted = 0
        pipe = redis.pipeline()
        for member in members:
            member_str = member.decode() if isinstance(member, bytes) else member
            # member format: "tenant_key:token_hash"
            idx = member_str.index(":")
            tenant_key = member_str[:idx]
            thash = member_str[idx + 1:]
            pipe.delete(f"sessions:{user_id}:{tenant_key}:{thash}")
            pipe.delete(f"refresh_map:{thash}")
            deleted += 1

        pipe.delete(user_sessions_key)
        await pipe.execute()

        logger.info(
            "All user sessions invalidated",
            user_id=str(user_id),
            sessions_deleted=deleted,
        )
        return deleted

    async def list_user_sessions(
        self,
        user_id: uuid.UUID,
        current_token_hash: Optional[str] = None,
    ) -> list[dict]:
        """
        Return metadata for all active sessions (for GET /sessions endpoint).
        Each entry includes session_id (safe prefix), is_current flag, and
        ip/user_agent/device_name/created_at from stored metadata.

        Stale members (primary key expired) are pruned from the SET.
        """
        from src.cache import get_redis_client

        redis = get_redis_client()
        user_sessions_key = f"user_sessions:{user_id}"
        members = await redis.smembers(user_sessions_key)

        sessions: list[dict] = []
        stale: list[bytes] = []

        for member in members:
            member_str = member.decode() if isinstance(member, bytes) else member
            idx = member_str.index(":")
            tenant_key = member_str[:idx]
            thash = member_str[idx + 1:]
            primary_key = f"sessions:{user_id}:{tenant_key}:{thash}"
            session_json = await redis.get(primary_key)
            if session_json is None:
                stale.append(member)
                continue
            session_data = json.loads(session_json)
            session_data["session_id"] = thash[:16]  # Client-safe identifier
            session_data["is_current"] = (
                current_token_hash is not None and thash == current_token_hash
            )
            sessions.append(session_data)

        if stale:
            await redis.srem(user_sessions_key, *stale)

        return sessions


# ---------------------------------------------------------------------------
# Module-level singleton — import as `from src.services.token_service import token_service`
# ---------------------------------------------------------------------------
token_service = TokenService()
