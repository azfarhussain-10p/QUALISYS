"""
QUALISYS — Org Deletion Service
Story: 1-13-data-export-org-deletion
AC: #3, #4, #6 — multi-step confirmation, background deletion, user impact

Deletion sequence (ordered per AC4):
  1. Log org.deletion_requested to public.deletion_audit (BEFORE any data deleted)
  2. Notify all org members via email
  3. Invalidate all sessions for all org members
  4. Delete public.tenants_users rows for this tenant
  5. Delete S3 objects (logo, exports, artifacts)
  6. DROP SCHEMA tenant_{slug} CASCADE
  7. Delete public.tenants row
  8. Update public.users.default_tenant_id = NULL for affected users

Security:
  - Schema name is looked up from public.tenants (never from user input — AC8.1)
  - 2FA/password verification required before any deletion proceeds (AC8.2)
  - Owner-only RBAC enforced at API layer (AC8.3)
"""

import uuid
from typing import Any, Optional

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.logger import logger
from src.services.tenant_provisioning import slug_to_schema_name, validate_safe_identifier

settings = get_settings()


class OrgDeletionService:
    """
    Handles org deletion: verification, background execution, user impact.
    """

    # ------------------------------------------------------------------
    # Verification — AC3
    # ------------------------------------------------------------------

    async def verify_deletion(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        org_name: str,
        org_name_confirmation: str,
        user_id: uuid.UUID,
        totp_code: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        Validate all confirmation factors before deletion proceeds.

        Steps:
          1. Org name must match exactly (case-sensitive)
          2. Either totp_code (if MFA enabled) or password re-entry

        Raises:
            ValueError with error code string on any verification failure.
        """
        # Step 1: org name confirmation (case-sensitive)
        if org_name_confirmation != org_name:
            raise ValueError("ORG_NAME_MISMATCH")

        # Load user for 2FA/password verification
        result = await db.execute(
            text("SELECT id, password_hash, totp_enabled FROM public.users WHERE id = :uid"),
            {"uid": str(user_id)},
        )
        user_row = result.mappings().fetchone()
        if user_row is None:
            raise ValueError("USER_NOT_FOUND")

        totp_enabled = bool(user_row["totp_enabled"])

        if totp_enabled:
            # Require TOTP code
            if not totp_code:
                raise ValueError("TOTP_REQUIRED")
            await self._verify_totp(db=db, user_id=user_id, totp_code=totp_code)
        else:
            # Require password re-entry
            if not password:
                raise ValueError("PASSWORD_REQUIRED")
            password_hash = user_row["password_hash"]
            if not password_hash:
                raise ValueError("NO_PASSWORD_SET")
            if not bcrypt.checkpw(password.encode(), password_hash.encode()):
                raise ValueError("INVALID_PASSWORD")

    async def _verify_totp(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        totp_code: str,
    ) -> None:
        """Verify TOTP code using TotpService."""
        from src.services.totp_service import totp_service

        result = await db.execute(
            text("SELECT totp_secret_encrypted FROM public.users WHERE id = :uid"),
            {"uid": str(user_id)},
        )
        row = result.mappings().fetchone()
        if not row or not row["totp_secret_encrypted"]:
            raise ValueError("MFA_NOT_SETUP")

        encrypted_secret = row["totp_secret_encrypted"]
        secret = totp_service.decrypt_secret(encrypted_secret)
        if not totp_service.verify_code(secret, totp_code):
            raise ValueError("INVALID_TOTP")

    # ------------------------------------------------------------------
    # Execute deletion — AC4 (background task body)
    # ------------------------------------------------------------------

    async def execute_deletion(
        self,
        org_id: uuid.UUID,
        deleted_by: uuid.UUID,
        deleted_by_name: str,
    ) -> None:
        """
        Execute the full deletion sequence in a background task.
        Each step is logged; failures mark the job as failed with the step that failed.
        Opens its own DB session (called as BackgroundTasks callback).
        """
        from src.db import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            try:
                await self._run_deletion(
                    db=db,
                    org_id=org_id,
                    deleted_by=deleted_by,
                    deleted_by_name=deleted_by_name,
                )
            except Exception as exc:
                logger.error(
                    "Org deletion failed",
                    org_id=str(org_id),
                    exc=str(exc),
                )
                # Attempt to record failure in deletion_audit if not already done
                try:
                    await db.execute(
                        text(
                            "INSERT INTO public.deletion_audit "
                            "(tenant_id, org_name, org_slug, deleted_by, member_count, details) "
                            "VALUES (:tid, :name, :slug, :by, 0, :details::jsonb)"
                        ),
                        {
                            "tid": str(org_id),
                            "name": "unknown",
                            "slug": "unknown",
                            "by": str(deleted_by),
                            "details": '{"error": "deletion_failed"}',
                        },
                    )
                    await db.commit()
                except Exception:
                    pass

    async def _run_deletion(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        deleted_by: uuid.UUID,
        deleted_by_name: str,
    ) -> None:
        """Inner deletion sequence."""

        # Look up tenant (schema name from DB — never from user input, AC8.1)
        result = await db.execute(
            text("SELECT id, name, slug FROM public.tenants WHERE id = :oid"),
            {"oid": str(org_id)},
        )
        tenant_row = result.mappings().fetchone()
        if tenant_row is None:
            logger.warning("Deletion: tenant not found", org_id=str(org_id))
            return

        org_name = tenant_row["name"]
        org_slug = tenant_row["slug"]
        schema_name = slug_to_schema_name(org_slug)

        # Count members for audit
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM public.tenants_users WHERE tenant_id = :tid"
            ),
            {"tid": str(org_id)},
        )
        member_count = result.scalar() or 0

        # Collect member emails + user_ids for notification + session invalidation
        result = await db.execute(
            text(
                "SELECT u.id, u.email, u.full_name "
                "FROM public.users u "
                "JOIN public.tenants_users tu ON tu.user_id = u.id "
                "WHERE tu.tenant_id = :tid"
            ),
            {"tid": str(org_id)},
        )
        members = result.mappings().fetchall()

        # ----------------------------------------------------------------
        # Step 1: Log deletion_requested to public.deletion_audit (BEFORE data deleted)
        # ----------------------------------------------------------------
        await db.execute(
            text(
                "INSERT INTO public.deletion_audit "
                "(tenant_id, org_name, org_slug, deleted_by, member_count, details) "
                "VALUES (:tid, :name, :slug, :by, :count, :details::jsonb)"
            ),
            {
                "tid": str(org_id),
                "name": org_name,
                "slug": org_slug,
                "by": str(deleted_by),
                "count": member_count,
                "details": '{"status": "deletion_requested"}',
            },
        )
        await db.commit()
        logger.info("Deletion step 1: audit recorded", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 2: Notify all org members
        # ----------------------------------------------------------------
        for member in members:
            try:
                await _send_deletion_notification(
                    recipient_email=str(member["email"]),
                    recipient_name=str(member["full_name"] or member["email"]),
                    org_name=org_name,
                    deleted_by_name=deleted_by_name,
                )
            except Exception as exc:
                logger.warning(
                    "Deletion: could not notify member",
                    user_id=str(member["id"]),
                    exc=str(exc),
                )
        logger.info("Deletion step 2: members notified", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 3: Invalidate all sessions for org members
        # ----------------------------------------------------------------
        try:
            from src.cache import get_redis_client
            redis = get_redis_client()
            for member in members:
                user_id = str(member["id"])
                # Pattern: sessions:user:{user_id}:* — scan and delete
                pattern = f"sessions:user:{user_id}:*"
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await redis.delete(*keys)
                    if cursor == 0:
                        break
        except Exception as exc:
            logger.warning("Deletion: session invalidation partial failure", exc=str(exc))
        logger.info("Deletion step 3: sessions invalidated", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 4: Delete public.tenants_users rows
        # ----------------------------------------------------------------
        await db.execute(
            text("DELETE FROM public.tenants_users WHERE tenant_id = :tid"),
            {"tid": str(org_id)},
        )
        await db.commit()
        logger.info("Deletion step 4: tenants_users removed", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 5: Delete S3 objects (logo + exports)
        # ----------------------------------------------------------------
        try:
            await _delete_s3_objects(org_id=org_id)
        except Exception as exc:
            logger.warning("Deletion: S3 cleanup partial failure", exc=str(exc))
        logger.info("Deletion step 5: S3 objects cleaned", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 6: DROP SCHEMA tenant_{slug} CASCADE
        # (schema_name validated from DB, not from user input — AC8.1)
        # ----------------------------------------------------------------
        if not validate_safe_identifier(schema_name):
            raise ValueError(f"Unsafe schema name derived from DB: {schema_name!r}")

        await db.execute(
            text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
        )
        await db.commit()
        logger.info("Deletion step 6: schema dropped", schema=schema_name)

        # ----------------------------------------------------------------
        # Step 7: Delete public.tenants row
        # ----------------------------------------------------------------
        await db.execute(
            text("DELETE FROM public.tenants WHERE id = :oid"),
            {"oid": str(org_id)},
        )
        await db.commit()
        logger.info("Deletion step 7: tenants row deleted", org_id=str(org_id))

        # ----------------------------------------------------------------
        # Step 8: Update public.users.default_tenant_id for affected users
        # ----------------------------------------------------------------
        for member in members:
            user_id = member["id"]
            # Find another org this user belongs to (any active membership)
            result = await db.execute(
                text(
                    "SELECT tenant_id FROM public.tenants_users "
                    "WHERE user_id = :uid AND is_active = true "
                    "ORDER BY joined_at ASC LIMIT 1"
                ),
                {"uid": str(user_id)},
            )
            other_tenant = result.scalar_one_or_none()
            await db.execute(
                text(
                    "UPDATE public.users SET default_tenant_id = :new_tid "
                    "WHERE id = :uid AND default_tenant_id = :old_tid"
                ),
                {
                    "new_tid": str(other_tenant) if other_tenant else None,
                    "uid": str(user_id),
                    "old_tid": str(org_id),
                },
            )
        await db.commit()
        logger.info("Deletion step 8: user default_tenant_id updated", org_id=str(org_id))

        # Update deletion_audit to mark as completed
        await db.execute(
            text(
                "UPDATE public.deletion_audit "
                "SET details = jsonb_set(details, '{status}', '\"completed\"') "
                "WHERE tenant_id = :tid AND deleted_by = :by"
            ),
            {"tid": str(org_id), "by": str(deleted_by)},
        )
        await db.commit()

        logger.info(
            "Org deletion completed",
            org_id=str(org_id),
            org_slug=org_slug,
            deleted_by=str(deleted_by),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

org_deletion_service = OrgDeletionService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_deletion_notification(
    recipient_email: str,
    recipient_name: str,
    org_name: str,
    deleted_by_name: str,
) -> None:
    """Notify an org member that their organization has been deleted."""
    from src.services.notification.notification_service import _send_email

    subject = f"Organization '{org_name}' has been deleted"
    html_body = f"""
<!DOCTYPE html>
<html>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #dc2626;">Organization Deleted</h2>
  <p>Hi {recipient_name},</p>
  <p>
    The organization <strong>{org_name}</strong> has been permanently deleted
    by <strong>{deleted_by_name}</strong>.
  </p>
  <p>You will no longer have access to this organization's projects, test cases, or data.</p>
  <p>If you belong to other organizations, you can continue using QUALISYS with those accounts.</p>
  <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
  <p style="color: #6b7280; font-size: 14px;">
    If you believe this was done in error, please contact support.
  </p>
</body>
</html>
"""
    text_body = (
        f"Hi {recipient_name},\n\n"
        f"The organization '{org_name}' has been permanently deleted by {deleted_by_name}.\n\n"
        f"You will no longer have access to this organization's data.\n\n"
        f"If you have questions, please contact support.\n"
    )

    await _send_email(
        recipient_email=recipient_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        correlation_id=str(uuid.uuid4()),
    )


async def _delete_s3_objects(org_id: uuid.UUID) -> None:
    """
    Delete all S3 objects under the tenant prefix:
      - tenants/{org_id}/logo/
      - exports/{org_id}/
    """
    if not settings.s3_bucket_name:
        return

    import boto3
    s3_client = boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )

    prefixes = [
        f"tenants/{org_id}/",
        f"exports/{org_id}/",
    ]

    for prefix in prefixes:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.s3_bucket_name, Prefix=prefix):
            objects = page.get("Contents", [])
            if objects:
                delete_spec = {"Objects": [{"Key": obj["Key"]} for obj in objects]}
                s3_client.delete_objects(Bucket=settings.s3_bucket_name, Delete=delete_spec)
