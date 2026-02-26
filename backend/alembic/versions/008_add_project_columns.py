"""Add slug/app_url/github_repo_url/status/created_by to tenant schema projects tables

Revision ID: 008
Revises: 007
Create Date: 2026-02-25

Story: 1-9-project-creation-configuration
AC: AC2 — projects record with slug, app_url, github_repo_url, status, created_by
AC: AC4 — JSONB settings column already exists; slug unique within tenant schema

Approach:
  - tenant_% schemas are created dynamically per org; Alembic cannot enumerate them
    at migration-author time.  We iterate pg_namespace at upgrade time to handle all
    existing schemas.
  - Uses ADD COLUMN IF NOT EXISTS so the migration is idempotent.
  - created_by has no FK to public.users inside the tenant schema (cross-schema FK
    constraint requires superuser privileges and complicates cross-DB portability).
    Referential integrity is enforced at application layer (service verifies user exists).
  - Slug uniqueness is enforced by a UNIQUE index within each tenant schema.
    Since each tenant has its own schema, schema-level unique index is sufficient.
  - Backfills slugs for existing projects using a deterministic slug algorithm
    (lowercase alphanumeric + hyphens, collision-safe suffix).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# PL/pgSQL helper — runs DDL across all existing tenant schemas
# ---------------------------------------------------------------------------

_UPGRADE_SQL = """
DO $$
DECLARE
    schema_rec RECORD;
    proj_rec   RECORD;
    base_slug  TEXT;
    candidate  TEXT;
    suffix_n   INT;
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP
        -- AC2: add new columns if they do not already exist

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'projects'
              AND  column_name  = 'slug'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.projects ADD COLUMN slug VARCHAR(100)',
                schema_rec.schema_name
            );
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'projects'
              AND  column_name  = 'app_url'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.projects ADD COLUMN app_url VARCHAR(500)',
                schema_rec.schema_name
            );
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'projects'
              AND  column_name  = 'github_repo_url'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.projects ADD COLUMN github_repo_url VARCHAR(500)',
                schema_rec.schema_name
            );
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'projects'
              AND  column_name  = 'status'
        ) THEN
            EXECUTE format(
                $sql$ALTER TABLE %I.projects ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'$sql$,
                schema_rec.schema_name
            );
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'projects'
              AND  column_name  = 'created_by'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.projects ADD COLUMN created_by UUID',
                schema_rec.schema_name
            );
        END IF;

        -- Subtask 1.3: Backfill slugs for existing projects (rows with NULL slug)
        FOR proj_rec IN
            EXECUTE format(
                'SELECT id, name FROM %I.projects WHERE slug IS NULL',
                schema_rec.schema_name
            )
        LOOP
            -- Generate base slug: lowercase, replace non-alphanumeric with hyphens,
            -- collapse consecutive hyphens, strip leading/trailing hyphens, truncate.
            base_slug := lower(proj_rec.name);
            base_slug := regexp_replace(base_slug, '[^a-z0-9]+', '-', 'g');
            base_slug := regexp_replace(base_slug, '^-+|-+$', '', 'g');
            base_slug := left(base_slug, 90);
            IF base_slug = '' THEN
                base_slug := 'project';
            END IF;

            -- Collision detection with suffix
            candidate := base_slug;
            suffix_n   := 0;
            LOOP
                EXECUTE format(
                    'SELECT 1 FROM %I.projects WHERE slug = $1 AND id != $2',
                    schema_rec.schema_name
                )
                INTO proj_rec
                USING candidate, proj_rec.id;
                EXIT WHEN NOT FOUND;
                suffix_n  := suffix_n + 1;
                candidate := left(base_slug, 90 - length('-' || suffix_n::text))
                             || '-' || suffix_n::text;
            END LOOP;

            EXECUTE format(
                'UPDATE %I.projects SET slug = $1 WHERE id = $2',
                schema_rec.schema_name
            )
            USING candidate, proj_rec.id;
        END LOOP;

        -- Subtask 1.2: Create unique index on slug (if not already present)
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'projects'
              AND  indexname  = format('ix_%s_projects_slug', replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE UNIQUE INDEX %I ON %I.projects (slug)',
                format('ix_%s_projects_slug', schema_rec.schema_name),
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
BEGIN
    FOR schema_rec IN
        SELECT nspname AS schema_name
        FROM   pg_namespace
        WHERE  nspname LIKE 'tenant_%'
        ORDER  BY nspname
    LOOP
        EXECUTE format(
            'DROP INDEX IF EXISTS %I.%I',
            schema_rec.schema_name,
            format('ix_%s_projects_slug', schema_rec.schema_name)
        );
        EXECUTE format(
            'ALTER TABLE %I.projects
               DROP COLUMN IF EXISTS slug,
               DROP COLUMN IF EXISTS app_url,
               DROP COLUMN IF EXISTS github_repo_url,
               DROP COLUMN IF EXISTS status,
               DROP COLUMN IF EXISTS created_by',
            schema_rec.schema_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
