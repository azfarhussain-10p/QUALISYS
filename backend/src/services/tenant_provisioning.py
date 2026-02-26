"""
QUALISYS — TenantProvisioningService
Story: 1-2-organization-creation-setup
AC: AC3 — PostgreSQL schema tenant_{slug} creation
AC: AC3 — Base migration (org_members, audit_logs tables) applied to new schema
AC: AC3 — Transaction-wrapped schema creation + rollback on failure
AC: AC3 — Async provisioning with status tracking
AC: AC9 — Schema name validated against SQL injection ([a-z0-9_] only)

Security: All DDL uses double-quoted identifiers after strict regex validation.
  NO string interpolation on user-supplied input.
  Schema name derived from slug (which is validated on org creation) via replace('-', '_').
  Additional re.fullmatch guard before any DDL execution.

Per architecture.md §ADR-001:
  Schema naming: tenant_{slug.replace('-', '_')}
  e.g. slug="my-org" → schema="tenant_my_org"
"""

import re
import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger


# ---------------------------------------------------------------------------
# Status Enum (AC3)
# ---------------------------------------------------------------------------

class ProvisioningStatus(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    READY = "ready"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Security — identifier validation (AC9)
# ---------------------------------------------------------------------------

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def validate_safe_identifier(name: str) -> bool:
    """
    Returns True iff `name` is safe to use as a PostgreSQL identifier.

    Rules (AC9):
      - Starts with lowercase letter
      - Contains only lowercase letters, digits, underscores
      - Max 63 chars (PostgreSQL identifier limit)
      - No SQL meta-characters: no quotes, spaces, semicolons, dashes, etc.

    This guard is called on the SCHEMA NAME (not the slug).
    The schema name is derived from the slug by replace('-', '_'), so the calling
    code must validate this already-transformed string.
    """
    return bool(_SAFE_IDENTIFIER_RE.match(name))


def slug_to_schema_name(slug: str) -> str:
    """
    Convert user-facing slug (lowercase alphanumeric + hyphens) to PostgreSQL schema name.
    Hyphens → underscores; prefixed with 'tenant_'.
    Example: 'my-org' → 'tenant_my_org'
    """
    return f"tenant_{slug.replace('-', '_')}"


# ---------------------------------------------------------------------------
# Base DDL for new tenant schema (AC3)
# Initial tables: org_members + audit_logs
# These are the minimal tables required for the org to function.
# Additional tables added by subsequent story migrations (Stories 1.3, 1.12, etc.)
# ---------------------------------------------------------------------------

def _build_base_migration_ddl(schema: str) -> list[str]:
    """
    Returns ordered DDL statements to create base tables in the new tenant schema.
    Schema name must be pre-validated by validate_safe_identifier().
    Double-quoted to prevent identifier injection.
    """
    # After validation, double-quoting is safe
    q = f'"{schema}"'
    return [
        # org_members — tenant-scoped membership table (extended by Story 1.3)
        f"""CREATE TABLE {q}.org_members (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id       UUID NOT NULL,
            role          VARCHAR(30) NOT NULL,
            is_active     BOOLEAN NOT NULL DEFAULT TRUE,
            joined_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            removed_at    TIMESTAMP WITH TIME ZONE,
            removed_by    UUID,
            UNIQUE (user_id)
        )""",
        f"CREATE INDEX idx_om_user_id ON {q}.org_members (user_id)",
        f"CREATE INDEX idx_om_is_active ON {q}.org_members (is_active) WHERE NOT is_active",

        # audit_logs — INSERT-ONLY immutable event log (extended by Story 1.12)
        f"""CREATE TABLE {q}.audit_logs (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            action        VARCHAR(100) NOT NULL,
            actor_id      UUID,
            actor_email   VARCHAR(255) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            resource_id   UUID,
            details       JSONB NOT NULL DEFAULT '{{}}',
            ip_address    INET,
            user_agent    TEXT,
            created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        )""",
        f"CREATE INDEX idx_al_action    ON {q}.audit_logs (action)",
        f"CREATE INDEX idx_al_actor_id  ON {q}.audit_logs (actor_id)",
        f"CREATE INDEX idx_al_created_at ON {q}.audit_logs (created_at DESC)",

        # Enforce audit_logs immutability (INSERT-ONLY)
        f"""CREATE RULE audit_no_update AS ON UPDATE TO {q}.audit_logs DO INSTEAD NOTHING""",
        f"""CREATE RULE audit_no_delete AS ON DELETE TO {q}.audit_logs DO INSTEAD NOTHING""",

        # projects — AC2 (Story 1.9): full schema including slug and new columns
        f"""CREATE TABLE {q}.projects (
            id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            name             VARCHAR(255) NOT NULL,
            description      TEXT,
            organization_id  UUID,
            tenant_id        UUID        NOT NULL,
            slug             VARCHAR(100) NOT NULL,
            app_url          VARCHAR(500),
            github_repo_url  VARCHAR(500),
            status           VARCHAR(20)  NOT NULL DEFAULT 'active',
            settings         JSONB        NOT NULL DEFAULT '{{}}',
            is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
            created_by       UUID,
            created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE (slug)
        )""",
        f"CREATE INDEX idx_proj_tenant_id ON {q}.projects (tenant_id)",
        f"CREATE INDEX idx_proj_is_active ON {q}.projects (is_active) WHERE NOT is_active",

        # RLS on projects — tenant isolation via app.current_tenant session variable
        f"ALTER TABLE {q}.projects ENABLE ROW LEVEL SECURITY",
        f"""CREATE POLICY tenant_isolation ON {q}.projects
            USING (tenant_id::text = current_setting('app.current_tenant', true))""",

        # project_members — AC#1 (Story 1.10): join table for project-level access control
        f"""CREATE TABLE {q}.project_members (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id  UUID        NOT NULL,
            user_id     UUID        NOT NULL,
            added_by    UUID,
            tenant_id   UUID        NOT NULL,
            created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            UNIQUE (project_id, user_id)
        )""",
        f"CREATE INDEX idx_pm_user_id ON {q}.project_members (user_id)",

        # RLS on project_members — same tenant isolation pattern
        f"ALTER TABLE {q}.project_members ENABLE ROW LEVEL SECURITY",
        f"""CREATE POLICY tenant_isolation ON {q}.project_members
            USING (tenant_id::text = current_setting('app.current_tenant', true))""",
    ]


# ---------------------------------------------------------------------------
# TenantProvisioningService
# ---------------------------------------------------------------------------

class TenantProvisioningService:
    """
    Provisions a new PostgreSQL schema for an organization tenant.

    Flow (AC3):
      1. Validate schema name (no SQL injection)
      2. BEGIN transaction
      3. CREATE SCHEMA tenant_{slug}
      4. Apply base migration DDL (org_members, audit_logs)
      5. COMMIT — schema is live
      On any failure: ROLLBACK (schema dropped atomically)

    The service uses the raw asyncpg connection for DDL because SQLAlchemy
    ORM does not support CREATE SCHEMA / DDL operations directly.
    DDL statements are NOT run via string interpolation on user input —
    the schema name is validated against a strict regex before execution.
    """

    async def provision_tenant(
        self,
        tenant_id: uuid.UUID,
        slug: str,
        db: AsyncSession,
        correlation_id: Optional[str] = None,
    ) -> ProvisioningStatus:
        """
        Create PostgreSQL schema for tenant and apply base migration.

        Returns ProvisioningStatus.READY on success.
        Raises RuntimeError (with descriptive message) on failure.
        Schema is rolled back atomically on failure.

        Security (AC9):
          - `slug` is the USER-FACING slug (already validated by OrgService before
            storing in public.tenants — only [a-z0-9-] allowed)
          - `schema_name` derived by replacing hyphens with underscores
          - `validate_safe_identifier(schema_name)` guards against any edge case
        """
        schema_name = slug_to_schema_name(slug)

        # AC9: guard — should already be safe given slug validation, but defensive
        if not validate_safe_identifier(schema_name):
            raise ValueError(
                f"Derived schema name '{schema_name}' failed safety validation. "
                f"Slug '{slug}' may contain invalid characters."
            )

        ctx = dict(
            tenant_id=str(tenant_id),
            slug=slug,
            schema_name=schema_name,
            correlation_id=correlation_id or "",
        )
        logger.info("Tenant schema provisioning started", **ctx)

        try:
            # Use the raw asyncpg connection for DDL
            conn = await db.connection()
            raw_conn = await conn.get_raw_connection()

            # All DDL in a single transaction — rollback on any failure (AC3)
            async with raw_conn.transaction():
                # CREATE SCHEMA — double-quoted identifier, validated above
                await raw_conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
                logger.info("Schema created", schema=schema_name, **ctx)

                # Apply base migration DDL statements
                for stmt in _build_base_migration_ddl(schema_name):
                    await raw_conn.execute(stmt)

            logger.info("Tenant schema provisioning complete", schema=schema_name, **ctx)
            return ProvisioningStatus.READY

        except Exception as exc:
            logger.error(
                "Tenant schema provisioning failed",
                schema=schema_name,
                error=str(exc),
                **ctx,
            )
            # Attempt schema cleanup (best-effort; transaction rollback handles DDL)
            try:
                await db.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
                await db.commit()
            except Exception:
                pass
            raise RuntimeError(
                f"Failed to provision schema '{schema_name}': {exc}"
            ) from exc

    async def drop_tenant_schema(
        self,
        slug: str,
        db: AsyncSession,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Drop tenant schema (CASCADE). Called on org deletion (Story 1.13).
        Schema name validated before DROP.
        """
        schema_name = slug_to_schema_name(slug)
        if not validate_safe_identifier(schema_name):
            raise ValueError(f"Invalid schema name: {schema_name}")

        logger.info(
            "Dropping tenant schema",
            schema=schema_name,
            correlation_id=correlation_id or "",
        )
        await db.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await db.commit()

    async def get_provisioning_status(
        self,
        slug: str,
        db: AsyncSession,
    ) -> ProvisioningStatus:
        """
        Check whether tenant schema exists by querying pg_namespace.
        Returns READY if exists, FAILED otherwise.
        """
        schema_name = slug_to_schema_name(slug)
        result = await db.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :schema"),
            {"schema": schema_name},
        )
        exists = result.scalar_one_or_none() is not None
        return ProvisioningStatus.READY if exists else ProvisioningStatus.PENDING
