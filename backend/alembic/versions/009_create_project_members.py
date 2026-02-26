"""Create project_members table in all tenant schemas

Revision ID: 009
Revises: 008
Create Date: 2026-02-25

Story: 1-10-project-team-assignment
AC: #1 — project_members table with id, project_id, user_id, added_by, tenant_id, created_at
AC: #3 — RLS policy scoped to tenant_id for isolation
AC: #6 — table ready for creator auto-assignment on project creation

Approach:
  - Follows same DO block pattern as migration 008.
  - Iterates all tenant_% schemas and creates table if not already present.
  - UNIQUE index on (project_id, user_id) prevents duplicate membership.
  - Index on user_id for "which projects is this user in?" lookup.
  - No cross-schema FK constraints (same reason as migration 008 — cross-schema FKs
    require superuser privileges; referential integrity enforced at application layer).
  - tenant_id column required for RLS policy (same pattern as projects table).
"""

from alembic import op
from sqlalchemy import text


revision = "009"
down_revision = "008"
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

        -- 1.1 Create project_members table if not already present
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'project_members'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE TABLE %I.project_members (
                    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id  UUID        NOT NULL,
                    user_id     UUID        NOT NULL,
                    added_by    UUID,
                    tenant_id   UUID        NOT NULL,
                    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                $sql$,
                schema_rec.schema_name
            );
        END IF;

        -- 1.2 UNIQUE index on (project_id, user_id)
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'project_members'
              AND  indexname  = format('uix_%s_pm_project_user',
                                       replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE UNIQUE INDEX %I ON %I.project_members (project_id, user_id)',
                format('uix_%s_pm_project_user', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.3 Index on user_id for membership lookup
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'project_members'
              AND  indexname  = format('idx_%s_pm_user_id',
                                       replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.project_members (user_id)',
                format('idx_%s_pm_user_id', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.4 Enable RLS on project_members
        EXECUTE format(
            'ALTER TABLE %I.project_members ENABLE ROW LEVEL SECURITY',
            schema_rec.schema_name
        );

        -- 1.4 RLS policy: tenant isolation (same pattern as projects table)
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'project_members'
              AND  policyname = 'tenant_isolation'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE POLICY tenant_isolation ON %I.project_members
                    USING (tenant_id::text = current_setting('app.current_tenant', true))
                $sql$,
                schema_rec.schema_name
            );
        END IF;

    END LOOP;
END $$;
"""

# 1.5 Rollback: drop project_members from all tenant schemas
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
            'DROP TABLE IF EXISTS %I.project_members CASCADE',
            schema_rec.schema_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
