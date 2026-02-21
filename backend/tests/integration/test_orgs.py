"""
Integration Tests — /api/v1/orgs
Story: 1-2-organization-creation-setup (Task 7.3)
AC: AC1 — org creation succeeds for authenticated user
AC: AC2 — public.tenants record created with correct fields
AC: AC4 — creator assigned owner role in tenants_users
AC: AC5 — GET/PATCH settings requires owner/admin (RBAC)
AC: AC6 — presigned-url endpoint returns upload_url
AC: AC7 — duplicate slug returns 409
AC: AC8 — structured error format on all error responses
"""

import uuid
from contextlib import contextmanager
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

ORG_PAYLOAD = {
    "name": "Acme Corporation",
    "slug": "acme-corp",
}


@contextmanager
def _patch_provisioning():
    """Patch tenant provisioning AND Redis — tests need neither a real PG schema DDL nor live Redis."""
    from src.services.tenant_provisioning import ProvisioningStatus

    mock_svc = MagicMock()
    mock_svc.provision_tenant = AsyncMock(return_value=ProvisioningStatus.READY)

    # Redis mock: count=1, ttl=-1 → first request, not rate-limited
    mock_redis = MagicMock()
    pipeline = MagicMock()
    pipeline.incr = MagicMock(return_value=pipeline)
    pipeline.expire = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, -1])
    mock_redis.pipeline.return_value = pipeline
    mock_redis.expire = AsyncMock(return_value=True)

    with patch("src.api.v1.orgs.router.TenantProvisioningService", return_value=mock_svc):
        with patch("src.api.v1.orgs.router.get_redis_client", return_value=mock_redis):
            yield


# ---------------------------------------------------------------------------
# POST /api/v1/orgs — creation
# ---------------------------------------------------------------------------

class TestCreateOrg:
    async def test_create_org_returns_201(self, client_with_auth: AsyncClient):
        with _patch_provisioning():
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "New Org", "slug": "new-org-x1"},
            )
        assert response.status_code == 201

    async def test_create_org_response_schema(self, client_with_auth: AsyncClient):
        with _patch_provisioning():
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "Beta Corp", "slug": "beta-corp-x1"},
            )
        data = response.json()
        assert "org" in data
        assert "schema_name" in data
        assert "provisioning_status" in data
        org = data["org"]
        assert org["name"] == "Beta Corp"
        assert org["slug"] == "beta-corp-x1"
        assert "id" in org

    async def test_create_org_auto_generates_slug(self, client_with_auth: AsyncClient):
        """AC2: slug auto-generated from name when not provided."""
        with _patch_provisioning():
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "Auto Slug Org"},
            )
        assert response.status_code == 201
        org = response.json()["org"]
        assert org["slug"]  # non-empty
        assert "auto-slug-org" in org["slug"]

    async def test_create_org_unauthenticated_returns_401(self, client: AsyncClient):
        """AC9: unauthenticated requests rejected."""
        response = await client.post("/api/v1/orgs", json=ORG_PAYLOAD)
        assert response.status_code == 401

    async def test_create_org_missing_name_returns_422(self, client_with_auth: AsyncClient):
        """AC8: validation errors use structured format."""
        response = await client_with_auth.post("/api/v1/orgs", json={})
        assert response.status_code == 422
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "VALIDATION_ERROR"

    async def test_create_org_name_too_short_returns_422(self, client_with_auth: AsyncClient):
        response = await client_with_auth.post(
            "/api/v1/orgs", json={"name": "AB"}
        )
        assert response.status_code == 422

    async def test_create_org_invalid_slug_returns_422(self, client_with_auth: AsyncClient):
        response = await client_with_auth.post(
            "/api/v1/orgs",
            json={"name": "Test Org", "slug": "-bad-slug-"},
        )
        assert response.status_code == 422

    async def test_create_org_duplicate_slug_returns_409(
        self,
        client_with_auth: AsyncClient,
        db_session: AsyncSession,
        existing_user: User,
    ):
        """AC7: duplicate slug returns 409 SLUG_TAKEN."""
        # Pre-insert a tenant with the conflicting slug
        conflict_slug = "taken-slug-99"
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Existing Org",
            slug=conflict_slug,
            data_retention_days=365,
            plan="free",
            settings={},
            created_by=existing_user.id,
        )
        db_session.add(tenant)
        await db_session.flush()

        with _patch_provisioning():
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "Any Name", "slug": conflict_slug},
            )
        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "SLUG_TAKEN"

    async def test_create_org_schema_name_uses_underscores(self, client_with_auth: AsyncClient):
        """schema_name converts hyphens to underscores (AC2)."""
        with _patch_provisioning():
            response = await client_with_auth.post(
                "/api/v1/orgs",
                json={"name": "My Dash Org", "slug": "my-dash-org"},
            )
        assert response.status_code == 201
        schema_name = response.json()["schema_name"]
        assert schema_name == "tenant_my_dash_org"


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/settings
# ---------------------------------------------------------------------------

class TestGetOrgSettings:
    async def test_get_settings_returns_200(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        """AC5: owner can retrieve settings."""
        response = await client_with_auth.get(
            f"/api/v1/orgs/{test_tenant.id}/settings"
        )
        assert response.status_code == 200

    async def test_get_settings_response_fields(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        response = await client_with_auth.get(
            f"/api/v1/orgs/{test_tenant.id}/settings"
        )
        data = response.json()
        assert data["id"] == str(test_tenant.id)
        assert data["name"] == test_tenant.name
        assert data["slug"] == test_tenant.slug
        assert "data_retention_days" in data
        assert "plan" in data

    async def test_get_settings_unauthenticated_returns_401(
        self, client: AsyncClient, test_tenant: Tenant
    ):
        response = await client.get(f"/api/v1/orgs/{test_tenant.id}/settings")
        assert response.status_code == 401

    async def test_get_settings_nonexistent_org_returns_404(
        self, client_with_auth: AsyncClient
    ):
        fake_id = uuid.uuid4()
        response = await client_with_auth.get(f"/api/v1/orgs/{fake_id}/settings")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ORG_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /api/v1/orgs/{org_id}/settings
# ---------------------------------------------------------------------------

class TestUpdateOrgSettings:
    async def test_patch_settings_returns_200(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        """AC5: owner can update settings."""
        response = await client_with_auth.patch(
            f"/api/v1/orgs/{test_tenant.id}/settings",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200

    async def test_patch_settings_updates_name(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        response = await client_with_auth.patch(
            f"/api/v1/orgs/{test_tenant.id}/settings",
            json={"name": "Brand New Name"},
        )
        assert response.json()["name"] == "Brand New Name"

    async def test_patch_invalid_retention_days_returns_422(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        """data_retention_days must be one of 30, 90, 180, 365."""
        response = await client_with_auth.patch(
            f"/api/v1/orgs/{test_tenant.id}/settings",
            json={"data_retention_days": 99},
        )
        assert response.status_code == 422

    async def test_patch_settings_non_member_returns_403(
        self,
        client_with_auth: AsyncClient,
        db_session: AsyncSession,
    ):
        """AC8: non-member gets 403 FORBIDDEN."""
        # Create a tenant that existing_user is NOT a member of
        orphan = Tenant(
            id=uuid.uuid4(),
            name="Orphan Org",
            slug="orphan-org-99",
            data_retention_days=365,
            plan="free",
            settings={},
        )
        db_session.add(orphan)
        await db_session.flush()

        response = await client_with_auth.patch(
            f"/api/v1/orgs/{orphan.id}/settings",
            json={"name": "Hack"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/logo/presigned-url — AC6
# ---------------------------------------------------------------------------

class TestLogoPresignedUrl:
    async def test_presigned_url_returns_200_with_s3_configured(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        mock_url = "https://s3.amazonaws.com/bucket/key?signature=abc"
        with patch(
            "src.api.v1.orgs.router.boto3.client",
            return_value=MagicMock(
                generate_presigned_url=MagicMock(return_value=mock_url)
            ),
        ):
            with patch(
                "src.api.v1.orgs.router.get_settings",
                return_value=MagicMock(
                    s3_bucket_name="test-bucket",
                    s3_region="us-east-1",
                    aws_access_key_id="key",
                    aws_secret_access_key="secret",
                    s3_logo_key_prefix="org-logos",
                ),
            ):
                response = await client_with_auth.post(
                    f"/api/v1/orgs/{test_tenant.id}/logo/presigned-url",
                    json={
                        "filename": "logo.png",
                        "content_type": "image/png",
                        "file_size": 1024,
                    },
                )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "key" in data

    async def test_presigned_url_unsupported_type_returns_422(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        response = await client_with_auth.post(
            f"/api/v1/orgs/{test_tenant.id}/logo/presigned-url",
            json={
                "filename": "virus.exe",
                "content_type": "application/octet-stream",
                "file_size": 1024,
            },
        )
        assert response.status_code == 422

    async def test_presigned_url_file_too_large_returns_422(
        self,
        client_with_auth: AsyncClient,
        test_tenant: Tenant,
    ):
        response = await client_with_auth.post(
            f"/api/v1/orgs/{test_tenant.id}/logo/presigned-url",
            json={
                "filename": "big.png",
                "content_type": "image/png",
                "file_size": 3 * 1024 * 1024,  # 3MB > 2MB limit
            },
        )
        assert response.status_code == 422
