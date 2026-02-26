"""
QUALISYS — Export Service
Story: 1-13-data-export-org-deletion
AC: #1, #2, #5 — async data export, S3 upload, presigned download URLs

Design:
  - request_export() — check rate limit (1/24h), create export_jobs record, launch background task
  - generate_export() — query all tenant tables, serialize JSON, ZIP, upload to S3
  - get_export_status() — return job record + optional download URL
  - list_exports() — list last 5 export jobs for tenant
  - get_download_url() — generate presigned S3 GET URL (24h expiry)

S3 path format: exports/{tenant_id}/{job_id}/{org_slug}-export-{timestamp}.zip
S3 object lifecycle: 30 days auto-expiry (set via ObjectExpiration in bucket policy; here we use
  an Expires tag on put_object for illustration — lifecycle rules are configured on the bucket).

Security:
  - Schema name looked up from tenants table (never from user input)
  - All queries use parameterized SQLAlchemy text() calls
  - Export ZIP contains only the requesting tenant's data (cross-tenant impossible)
"""

import io
import json
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.logger import logger
from src.models.tenant import Tenant, TenantUser

settings = get_settings()

# Export rate limit: 1 per org per 24 hours
_EXPORT_RATE_WINDOW_SECONDS = 86400  # 24 hours

# Tenant schema tables to include in export
_TENANT_TABLES = [
    "projects",
    "project_members",
    "audit_logs",
]

# Public schema tables (filtered by tenant_id) to include in export
_PUBLIC_TABLES_TENANT_SCOPED = [
    "tenants",          # the org record itself
    "tenants_users",    # membership records
]


class ExportService:
    """
    Handles async data export: creates background job, generates ZIP, uploads to S3.
    """

    # ------------------------------------------------------------------
    # Rate limiting (Redis-based, 1 export / org / 24h)
    # ------------------------------------------------------------------

    async def _check_export_rate_limit(self, tenant_id: uuid.UUID) -> bool:
        """
        Returns True if export is allowed, False if rate limit exceeded.
        Uses Redis SETNX pattern: key exists → blocked; set with TTL → allowed.
        """
        from src.cache import get_redis_client
        redis = get_redis_client()
        rate_key = f"rate:export:{tenant_id}"
        try:
            # SETNX with 24h TTL — if key already exists, rate limit hit
            result = await redis.set(rate_key, "1", nx=True, ex=_EXPORT_RATE_WINDOW_SECONDS)
            return result is not None  # True = key was set (allowed); None = key existed (blocked)
        except Exception as exc:
            logger.warning("Export rate limit Redis check failed (allowing)", exc=str(exc))
            return True

    # ------------------------------------------------------------------
    # Request export — AC2
    # ------------------------------------------------------------------

    async def request_export(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        requested_by: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Create an export job record and launch the background generation task.

        Returns:
            { job_id, status, estimated_duration }

        Raises:
            ValueError with code 'EXPORT_IN_PROGRESS' if a job is already processing.
            ValueError with code 'RATE_LIMIT_EXCEEDED' if 1/24h limit hit.
        """
        # Check if an export is already in progress for this tenant
        result = await db.execute(
            text(
                "SELECT id FROM public.export_jobs "
                "WHERE tenant_id = :tenant_id AND status = 'processing' "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"tenant_id": str(tenant_id)},
        )
        row = result.fetchone()
        if row is not None:
            raise ValueError("EXPORT_IN_PROGRESS")

        # Rate limit check
        allowed = await self._check_export_rate_limit(tenant_id)
        if not allowed:
            raise ValueError("RATE_LIMIT_EXCEEDED")

        # Create export_jobs record
        job_id = uuid.uuid4()
        await db.execute(
            text(
                "INSERT INTO public.export_jobs "
                "(id, tenant_id, requested_by, status, progress_percent) "
                "VALUES (:id, :tenant_id, :requested_by, 'processing', 0)"
            ),
            {
                "id": str(job_id),
                "tenant_id": str(tenant_id),
                "requested_by": str(requested_by),
            },
        )
        await db.commit()

        logger.info(
            "Export job created",
            job_id=str(job_id),
            tenant_id=str(tenant_id),
            requested_by=str(requested_by),
        )

        return {
            "job_id": str(job_id),
            "status": "processing",
            "estimated_duration": "2-5 minutes",
        }

    # ------------------------------------------------------------------
    # Generate export — AC2, AC5 (background task body)
    # ------------------------------------------------------------------

    async def generate_export(
        self,
        job_id: uuid.UUID,
        tenant_id: uuid.UUID,
        org_slug: str,
        schema_name: str,
        requester_email: str,
        requester_name: str,
    ) -> None:
        """
        Full export pipeline: query → serialize → ZIP → S3 upload → email notification.
        Updates export_jobs progress as it runs.
        Called as a BackgroundTasks callback (opens its own DB session).
        """
        from src.db import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                await self._run_export(
                    db=db,
                    job_id=job_id,
                    tenant_id=tenant_id,
                    org_slug=org_slug,
                    schema_name=schema_name,
                    requester_email=requester_email,
                    requester_name=requester_name,
                )
            except Exception as exc:
                logger.error(
                    "Export generation failed",
                    job_id=str(job_id),
                    tenant_id=str(tenant_id),
                    exc=str(exc),
                )
                # Mark job as failed
                try:
                    await db.execute(
                        text(
                            "UPDATE public.export_jobs "
                            "SET status = 'failed', error_message = :error, "
                            "completed_at = NOW() "
                            "WHERE id = :job_id"
                        ),
                        {"error": str(exc)[:500], "job_id": str(job_id)},
                    )
                    await db.commit()
                except Exception:
                    pass

    async def _run_export(
        self,
        db: AsyncSession,
        job_id: uuid.UUID,
        tenant_id: uuid.UUID,
        org_slug: str,
        schema_name: str,
        requester_email: str,
        requester_name: str,
    ) -> None:
        """Inner export logic. Updates progress in DB as it advances."""

        async def _set_progress(pct: int) -> None:
            await db.execute(
                text(
                    "UPDATE public.export_jobs SET progress_percent = :pct WHERE id = :job_id"
                ),
                {"pct": pct, "job_id": str(job_id)},
            )
            await db.commit()

        await _set_progress(5)

        # Build ZIP in memory
        zip_buffer = io.BytesIO()
        total_steps = len(_TENANT_TABLES) + len(_PUBLIC_TABLES_TENANT_SCOPED)
        step = 0

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Tenant schema tables
            for table in _TENANT_TABLES:
                try:
                    result = await db.execute(
                        text(f'SELECT * FROM "{schema_name}".{table}')  # noqa: S608
                    )
                    rows = result.mappings().fetchall()
                    data = [dict(r) for r in rows]
                    zf.writestr(
                        f"{table}.json",
                        json.dumps(data, default=_json_default, indent=2),
                    )
                except Exception as exc:
                    logger.warning(
                        "Export: could not read table",
                        table=table,
                        exc=str(exc),
                    )
                    zf.writestr(f"{table}.json", json.dumps([], indent=2))

                step += 1
                progress = 5 + int(step / total_steps * 60)
                await _set_progress(progress)

            # Public schema tables (filtered by tenant_id)
            for table in _PUBLIC_TABLES_TENANT_SCOPED:
                try:
                    result = await db.execute(
                        text(
                            f"SELECT * FROM public.{table} WHERE tenant_id = :tid"  # noqa: S608
                        ),
                        {"tid": str(tenant_id)},
                    )
                    rows = result.mappings().fetchall()
                    data = [dict(r) for r in rows]
                    zf.writestr(
                        f"public_{table}.json",
                        json.dumps(data, default=_json_default, indent=2),
                    )
                except Exception as exc:
                    logger.warning(
                        "Export: could not read public table",
                        table=table,
                        exc=str(exc),
                    )
                    zf.writestr(f"public_{table}.json", json.dumps([], indent=2))

                step += 1
                progress = 5 + int(step / total_steps * 60)
                await _set_progress(progress)

        await _set_progress(70)

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.read()
        file_size = len(zip_bytes)

        # Upload to S3
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        s3_key = f"exports/{tenant_id}/{job_id}/{org_slug}-export-{timestamp}.zip"

        if settings.s3_bucket_name:
            try:
                s3_client = _make_s3_client()
                s3_client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=s3_key,
                    Body=zip_bytes,
                    ContentType="application/zip",
                    # Tag for lifecycle rule identification (30-day expiry managed via bucket policy)
                    Tagging="Expiry=30days",
                )
                await _set_progress(90)
            except ClientError as exc:
                logger.error("S3 upload failed", job_id=str(job_id), exc=str(exc))
                raise

        else:
            # S3 not configured — store key as placeholder for local dev
            logger.warning("S3 not configured, export ZIP not persisted", job_id=str(job_id))

        # Mark job completed
        await db.execute(
            text(
                "UPDATE public.export_jobs "
                "SET status = 'completed', progress_percent = 100, "
                "file_size_bytes = :size, s3_key = :s3_key, completed_at = NOW() "
                "WHERE id = :job_id"
            ),
            {
                "size": file_size,
                "s3_key": s3_key,
                "job_id": str(job_id),
            },
        )
        await db.commit()

        logger.info(
            "Export completed",
            job_id=str(job_id),
            file_size=file_size,
            s3_key=s3_key,
        )

        # Send email notification
        if settings.s3_bucket_name:
            try:
                download_url = await self.get_download_url(s3_key)
                await _send_export_email(
                    requester_email=requester_email,
                    requester_name=requester_name,
                    org_slug=org_slug,
                    download_url=download_url,
                    job_id=str(job_id),
                )
            except Exception as exc:
                logger.warning("Export email notification failed", exc=str(exc))

    # ------------------------------------------------------------------
    # Pre-export size estimation — AC1
    # ------------------------------------------------------------------

    async def get_export_estimate(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        schema_name: str,
    ) -> dict[str, Any]:
        """
        Return row counts per table to give a pre-export size estimate.
        AC1: "Estimated size shown before export (count of records per table)."
        """
        counts: dict[str, int] = {}
        total = 0

        # Tenant schema tables
        for table in _TENANT_TABLES:
            try:
                result = await db.execute(
                    text(f'SELECT COUNT(*) FROM "{schema_name}"."{table}"')  # noqa: S608
                )
                n = result.scalar() or 0
            except Exception:
                n = 0
            counts[table] = n
            total += n

        # Public schema tables scoped to this tenant
        for table in _PUBLIC_TABLES_TENANT_SCOPED:
            try:
                result = await db.execute(
                    text(f'SELECT COUNT(*) FROM public."{table}" WHERE tenant_id = :tid'),  # noqa: S608
                    {"tid": str(tenant_id)},
                )
                n = result.scalar() or 0
            except Exception:
                n = 0
            counts[f"public_{table}"] = n
            total += n

        return {
            "tables": counts,
            "total_records": total,
            "note": "Estimate based on current row counts; actual ZIP size varies with data content.",
        }

    # ------------------------------------------------------------------
    # Query export status — AC2
    # ------------------------------------------------------------------

    async def get_export_status(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> Optional[dict[str, Any]]:
        """
        Return job status dict or None if not found / not owned by tenant.
        """
        result = await db.execute(
            text(
                "SELECT id, status, progress_percent, file_size_bytes, s3_key, "
                "error_message, created_at, completed_at "
                "FROM public.export_jobs "
                "WHERE id = :job_id AND tenant_id = :tenant_id"
            ),
            {"job_id": str(job_id), "tenant_id": str(tenant_id)},
        )
        row = result.mappings().fetchone()
        if row is None:
            return None

        response: dict[str, Any] = {
            "job_id": str(row["id"]),
            "status": row["status"],
            "progress_percent": row["progress_percent"],
            "file_size_bytes": row["file_size_bytes"],
            "error": row["error_message"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "download_url": None,
        }

        # Include presigned download URL if completed and S3 is configured
        if row["status"] == "completed" and row["s3_key"] and settings.s3_bucket_name:
            try:
                response["download_url"] = await self.get_download_url(row["s3_key"])
            except Exception as exc:
                logger.warning("Could not generate download URL", exc=str(exc))

        return response

    # ------------------------------------------------------------------
    # List export history — AC5
    # ------------------------------------------------------------------

    async def list_exports(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return last `limit` export jobs for this tenant."""
        result = await db.execute(
            text(
                "SELECT id, status, progress_percent, file_size_bytes, s3_key, "
                "error_message, created_at, completed_at "
                "FROM public.export_jobs "
                "WHERE tenant_id = :tenant_id "
                "ORDER BY created_at DESC "
                "LIMIT :limit"
            ),
            {"tenant_id": str(tenant_id), "limit": limit},
        )
        rows = result.mappings().fetchall()
        jobs = []
        for row in rows:
            item: dict[str, Any] = {
                "job_id": str(row["id"]),
                "status": row["status"],
                "progress_percent": row["progress_percent"],
                "file_size_bytes": row["file_size_bytes"],
                "error": row["error_message"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
                "download_url": None,
            }
            if row["status"] == "completed" and row["s3_key"] and settings.s3_bucket_name:
                try:
                    item["download_url"] = await self.get_download_url(row["s3_key"])
                except Exception:
                    pass
            jobs.append(item)
        return jobs

    # ------------------------------------------------------------------
    # Presigned download URL — AC5
    # ------------------------------------------------------------------

    async def get_download_url(self, s3_key: str, expiry_seconds: int = 86400) -> str:
        """Generate S3 presigned GET URL (default 24h expiry)."""
        if not settings.s3_bucket_name:
            return f"/dev-export/{s3_key}"  # dev placeholder

        s3_client = _make_s3_client()
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=expiry_seconds,
        )
        return url


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

export_service = ExportService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_s3_client():
    """Create boto3 S3 client using settings credentials."""
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def _json_default(obj: Any) -> Any:
    """JSON serializer for types not serializable by default (uuid, datetime)."""
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


async def _send_export_email(
    requester_email: str,
    requester_name: str,
    org_slug: str,
    download_url: str,
    job_id: str,
) -> None:
    """Send export completion email with presigned download link."""
    from src.services.notification.notification_service import _send_email

    subject = "Your QUALISYS data export is ready"
    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #1a1a1a;">Your data export is ready</h2>
  <p>Hi {requester_name},</p>
  <p>Your data export for <strong>{org_slug}</strong> is ready for download.</p>
  <p>
    <a href="{download_url}"
       style="display: inline-block; background: #2563eb; color: white;
              padding: 12px 24px; border-radius: 6px; text-decoration: none;">
      Download Export ZIP
    </a>
  </p>
  <p style="color: #6b7280; font-size: 14px;">
    This link expires in 24 hours. The file will be available on S3 for 30 days.
  </p>
  <p style="color: #6b7280; font-size: 12px;">Job ID: {job_id}</p>
</body>
</html>
"""
    text_body = (
        f"Hi {requester_name},\n\n"
        f"Your data export for '{org_slug}' is ready.\n\n"
        f"Download: {download_url}\n\n"
        f"This link expires in 24 hours. Job ID: {job_id}\n"
    )

    await _send_email(
        recipient_email=requester_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        correlation_id=job_id,
    )
