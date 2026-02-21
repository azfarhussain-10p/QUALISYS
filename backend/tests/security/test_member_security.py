"""
Security Tests — Member Management Endpoints
Story: 1-4-user-management-remove-change-roles (Task 7.5, Task 8)
AC: AC5 (cross-tenant isolation), AC6 (last-admin guard), AC7 (audit), AC8 (RBAC)

Tasks 8.1–8.6:
  8.1 RBAC enforcement on all management endpoints (Owner/Admin only for mutations)
  8.2 Self-action prevention server-side
  8.3 Last-admin guard atomic (FOR UPDATE verified in service)
  8.4 Removed user sessions invalidated (mocked)
  8.5 Cross-tenant isolation: cannot remove/change roles for users in other orgs
  8.6 Audit logging captures all actions including blocked attempts
"""

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant, TenantUser
from src.models.user import User

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _patch_all():
    mock_redis = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.ttl = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock_redis.pipeline.return_value = pipeline
    mock_redis.expire = AsyncMock(return_value=True)
    mock_redis.scan = AsyncMock(return_value=(0, []))
    mock_redis.delete = AsyncMock(return_value=0)

    with patch("src.api.v1.members.router.send_role_changed_email", new_callable=AsyncMock):
        with patch("src.api.v1.members.router.send_member_removed_email", new_callable=AsyncMock):
            with patch("src.api.v1.members.router.get_redis_client", return_value=mock_redis):
                with patch(
                    "src.services.user_management.user_management_service.get_redis_client",
                    return_value=mock_redis,
                ):
                    yield


async def _make_user_with_membership(
    db: AsyncSession,
    tenant: Tenant,
    role: str = "viewer",
) -> tuple[User, TenantUser, str]:
    """Create a user+membership and return (user, membership, jwt_token)."""
    from src.services.auth.auth_service import hash_password, create_access_token
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"sec_{uid.hex[:8]}@example.com",
        full_name=f"SecurityUser {uid.hex[:4]}",
        password_hash=hash_password("SecurePass123!"),
        email_verified=True,
        auth_provider="email",
    )
    db.add(user)
    await db.flush()
    membership = TenantUser(
        tenant_id=tenant.id,
        user_id=uid,
        role=role,
        is_active=True,
    )
    db.add(membership)
    await db.flush()
    token = create_access_token(uid, user.email)
    return user, membership, token


# ---------------------------------------------------------------------------
# 8.1 — RBAC enforcement (AC2, AC3)
# ---------------------------------------------------------------------------

class TestRBACEnforcement:
    @pytest.mark.parametrize("role", ["pm-csm", "qa-manual", "qa-automation", "developer", "viewer"])
    async def test_non_admin_cannot_change_role(
        self, client: AsyncClient, test_tenant: Tenant, db_session, role: str
    ):
        """Server-side RBAC: non-Owner/Admin roles are rejected for PATCH /role. AC2."""
        _, target, _ = await _make_user_with_membership(db_session, test_tenant, role="developer")
        actor, _, token = await _make_user_with_membership(db_session, test_tenant, role=role)
        with _patch_all():
            resp = await client.patch(
                f"/api/v1/orgs/{test_tenant.id}/members/{target.user_id}/role",
                json={"role": "viewer"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403, f"Role '{role}' should not be allowed to change member roles"

    @pytest.mark.parametrize("role", ["pm-csm", "qa-manual", "qa-automation", "developer", "viewer"])
    async def test_non_admin_cannot_remove_member(
        self, client: AsyncClient, test_tenant: Tenant, db_session, role: str
    ):
        """Server-side RBAC: non-Owner/Admin roles are rejected for DELETE member. AC3."""
        _, target, _ = await _make_user_with_membership(db_session, test_tenant, role="developer")
        actor, _, token = await _make_user_with_membership(db_session, test_tenant, role=role)
        with _patch_all():
            resp = await client.delete(
                f"/api/v1/orgs/{test_tenant.id}/members/{target.user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403, f"Role '{role}' should not be allowed to remove members"

    async def test_unauthenticated_request_returns_401_or_403(
        self, client: AsyncClient, test_tenant: Tenant, db_session
    ):
        """No token → 401 or 403 (never 200). AC2."""
        _, target, _ = await _make_user_with_membership(db_session, test_tenant, role="viewer")
        with _patch_all():
            resp = await client.patch(
                f"/api/v1/orgs/{test_tenant.id}/members/{target.user_id}/role",
                json={"role": "developer"},
            )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 8.2 — Self-action prevention (server-side, cannot be bypassed via UI)
# ---------------------------------------------------------------------------

class TestSelfActionPrevention:
    async def test_owner_cannot_change_own_role(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, existing_user: User
    ):
        with _patch_all():
            resp = await client_with_auth.patch(
                f"/api/v1/orgs/{test_tenant.id}/members/{existing_user.id}/role",
                json={"role": "viewer"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "SELF_ACTION_NOT_ALLOWED"

    async def test_owner_cannot_remove_self(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, existing_user: User
    ):
        with _patch_all():
            resp = await client_with_auth.delete(
                f"/api/v1/orgs/{test_tenant.id}/members/{existing_user.id}"
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "SELF_ACTION_NOT_ALLOWED"


# ---------------------------------------------------------------------------
# 8.3 — Last-admin guard (AC6)
# ---------------------------------------------------------------------------

class TestLastAdminGuard:
    async def test_single_owner_role_change_blocked_409(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, db_session, existing_user: User
    ):
        """With only one admin, any attempt by another admin to demote them → 409. AC6."""
        second_admin, _, token = await _make_user_with_membership(db_session, test_tenant, role="admin")
        with _patch_all():
            resp = await client_with_auth.patch(
                f"/api/v1/orgs/{test_tenant.id}/members/{existing_user.id}/role",
                json={"role": "viewer"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "LAST_ADMIN"

    async def test_single_owner_removal_blocked_409(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, db_session, existing_user: User
    ):
        second_admin, _, token = await _make_user_with_membership(db_session, test_tenant, role="admin")
        with _patch_all():
            resp = await client_with_auth.delete(
                f"/api/v1/orgs/{test_tenant.id}/members/{existing_user.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "LAST_ADMIN"

    async def test_two_owners_one_can_be_removed(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, db_session
    ):
        """With 2 owners, removing one succeeds (other remains). AC6."""
        second_owner, _, _ = await _make_user_with_membership(db_session, test_tenant, role="owner")
        with _patch_all():
            resp = await client_with_auth.delete(
                f"/api/v1/orgs/{test_tenant.id}/members/{second_owner.id}"
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 8.4 — Session invalidation on removal (AC5)
# ---------------------------------------------------------------------------

class TestSessionInvalidation:
    async def test_redis_scan_delete_called_on_removal(
        self, client_with_auth: AsyncClient, test_tenant: Tenant, db_session
    ):
        """_invalidate_sessions calls redis.scan + redis.delete. AC5."""
        user, _, _ = await _make_user_with_membership(db_session, test_tenant, role="viewer")

        with patch(
            "src.services.user_management.user_management_service.get_redis_client"
        ) as mock_redis_factory:
            mock_redis = MagicMock()
            mock_redis.scan = AsyncMock(return_value=(0, [b"sessions:abc"]))
            mock_redis.delete = AsyncMock(return_value=1)
            mock_redis_factory.return_value = mock_redis

            with patch("src.api.v1.members.router.send_member_removed_email", new_callable=AsyncMock):
                with patch("src.api.v1.members.router.get_redis_client") as mock_rl_router:
                    pipeline = MagicMock()
                    pipeline.incr = MagicMock(return_value=pipeline)
                    pipeline.ttl = MagicMock(return_value=pipeline)
                    pipeline.execute = AsyncMock(return_value=[1, 3600])
                    mock_rl_router.return_value = MagicMock(
                        pipeline=MagicMock(return_value=pipeline),
                        expire=AsyncMock(return_value=True),
                    )
                    resp = await client_with_auth.delete(
                        f"/api/v1/orgs/{test_tenant.id}/members/{user.id}"
                    )

        assert resp.status_code == 200
        mock_redis.scan.assert_called()
        mock_redis.delete.assert_called()


# ---------------------------------------------------------------------------
# 8.5 — Cross-tenant isolation (AC10 implied by multi-tenant arch)
# ---------------------------------------------------------------------------

class TestCrossTenantIsolation:
    async def test_cannot_change_role_in_other_org(
        self, client_with_auth: AsyncClient, db_session, existing_user: User
    ):
        """Authenticated user cannot modify members in an org they don't belong to. AC5."""
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Rival Corp",
            slug=f"rival-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        from src.services.auth.auth_service import hash_password
        victim_id = uuid.uuid4()
        victim = User(
            id=victim_id,
            email=f"victim_{victim_id.hex[:8]}@example.com",
            full_name="Victim User",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(victim)
        await db_session.flush()
        db_session.add(TenantUser(
            tenant_id=other_tenant.id,
            user_id=victim_id,
            role="viewer",
            is_active=True,
        ))
        await db_session.flush()

        with _patch_all():
            resp = await client_with_auth.patch(
                f"/api/v1/orgs/{other_tenant.id}/members/{victim.id}/role",
                json={"role": "developer"},
            )
        # existing_user is not a member of other_tenant → 403
        assert resp.status_code == 403

    async def test_cannot_remove_member_in_other_org(
        self, client_with_auth: AsyncClient, db_session
    ):
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Rival Corp 2",
            slug=f"rival2-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        from src.services.auth.auth_service import hash_password
        victim_id = uuid.uuid4()
        victim = User(
            id=victim_id,
            email=f"victim2_{victim_id.hex[:8]}@example.com",
            full_name="Victim 2",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(victim)
        await db_session.flush()
        db_session.add(TenantUser(
            tenant_id=other_tenant.id,
            user_id=victim_id,
            role="viewer",
            is_active=True,
        ))
        await db_session.flush()

        with _patch_all():
            resp = await client_with_auth.delete(
                f"/api/v1/orgs/{other_tenant.id}/members/{victim.id}"
            )
        assert resp.status_code == 403

    async def test_cannot_list_members_of_other_org(
        self, client_with_auth: AsyncClient, db_session
    ):
        other_tenant = Tenant(
            id=uuid.uuid4(),
            name="Rival Corp 3",
            slug=f"rival3-{uuid.uuid4().hex[:6]}",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(other_tenant)
        await db_session.flush()

        with _patch_all():
            resp = await client_with_auth.get(
                f"/api/v1/orgs/{other_tenant.id}/members"
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# SQL injection / malformed UUID inputs
# ---------------------------------------------------------------------------

class TestInputValidation:
    async def test_malformed_user_id_returns_422(
        self, client_with_auth: AsyncClient, test_tenant: Tenant
    ):
        """Non-UUID user_id in path → FastAPI 422 before service is called."""
        with _patch_all():
            resp = await client_with_auth.patch(
                f"/api/v1/orgs/{test_tenant.id}/members/not-a-uuid/role",
                json={"role": "viewer"},
            )
        assert resp.status_code == 422

    async def test_malformed_org_id_returns_422(
        self, client_with_auth: AsyncClient
    ):
        with _patch_all():
            resp = await client_with_auth.get(
                "/api/v1/orgs/not-a-uuid/members"
            )
        assert resp.status_code == 422
