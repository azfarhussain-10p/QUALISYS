"""Add index on (is_active, tenant_id) for efficient project list filtering

Revision ID: 010
Revises: 009
Create Date: 2026-02-25

Story: 1-11-project-management-archive-delete-list
AC: #1, #2, #3 — Efficient filtering of active/archived projects
Task: 1.3 — Index on (is_active, tenant_id) in all tenant schemas

This index supports:
  - GET /api/v1/projects?status=active   → WHERE is_active = true AND tenant_id = :tid
  - GET /api/v1/projects?status=archived → WHERE is_active = false AND tenant_id = :tid
  - GET /api/v1/projects?status=all      → WHERE tenant_id = :tid (still benefits from index)

Approach: Same DO block pattern as migrations 008 and 009.
"""

from alembic import op
from sqlalchemy import text


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


_UPGRADE_SQL = """
DO $$
DECLARE
    schema_rec RECORD;
    idx_name TEXT;
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP
        idx_name := format('idx_%s_projects_active_tenant',
                           replace(schema_rec.schema_name, '-', '_'));

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'projects'
              AND  indexname  = idx_name
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.projects (is_active, tenant_id)',
                idx_name,
                schema_rec.schema_name
            );
        END IF;
    END LOOP;
END $$;
"""

_DOWNGRADE_SQL = """
DO $$
DECLARE
    schema_rec RECORD;
    idx_name TEXT;
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP
        idx_name := format('idx_%s_projects_active_tenant',
                           replace(schema_rec.schema_name, '-', '_'));

        EXECUTE format(
            'DROP INDEX IF EXISTS %I.%I',
            schema_rec.schema_name,
            idx_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
