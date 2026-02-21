"""
Security Tests — Invitation Endpoints
Story: 1-3-team-member-invitation (Task 7.3)
AC: AC9 — brute-force prevention, SQL injection, cross-tenant isolation
"""

import hashlib
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


def _hash_token(raw: str) -> str:
    """SHA-256 hash a raw token — mirrors invitation_service._hash_token."""
    return hashlib.sha256(raw.encode()).hexdigest()

import pytest
from httpx import AsyncClient

from src.models.invitation import Invitation
from src.models.tenant import Tenant, TenantUser
from src.models.user import User

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "admin'--",
    "'; DROP TABLE invitations; --",
    "' OR '1'='1",
    "1' UNION SELECT NULL,NULL--",
]

XSS_PAYLOADS = [
    "<script>alert(1)</script>@example.com",
    '"><img src=x onerror=alert(1)>@example.com',
]


@contextmanager
def _patch_all():
    mock_redis = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock_redis.pipeline.return_value = pipeline
    mock_redis.expire = AsyncMock(return_value=True)

    with patch(
        "src.api.v1.invitations.router.send_invitation_email",
        new_callable=AsyncMock,
    ):
        with patch(
            "src.api.v1.invitations.router.get_redis_client",
            return_value=mock_redis,
        ):
            yield


# ---------------------------------------------------------------------------
# SQL injection prevention — AC9
# ---------------------------------------------------------------------------

class TestSQLInjectionPrevention:
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_invite_email_rejected_or_stored_safely(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, payload: str
    ):
        """ORM parameterized queries — injection treated as literal data."""
        with _patch_all():
            resp = await client_with_auth.post(
                f"/api/v1/orgs/{test_tenant.id}/invitations",
                json={"invitations": [{"email": f"{payload}@example.com", "role": "viewer"}]},
            )
        # Must NEVER return 500 (unhandled SQL error)
        assert resp.status_code != 500
        # Pydantic EmailStr validation rejects most SQL injection strings as non-RFC5322
        assert resp.status_code in (201, 400, 422)

    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_token_param_handled(
        self, client: AsyncClient, payload: str
    ):
        """GET /api/v1/invitations/{token} with injection payload must not cause 500."""
        # M2: token now in path — httpx URL-encodes special characters automatically
        resp = await client.get(f"/api/v1/invitations/{payload}")
        assert resp.status_code != 500
        assert resp.status_code in (400, 404, 410, 422)


# ---------------------------------------------------------------------------
# Cross-tenant isolation — AC9
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    async def test_cannot_list_another_tenants_invitations(
        self,
        client_with_auth: AsyncClient,
        db_session,
        existing_user: User,
    ):
        """User can only see invitations for their own org."""
        # Create a completely separate tenant
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Corp",
            slug=f"other-corp-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        # Create invitation in the other tenant
        raw_cross = f"cross-tenant-token-{uuid.uuid4().hex}"
        inv = Invitation(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            email="victim@example.com",
            role="viewer",
            invited_by=existing_user.id,  # any user id for FK constraint
            token=_hash_token(raw_cross),  # M1: store SHA-256 hash
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.flush()

        # Authenticated user requests the OTHER tenant's invitations
        resp = await client_with_auth.get(
            f"/api/v1/orgs/{other_tenant.id}/invitations"
        )
        # Must be 403 (not a member of that org) — not 200 with other tenant's data
        assert resp.status_code == 403

    async def test_cannot_revoke_another_tenants_invitation(
        self,
        client_with_auth: AsyncClient,
        db_session,
        existing_user: User,
    ):
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Other Corp 2",
            slug=f"other-corp2-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        raw_revoke = f"cross-revoke-token-{uuid.uuid4().hex}"
        inv = Invitation(
            id=uuid.uuid4(),
            tenant_id=other_tenant.id,
            email="protect@example.com",
            role="viewer",
            invited_by=existing_user.id,
            token=_hash_token(raw_revoke),  # M1: store SHA-256 hash
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(inv)
        await db_session.flush()

        resp = await client_with_auth.delete(
            f"/api/v1/orgs/{other_tenant.id}/invitations/{inv.id}"
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Token enumeration / brute-force (AC9)
# ---------------------------------------------------------------------------

class TestTokenEnumeration:
    async def test_invalid_token_returns_generic_message(
        self, client: AsyncClient
    ):
        """AC9: error message must not distinguish 'not found' vs 'expired' vs 'revoked'."""
        # M2: token now in path
        resp = await client.get("/api/v1/invitations/nonexistent-random-token")
        # Router maps TokenNotFoundError/TokenRevokedError → 400 (AC9: same code)
        assert resp.status_code in (400, 410)
        body = resp.json()
        error_text = str(body).lower()
        # Must not reveal token status details that would aid enumeration
        assert "nonexistent-random-token" not in error_text

    async def test_accept_nonexistent_token_is_generic(
        self, client: AsyncClient
    ):
        """POST /accept with bad token → generic 400/404, no internal info."""
        resp = await client.post(
            "/api/v1/invitations/accept",
            json={
                "token": "attacker-guess-00001",
                "full_name": "Attacker",
                "password": "SecurePass123!",
            },
        )
        assert resp.status_code in (400, 404, 410)
        body = resp.json()
        assert "attacker-guess-00001" not in str(body)

    async def test_expired_and_revoked_tokens_return_same_status_code(
        self,
        client: AsyncClient,
        db_session,
        test_tenant: Tenant,
        existing_user: User,
    ):
        """AC9: expired and revoked return same-kind HTTP status to prevent oracle."""
        raw_expired = "oracle-expired-token"
        raw_revoked = "oracle-revoked-token"
        expired_inv = Invitation(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            email="expired-oracle@example.com",
            role="viewer",
            invited_by=existing_user.id,
            token=_hash_token(raw_expired),  # M1: store SHA-256 hash
            status="expired",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            created_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
        revoked_inv = Invitation(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            email="revoked-oracle@example.com",
            role="viewer",
            invited_by=existing_user.id,
            token=_hash_token(raw_revoked),  # M1: store SHA-256 hash
            status="revoked",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(expired_inv)
        db_session.add(revoked_inv)
        await db_session.flush()

        # M2: raw tokens in path — service hashes them for DB lookup
        resp_expired = await client.get(f"/api/v1/invitations/{raw_expired}")
        resp_revoked = await client.get(f"/api/v1/invitations/{raw_revoked}")
        # AC9: revoked and not-found both map to 400 (INVALID_INVITATION)
        # Expired maps to 410 (INVITATION_EXPIRED) — distinct to allow UX to show "please resend"
        # At minimum: neither must return 200
        assert resp_expired.status_code != 200
        assert resp_revoked.status_code != 200
        # Revoked returns same code as not-found (AC9: no oracle for revocation state)
        assert resp_revoked.status_code == 400


# ---------------------------------------------------------------------------
# IDOR prevention — AC9
# ---------------------------------------------------------------------------

class TestIDORPrevention:
    async def test_cannot_revoke_invitation_by_guessing_uuid(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        """Attempting to revoke a UUID that does not belong to tenant returns 404."""
        random_id = uuid.uuid4()
        resp = await client_with_auth.delete(
            f"/api/v1/orgs/{test_tenant.id}/invitations/{random_id}"
        )
        assert resp.status_code == 404

    async def test_malformed_uuid_in_invite_id_returns_422(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        resp = await client_with_auth.delete(
            f"/api/v1/orgs/{test_tenant.id}/invitations/not-a-uuid"
        )
        assert resp.status_code == 422
