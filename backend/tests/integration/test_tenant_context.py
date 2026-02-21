"""
Integration Tests — TenantContextMiddleware + RBAC
Story: 1-2-organization-creation-setup (Task 7.4)
AC: AC8 — middleware sets ContextVar, RBAC enforced at endpoint level
AC: AC9 — role-based access control prevents unauthorized access
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant import Tenant, TenantUser
from src.models.user import User
from src.services.auth.auth_service import create_access_token

pytestmark = pytest.mark.asyncio


class TestTenantContextMiddleware:
    async def test_public_paths_bypass_jwt_check(self, client: AsyncClient):
        """Middleware skips /api/v1/auth/* — no auth required."""
        response = await client.get("/health")
        assert response.status_code in (200, 404)  # endpoint exists or not, no 401

    async def test_missing_bearer_allows_public_endpoint(self, client: AsyncClient):
        """Missing JWT on public path must not return 401."""
        response = await client.get("/docs")
        # /docs is a public path — no redirect to auth
        assert response.status_code in (200, 404)

    async def test_invalid_jwt_does_not_crash_middleware(self, client: AsyncClient):
        """Middleware swallows JWTError — endpoint dependency returns 401."""
        response = await client.get(
            "/api/v1/orgs/" + str(uuid.uuid4()) + "/settings",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert response.status_code == 401

    async def test_expired_token_returns_401(self, client: AsyncClient):
        """RBAC dependency raises 401 for expired tokens."""
        import time
        from jose import jwt
        from src.config import get_settings

        cfg = get_settings()
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "email": "x@example.com",
            "type": "access",
            "exp": int(time.time()) - 3600,  # already expired
        }
        token = jwt.encode(expired_payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)
        response = await client.get(
            "/api/v1/orgs/" + str(uuid.uuid4()) + "/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


class TestRBACRequireRole:
    async def test_owner_can_access_settings(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        """AC8/AC9: owner role passes require_role('owner', 'admin') check."""
        response = await client_with_auth.get(
            f"/api/v1/orgs/{test_tenant.id}/settings"
        )
        assert response.status_code == 200

    async def test_viewer_cannot_patch_settings(
        self,
        db_session: AsyncSession,
        client: AsyncClient,
        test_tenant: Tenant,
        existing_user: User,
    ):
        """AC9: viewer role blocked from PATCH settings (requires owner/admin)."""
        # Create a second user with viewer role
        from src.services.auth.auth_service import hash_password

        viewer = User(
            id=uuid.uuid4(),
            email=f"viewer_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Viewer User",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(viewer)
        await db_session.flush()

        viewer_membership = TenantUser(
            tenant_id=test_tenant.id,
            user_id=viewer.id,
            role="viewer",
        )
        db_session.add(viewer_membership)
        await db_session.flush()

        viewer_token = create_access_token(viewer.id, viewer.email)
        response = await client.patch(
            f"/api/v1/orgs/{test_tenant.id}/settings",
            json={"name": "Hacked"},
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    async def test_non_member_gets_403_forbidden(
        self,
        db_session: AsyncSession,
        client: AsyncClient,
        test_tenant: Tenant,
    ):
        """AC9: authenticated user who is NOT a member gets 403 FORBIDDEN."""
        from src.services.auth.auth_service import hash_password

        outsider = User(
            id=uuid.uuid4(),
            email=f"outsider_{uuid.uuid4().hex[:6]}@example.com",
            full_name="Outsider",
            password_hash=hash_password("SecurePass123!"),
            email_verified=True,
            auth_provider="email",
        )
        db_session.add(outsider)
        await db_session.flush()

        token = create_access_token(outsider.id, outsider.email)
        response = await client.get(
            f"/api/v1/orgs/{test_tenant.id}/settings",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
