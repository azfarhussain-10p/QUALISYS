"""
QUALISYS — Org Export & Deletion API Router
Story: 1-13-data-export-org-deletion
AC: #1, #2, #3, #4, #5, #7, #8

Endpoints:
  POST   /api/v1/orgs/{org_id}/export              — Request data export (Owner only)
  GET    /api/v1/orgs/{org_id}/exports             — List export history (up to 5)
  GET    /api/v1/orgs/{org_id}/exports/{job_id}    — Check export status
  GET    /api/v1/orgs/{org_id}/exports/{job_id}/download — Redirect to presigned URL
  POST   /api/v1/orgs/{org_id}/delete              — Request org deletion (Owner only)
  GET    /api/v1/orgs/{org_id}/deletion-status     — Query deletion progress (placeholder)

RBAC: All endpoints require Owner role (not Admin — AC4.7, AC7).
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.middleware.rbac import require_role
from src.models.tenant import Tenant
from src.services.audit_service import audit_service
from src.services.export_service import export_service
from src.services.org_deletion_service import org_deletion_service
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(prefix="/api/v1/orgs", tags=["export-deletion"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class DeleteOrgRequest(BaseModel):
    """POST /orgs/{org_id}/delete — AC3"""
    org_name_confirmation: str
    totp_code: Optional[str] = None
    password: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/export/estimate — AC1
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/export/estimate",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
        404: {"description": "Organization not found"},
    },
)
async def get_export_estimate(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return row counts per table for pre-export size estimation. Owner only.
    AC1: "Estimated size shown before export (count of records per table)."
    """
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    schema_name = slug_to_schema_name(tenant.slug)
    estimate = await export_service.get_export_estimate(
        db=db, tenant_id=org_id, schema_name=schema_name
    )
    return estimate


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/export — AC2
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/export",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
        404: {"description": "Organization not found"},
        409: {"description": "Export already in progress"},
        429: {"description": "Rate limit exceeded (1 export per org per 24h)"},
    },
)
async def request_export(
    org_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Request a full organization data export. Owner only.
    Returns 202 immediately; export runs in background.
    AC2: rate limited to 1 export per org per 24 hours.
    AC8: audit log — org.export_requested.
    """
    user, membership = auth

    # Lookup tenant
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # Attempt to create export job (validates rate limit + in-progress check)
    try:
        job = await export_service.request_export(
            db=db,
            tenant_id=org_id,
            requested_by=user.id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "EXPORT_IN_PROGRESS":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "EXPORT_IN_PROGRESS",
                        "message": "An export is already in progress for this organization.",
                    }
                },
            )
        if code == "RATE_LIMIT_EXCEEDED":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Export limited to 1 per organization per 24 hours.",
                    }
                },
                headers={"Retry-After": "86400"},
            )
        raise

    schema_name = slug_to_schema_name(tenant.slug)
    job_id = uuid.UUID(job["job_id"])

    # AC8: audit log (non-blocking)
    background_tasks.add_task(
        audit_service.log_action_async,
        schema_name=schema_name,
        tenant_id=org_id,
        actor_user_id=user.id,
        action="org.export_requested",
        resource_type="organization",
        resource_id=org_id,
        details={"job_id": str(job_id)},
    )

    # Launch background export generation
    background_tasks.add_task(
        export_service.generate_export,
        job_id=job_id,
        tenant_id=org_id,
        org_slug=tenant.slug,
        schema_name=schema_name,
        requester_email=user.email,
        requester_name=getattr(user, "full_name", None) or user.email,
    )

    return job


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/exports — AC5
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/exports",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
    },
)
async def list_exports(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List up to 5 most recent export jobs for the organization. Owner only."""
    jobs = await export_service.list_exports(db=db, tenant_id=org_id, limit=5)
    return {"exports": jobs}


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/exports/{job_id} — AC2
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/exports/{job_id}",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
        404: {"description": "Export job not found"},
    },
)
async def get_export_status(
    org_id: uuid.UUID,
    job_id: uuid.UUID,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check the status of a specific export job. Owner only."""
    job = await export_service.get_export_status(db=db, tenant_id=org_id, job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Export job not found."}},
        )
    return job


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/exports/{job_id}/download — AC5
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/exports/{job_id}/download",
    responses={
        302: {"description": "Redirect to presigned S3 download URL"},
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
        404: {"description": "Export job not found or not completed"},
        503: {"description": "S3 not configured"},
    },
)
async def download_export(
    org_id: uuid.UUID,
    job_id: uuid.UUID,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Redirect to presigned S3 download URL. Owner only. URL expires in 24h."""
    job = await export_service.get_export_status(db=db, tenant_id=org_id, job_id=job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "JOB_NOT_FOUND", "message": "Export job not found."}},
        )
    if job["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "EXPORT_NOT_READY", "message": "Export has not completed yet."}},
        )
    download_url = job.get("download_url")
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": {"code": "S3_NOT_CONFIGURED", "message": "Object storage is not configured."}},
        )
    return RedirectResponse(url=download_url, status_code=302)


# ---------------------------------------------------------------------------
# POST /api/v1/orgs/{org_id}/delete — AC3, AC4
# ---------------------------------------------------------------------------

@router.post(
    "/{org_id}/delete",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "Org name does not match"},
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required / verification failed"},
        404: {"description": "Organization not found"},
    },
)
async def request_org_deletion(
    org_id: uuid.UUID,
    payload: DeleteOrgRequest,
    background_tasks: BackgroundTasks,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Initiate org deletion (Owner only). Requires multi-step confirmation:
      - org_name_confirmation: must match exact org name (case-sensitive)
      - totp_code (if MFA enabled) OR password

    Returns 202; deletion runs in background.
    AC8: org.deletion_requested is audited inside the deletion service.
    """
    user, membership = auth

    # Lookup tenant to get official org name
    result = await db.execute(select(Tenant).where(Tenant.id == org_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "ORG_NOT_FOUND", "message": "Organization not found."}},
        )

    # Verify all deletion confirmations
    try:
        await org_deletion_service.verify_deletion(
            db=db,
            org_id=org_id,
            org_name=tenant.name,
            org_name_confirmation=payload.org_name_confirmation,
            user_id=user.id,
            totp_code=payload.totp_code,
            password=payload.password,
        )
    except ValueError as exc:
        code = str(exc)
        _code_map = {
            "ORG_NAME_MISMATCH": (400, "ORG_NAME_MISMATCH", "Organization name does not match."),
            "TOTP_REQUIRED": (403, "TOTP_REQUIRED", "TOTP verification code is required."),
            "PASSWORD_REQUIRED": (403, "PASSWORD_REQUIRED", "Password verification is required."),
            "INVALID_PASSWORD": (403, "VERIFICATION_FAILED", "Verification failed. Incorrect password."),
            "INVALID_TOTP": (403, "VERIFICATION_FAILED", "Verification failed. Invalid TOTP code."),
            "MFA_NOT_SETUP": (403, "MFA_NOT_SETUP", "2FA is not set up for this account."),
            "NO_PASSWORD_SET": (403, "NO_PASSWORD_SET", "No password set. Use TOTP verification."),
        }
        http_status, err_code, message = _code_map.get(code, (403, "VERIFICATION_FAILED", "Verification failed."))
        raise HTTPException(
            status_code=http_status,
            detail={"error": {"code": err_code, "message": message}},
        )

    # Launch background deletion
    requester_name = getattr(user, "full_name", None) or user.email
    background_tasks.add_task(
        org_deletion_service.execute_deletion,
        org_id=org_id,
        deleted_by=user.id,
        deleted_by_name=requester_name,
    )

    return {
        "job_id": None,  # deletion is tracked in deletion_audit, not export_jobs
        "status": "processing",
        "message": (
            f"Organization '{tenant.name}' deletion has been initiated. "
            "All members will be notified. This process may take a few minutes."
        ),
    }


# ---------------------------------------------------------------------------
# GET /api/v1/orgs/{org_id}/deletion-status — AC4
# ---------------------------------------------------------------------------

@router.get(
    "/{org_id}/deletion-status",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Owner role required"},
    },
)
async def get_deletion_status(
    org_id: uuid.UUID,
    auth: tuple = require_role("owner"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Query deletion audit record status.
    Returns the most recent deletion record for this org (if any).
    Owner only.
    """
    result = await db.execute(
        text(
            "SELECT tenant_id, org_name, org_slug, deleted_by, member_count, details, created_at "
            "FROM public.deletion_audit "
            "WHERE tenant_id = :tid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"tid": str(org_id)},
    )
    row = result.mappings().fetchone()
    if row is None:
        return {"status": "not_found", "org_id": str(org_id)}

    return {
        "org_id": str(org_id),
        "org_name": row["org_name"],
        "org_slug": row["org_slug"],
        "deleted_by": str(row["deleted_by"]),
        "member_count": row["member_count"],
        "details": row["details"],
        "status": row["details"].get("status", "unknown"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
