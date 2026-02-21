"""
QUALISYS — Organization API Router
Story: 1-2-organization-creation-setup
ACs: AC1–AC9

Endpoints implemented:
  POST   /api/v1/orgs                              — Create organization (AC1,AC2,AC3,AC4,AC7,AC9)
  GET    /api/v1/orgs/{org_id}/settings            — Read org settings (AC5, Owner/Admin)
  PATCH  /api/v1/orgs/{org_id}/settings            — Update org settings (AC5, Owner/Admin)
  POST   /api/v1/orgs/{org_id}/logo/presigned-url  — S3 pre-signed upload URL (AC6, Owner/Admin)
  GET    /api/v1/orgs/{org_id}/provisioning-status — Check schema provisioning status (AC3)
"""

import json
import re
import unicodedata
import uuid
from datetime import timedelta
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.orgs.schemas import (
    CreateOrgRequest,
    CreateOrgResponse,
    OrgResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    UpdateOrgSettingsRequest,
)
from src.cache import get_redis_client
from src.config import get_settings
from src.db import get_db
from src.logger import logger
from src.middleware.rate_limit import check_rate_limit
from src.middleware.rbac import get_current_user, require_role
from src.models.tenant import Tenant, TenantUser
from src.models.user import User
from src.services.tenant_provisioning import (
    ProvisioningStatus,
    TenantProvisioningService,
    slug_to_schema_name,
)

settings = get_settings()
router = APIRouter(prefix="/api/v1/orgs", tags=["organizations"])
_provisioning_svc = TenantProvisioningService()


def _correlation_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Slug generation helpers (AC1, AC7)
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """
    Generate a URL-safe slug from org name.
    Steps:
      1. Unicode normalize → ASCII
      2. Lowercase
      3. Replace non-alphanumeric/space runs with hyphen
      4. Strip leading/trailing hyphens
      5. Truncate to 50 chars
    """
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    return name[:50]


async def _unique_slug(base: str, db: AsyncSession) -> str:
    """
    Ensure slug uniqueness with incrementing suffix (AC7).
    Checks LOWER(slug) in public.tenants for case-insensitive collision.
    Returns the first available slug: base, base-1, base-2, ...
    """
    candidate = base
    counter = 0
    while True:
        stmt = select(Tenant).where(func.lower(Tenant.slug) == candidate.lower())
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is None:
            return candidate
        counter += 1
        # Ensure we don't exceed 50 chars after appending suffix
        suffix = f"-{counter}"
        candidate = base[:50 - len(suffix)] + suffix


# ---------------------------------------------------------------------------
# Audit log helper (AC9)
# ---------------------------------------------------------------------------

async def _audit_log(
    db: AsyncSession,
    schema_name: str,
    action: str,
    actor_id: uuid.UUID,
    actor_email: str,
    resource_type: str,
    resource_id: uuid.UUID,
    details: dict,
    ip_address: Optional[str] = None,
) -> None:
    """
    Insert an audit log entry into the tenant schema's audit_logs table.
    Non-blocking: called as a background task from endpoints.
    """
    from sqlalchemy import text
    try:
        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".audit_logs '
                "(action, actor_id, actor_email, resource_type, resource_id, details, ip_address) "
                "VALUES (:action, :actor_id, :actor_email, :resource_type, :resource_id, "
                "        :details::jsonb, :ip_address)"
            ),
            {
                "action": action,
                "actor_id": str(actor_id),
                "actor_email": actor_email,
                "resource_type": resource_type,
                "resource_id": str(resource_id),
                "details": json.dumps(details, default=str),
                "ip_address": ip_address,
            },
        )
        await db.commit()
    except Exception as exc:
        # Non-critical — log but don't fail the request
        logger.error("Audit log write failed", error=str(exc), action=action)


# ---------------------------------------------------------------------------
# POST /api/v1/orgs — AC1, AC2, AC3, AC4, AC7, AC9
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=CreateOrgResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        409: {"description": "Slug already taken"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_org(
    payload: CreateOrgRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateOrgResponse:
    """
    Create a new organization.

    - Validates name (3-100 chars) and optional slug format (AC1)
    - Auto-generates slug from name if not provided (AC7)
    - Prevents duplicate slugs (case-insensitive) with auto-increment (AC7)
    - Creates public.tenants record (AC2)
    - Assigns owner role in public.tenants_users (AC4)
    - Sets public.users.default_tenant_id (AC4)
    - Triggers async schema provisioning (AC3)
    - Audit logs org.created in tenant schema (AC9)
    - Rate limited: 3 org creations per user per hour (AC9)
    """
    correlation_id = _correlation_id(request)

    # AC9: rate limit — 3 org creations per user per hour (keyed by user_id)
    redis = get_redis_client()
    rate_key = f"rate:org_create:{current_user.id}"
    pipe = redis.pipeline()
    pipe.incr(rate_key)
    pipe.ttl(rate_key)
    results = await pipe.execute()
    count, ttl = results[0], results[1]
    if count == 1:
        await redis.expire(rate_key, 3600)
    if count > 3:
        retry_after = max(ttl, 1)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many organization creation requests. Try again later.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Determine slug (AC7)
    if payload.slug:
        slug = payload.slug.lower()
    else:
        slug = _slugify(payload.name)
        if not slug:
            slug = f"org-{uuid.uuid4().hex[:8]}"

    # AC7: ensure slug uniqueness with auto-increment
    slug = await _unique_slug(slug, db)

    # AC2: create public.tenants record
    org_id = uuid.uuid4()
    tenant = Tenant(
        id=org_id,
        name=payload.name,
        slug=slug,
        logo_url=payload.logo_url,
        custom_domain=payload.custom_domain,
        created_by=current_user.id,
    )
    db.add(tenant)
    await db.flush()  # get DB-assigned defaults (created_at etc.) without full commit

    # AC4: assign owner role in public.tenants_users
    membership = TenantUser(
        tenant_id=org_id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(membership)

    # AC4: set user's default_tenant_id
    current_user.default_tenant_id = org_id

    await db.commit()
    await db.refresh(tenant)

    schema_name = tenant.schema_name

    logger.info(
        "Organization created",
        org_id=str(org_id),
        slug=slug,
        schema=schema_name,
        user_id=str(current_user.id),
        correlation_id=correlation_id,
    )

    # AC3: async schema provisioning (non-blocking)
    provisioning_status = ProvisioningStatus.PENDING

    async def _provision():
        from sqlalchemy.ext.asyncio import AsyncSession as _Session
        from src.db import AsyncSessionLocal
        async with AsyncSessionLocal() as pdb:
            try:
                await _provisioning_svc.provision_tenant(
                    tenant_id=org_id,
                    slug=slug,
                    db=pdb,
                    correlation_id=correlation_id,
                )
                # Audit log: org.created (AC9)
                await _audit_log(
                    db=pdb,
                    schema_name=schema_name,
                    action="org.created",
                    actor_id=current_user.id,
                    actor_email=current_user.email,
                    resource_type="organization",
                    resource_id=org_id,
                    details={"org_name": payload.name, "slug": slug},
                    ip_address=request.client.host if request.client else None,
                )
            except Exception as exc:
                logger.error(
                    "Async provisioning failed",
                    org_id=str(org_id),
                    error=str(exc),
                    correlation_id=correlation_id,
                )

    background_tasks.add_task(_provision)

    return CreateOrgResponse(
        org=OrgResponse.model_validate(tenant),
        schema_name=schema_name,
        provisioning_status=provisioning_status.value,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/settings — AC5 (Owner/Admin only)
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/settings",
    response_model=OrgResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role"},
        404: {"description": "Organization not found"},
    },
)
async def get_org_settings(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """
    Retrieve organization settings. Accessible to Owner and Admin roles only.
    AC5: RBAC enforced via require_role dependency.
    """
    user, membership = auth

    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # Add provisioning status
    prov_status = await _provisioning_svc.get_provisioning_status(tenant.slug, db)
    response = OrgResponse.model_validate(tenant)
    response.provisioning_status = prov_status.value
    return response


# ---------------------------------------------------------------------------
# PATCH /api/v1/orgs/{org_id}/settings — AC5 (Owner/Admin only)
# ---------------------------------------------------------------------------

@router.patch(
    "/{org_id}/settings",
    response_model=OrgResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role"},
        404: {"description": "Organization not found"},
        409: {"description": "Slug already taken"},
    },
)
async def update_org_settings(
    org_id: uuid.UUID,
    payload: UpdateOrgSettingsRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """
    Update organization settings. Owner/Admin only.
    AC5: Slug change triggers uniqueness re-check.
    AC9: Audit log for org.settings_updated.
    """
    user, membership = auth
    correlation_id = _correlation_id(request)

    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    changes: dict = {}

    if payload.name is not None:
        tenant.name = payload.name
        changes["name"] = payload.name

    if payload.slug is not None and payload.slug != tenant.slug:
        # AC5: validate new slug uniqueness (case-insensitive)
        stmt = select(Tenant).where(
            func.lower(Tenant.slug) == payload.slug.lower(),
            Tenant.id != org_id,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "SLUG_TAKEN",
                        "message": "This organization URL is already taken. Please choose a different name.",
                    }
                },
            )
        old_slug = tenant.slug
        tenant.slug = payload.slug
        changes["slug"] = {"from": old_slug, "to": payload.slug}

    if payload.logo_url is not None:
        tenant.logo_url = payload.logo_url
        changes["logo_url"] = payload.logo_url

    if payload.custom_domain is not None:
        tenant.custom_domain = payload.custom_domain
        changes["custom_domain"] = payload.custom_domain

    if payload.data_retention_days is not None:
        tenant.data_retention_days = payload.data_retention_days
        changes["data_retention_days"] = payload.data_retention_days

    if payload.settings is not None:
        # Merge JSONB settings (don't overwrite keys not in payload)
        merged = {**tenant.settings, **payload.settings}
        tenant.settings = merged
        changes["settings"] = "updated"

    await db.commit()
    await db.refresh(tenant)

    logger.info(
        "Org settings updated",
        org_id=str(org_id),
        changes=list(changes.keys()),
        user_id=str(user.id),
        correlation_id=correlation_id,
    )

    # AC9: audit log (background — non-blocking)
    # Must use a new AsyncSessionLocal: the request db session is closed after the response.
    schema_name = tenant.schema_name
    _actor_id = user.id
    _actor_email = user.email
    _ip = request.client.host if request.client else None

    async def _settings_audit() -> None:
        from src.db import AsyncSessionLocal
        async with AsyncSessionLocal() as audit_db:
            await _audit_log(
                db=audit_db,
                schema_name=schema_name,
                action="org.settings_updated",
                actor_id=_actor_id,
                actor_email=_actor_email,
                resource_type="organization",
                resource_id=org_id,
                details=changes,
                ip_address=_ip,
            )

    background_tasks.add_task(_settings_audit)

    return OrgResponse.model_validate(tenant)


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/logo/presigned-url — AC6 (Owner/Admin only)
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/logo/presigned-url",
    response_model=PresignedUrlResponse,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role"},
        404: {"description": "Organization not found"},
        422: {"description": "Invalid file type or size"},
        501: {"description": "S3 not configured"},
    },
)
async def get_logo_presigned_url(
    org_id: uuid.UUID,
    payload: PresignedUrlRequest,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> PresignedUrlResponse:
    """
    Generate an S3 pre-signed PUT URL for direct browser-to-S3 logo upload.
    AC6: PNG/JPG/SVG only, max 2MB. Returns {upload_url, key}.

    The client uploads directly to S3 using upload_url.
    After upload, the client calls PATCH /settings with logo_url = key.

    Thumbnail generation: Handled by S3 Lambda trigger in production.
    For development: the original is preserved at tenants/{tenant_id}/logo/{filename}.
    """
    user, membership = auth

    if not settings.s3_bucket_name:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "error": {
                    "code": "S3_NOT_CONFIGURED",
                    "message": "Object storage is not configured.",
                }
            },
        )

    # Construct S3 key (AC6)
    safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", payload.filename)
    s3_key = f"tenants/{org_id}/logo/{safe_filename}"

    try:
        s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        # Generate pre-signed PUT URL (15-minute expiry)
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.s3_bucket_name,
                "Key": s3_key,
                "ContentType": payload.content_type,
                "ContentLength": payload.file_size,
            },
            ExpiresIn=900,  # 15 minutes
        )
    except ClientError as exc:
        logger.error("S3 presigned URL generation failed", error=str(exc), org_id=str(org_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "S3_ERROR",
                    "message": "Failed to generate upload URL. Please try again.",
                }
            },
        ) from exc

    return PresignedUrlResponse(
        upload_url=upload_url,
        key=s3_key,
        expires_in_seconds=900,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/provisioning-status — AC3
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/provisioning-status",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role or not a member of this organization"},
        404: {"description": "Organization not found"},
    },
)
async def get_provisioning_status(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner", "admin"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Poll tenant schema provisioning status.
    AC3: Async provisioning with status tracking (pending → ready | failed).
    AC9: RBAC — owner/admin only (fixes IDOR: any authenticated user could poll any org).
    """
    user, membership = auth

    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    prov_status = await _provisioning_svc.get_provisioning_status(tenant.slug, db)
    return {"org_id": str(org_id), "status": prov_status.value}
