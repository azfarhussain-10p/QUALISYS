"""Create public.export_jobs and public.deletion_audit tables

Revision ID: 012
Revises: 011
Create Date: 2026-02-25

Story: 1-13-data-export-org-deletion
AC: #2 — public.export_jobs table: tracks async export background jobs
AC: #4, #8 — public.deletion_audit table: preserves deletion records after DROP SCHEMA CASCADE

Both tables live in the public schema so they survive tenant schema deletion.
"""

from alembic import op
from sqlalchemy import text


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Upgrade SQL
# ---------------------------------------------------------------------------

_UPGRADE_SQL = """
-- 1.1 public.export_jobs — tracks async data export background jobs
CREATE TABLE IF NOT EXISTS public.export_jobs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID         NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    requested_by     UUID         REFERENCES public.users(id) ON DELETE SET NULL,
    status           VARCHAR(20)  NOT NULL DEFAULT 'processing'
                                  CHECK (status IN ('processing', 'completed', 'failed')),
    progress_percent INTEGER      NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),
    file_size_bytes  BIGINT,
    s3_key           VARCHAR(500),
    error_message    TEXT,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMP WITH TIME ZONE
);

-- 1.3 Index on (tenant_id, created_at DESC) for listing exports per org
CREATE INDEX IF NOT EXISTS idx_export_jobs_tenant_created
    ON public.export_jobs (tenant_id, created_at DESC);

-- 1.2 public.deletion_audit — preserves deletion audit trail after DROP SCHEMA CASCADE
--     No FK to tenants/users since those rows are deleted during org deletion.
CREATE TABLE IF NOT EXISTS public.deletion_audit (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID         NOT NULL,
    org_name     VARCHAR(255) NOT NULL,
    org_slug     VARCHAR(100) NOT NULL,
    deleted_by   UUID         NOT NULL,
    member_count INTEGER      NOT NULL DEFAULT 0,
    details      JSONB        NOT NULL DEFAULT '{}',
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Index for lookups by tenant_id (used in audit queries post-deletion)
CREATE INDEX IF NOT EXISTS idx_deletion_audit_tenant
    ON public.deletion_audit (tenant_id);
"""

# ---------------------------------------------------------------------------
# Downgrade SQL — 1.4 rollback
# ---------------------------------------------------------------------------

_DOWNGRADE_SQL = """
DROP TABLE IF EXISTS public.deletion_audit;
DROP TABLE IF EXISTS public.export_jobs;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
