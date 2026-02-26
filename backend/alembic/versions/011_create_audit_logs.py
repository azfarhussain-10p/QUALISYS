"""Create audit_logs table in all tenant schemas

Revision ID: 011
Revises: 010
Create Date: 2026-02-25

Story: 1-12-usage-analytics-audit-logs-basic
AC: #2 — audit_logs table (id, tenant_id, actor_user_id, action, resource_type,
          resource_id, details, ip_address, user_agent, created_at)
AC: #2 — Indexes: (tenant_id, created_at DESC), (tenant_id, action),
          (tenant_id, actor_user_id)
AC: #2 — RLS policy for tenant isolation (tenant_id = app.current_tenant)
AC: #2 — INSERT-ONLY: RLS blocks UPDATE and DELETE (immutable audit trail)

Approach:
  - Follows same DO block pattern as migration 009.
  - Iterates all tenant_% schemas and creates table if not already present.
  - The audit_logs table is INSERT-ONLY: separate RLS policies with USING (false)
    block all UPDATE and DELETE operations, even if the DB role has those privileges.
  - No cross-schema FK on actor_user_id (same reasoning as prior migrations —
    cross-schema FKs require superuser; referential integrity at application layer).
"""

from alembic import op
from sqlalchemy import text


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# PL/pgSQL — idempotent DDL across all tenant schemas
# ---------------------------------------------------------------------------

_UPGRADE_SQL = """
DO $$
DECLARE
    schema_rec RECORD;
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP

        -- 1.1 Create audit_logs table if not already present
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'audit_logs'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE TABLE %I.audit_logs (
                    id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id      UUID         NOT NULL,
                    actor_user_id  UUID         NOT NULL,
                    action         VARCHAR(100) NOT NULL,
                    resource_type  VARCHAR(50)  NOT NULL,
                    resource_id    UUID,
                    details        JSONB,
                    ip_address     VARCHAR(45),
                    user_agent     TEXT,
                    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                $sql$,
                schema_rec.schema_name
            );
        END IF;

        -- 1.2 Index on (tenant_id, created_at DESC) for paginated list queries
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  indexname  = format('idx_%s_al_tenant_created',
                                       replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.audit_logs (tenant_id, created_at DESC)',
                format('idx_%s_al_tenant_created', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.3 Index on (tenant_id, action) for action-type filtering
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  indexname  = format('idx_%s_al_tenant_action',
                                       replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.audit_logs (tenant_id, action)',
                format('idx_%s_al_tenant_action', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.4 Index on (tenant_id, actor_user_id) for actor filtering
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  indexname  = format('idx_%s_al_tenant_actor',
                                       replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.audit_logs (tenant_id, actor_user_id)',
                format('idx_%s_al_tenant_actor', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.5 Enable RLS on audit_logs
        EXECUTE format(
            'ALTER TABLE %I.audit_logs ENABLE ROW LEVEL SECURITY',
            schema_rec.schema_name
        );

        -- 1.5 RLS policy: tenant isolation for SELECT (read own tenant only)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  policyname = 'tenant_isolation'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE POLICY tenant_isolation ON %I.audit_logs
                    FOR SELECT
                    USING (tenant_id::text = current_setting('app.current_tenant', true))
                $sql$,
                schema_rec.schema_name
            );
        END IF;

        -- 1.5 RLS policy: allow INSERT (any tenant — actor writes own tenant record)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  policyname = 'allow_insert'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE POLICY allow_insert ON %I.audit_logs
                    FOR INSERT
                    WITH CHECK (true)
                $sql$,
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 INSERT-ONLY: block UPDATE via RLS (immutable audit trail — C3)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  policyname = 'block_update'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE POLICY block_update ON %I.audit_logs
                    FOR UPDATE
                    USING (false)
                $sql$,
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 INSERT-ONLY: block DELETE via RLS (immutable audit trail — C3)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'audit_logs'
              AND  policyname = 'block_delete'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE POLICY block_delete ON %I.audit_logs
                    FOR DELETE
                    USING (false)
                $sql$,
                schema_rec.schema_name
            );
        END IF;

    END LOOP;
END $$;
"""

# Rollback: drop audit_logs from all tenant schemas
_DOWNGRADE_SQL = """
DO $$
DECLARE
    schema_rec RECORD;
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP
        EXECUTE format(
            'DROP TABLE IF EXISTS %I.audit_logs CASCADE',
            schema_rec.schema_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
