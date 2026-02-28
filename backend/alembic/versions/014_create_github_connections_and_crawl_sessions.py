"""Create github_connections and crawl_sessions tables

Revision ID: 014
Revises: 013
Create Date: 2026-02-27

Story: 2-3-github-repository-connection
AC: #9 — github_connections table: PAT validation, clone_path, status, analysis_summary
AC: #10 — expires_at column for 7-day auto-cleanup of cloned repos
Story 2-5 prerequisite: crawl_sessions table created here (same migration per tech-spec §4.2)

Approach:
  - PL/pgSQL DO block iterates all tenant_% schemas (idempotent IF NOT EXISTS)
  - github_connections: stores encrypted PAT, clone status, and source-code analysis summary
  - crawl_sessions: stores Playwright DOM crawl results (used from Story 2-5)
  - Indexes on project_id for both tables (fast per-project lookups)
"""

from alembic import op
from sqlalchemy import text


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


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

        -- github_connections: one active connection per project (or more for history)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'github_connections'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.github_connections (
                    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id          UUID NOT NULL,
                    repo_url            VARCHAR(500) NOT NULL,
                    encrypted_token     TEXT NOT NULL,
                    clone_path          TEXT,
                    status              VARCHAR(50) NOT NULL DEFAULT ''pending'',
                    routes_count        INTEGER NOT NULL DEFAULT 0,
                    components_count    INTEGER NOT NULL DEFAULT 0,
                    endpoints_count     INTEGER NOT NULL DEFAULT 0,
                    analysis_summary    JSONB,
                    error_message       TEXT,
                    expires_at          TIMESTAMPTZ,
                    created_by          UUID NOT NULL,
                    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )', schema_rec.schema_name);
        END IF;

        -- Index on project_id for fast per-project lookups
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_github_connections_project_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_github_connections_project_id
                ON %I.github_connections (project_id)',
                schema_rec.schema_name);
        END IF;

        -- crawl_sessions: Playwright DOM crawl sessions (Story 2-5)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'crawl_sessions'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.crawl_sessions (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id      UUID NOT NULL,
                    target_url      VARCHAR(2000) NOT NULL,
                    auth_config     JSONB,
                    status          VARCHAR(50) NOT NULL DEFAULT ''pending'',
                    pages_crawled   INTEGER NOT NULL DEFAULT 0,
                    forms_found     INTEGER NOT NULL DEFAULT 0,
                    links_found     INTEGER NOT NULL DEFAULT 0,
                    crawl_data      JSONB,
                    error_message   TEXT,
                    started_at      TIMESTAMPTZ,
                    completed_at    TIMESTAMPTZ,
                    created_by      UUID NOT NULL,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )', schema_rec.schema_name);
        END IF;

        -- Index on project_id for crawl_sessions
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_crawl_sessions_project_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_crawl_sessions_project_id
                ON %I.crawl_sessions (project_id)',
                schema_rec.schema_name);
        END IF;

    END LOOP;
END;
$$;
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
        EXECUTE format('DROP TABLE IF EXISTS %I.crawl_sessions CASCADE',
                       schema_rec.schema_name);
        EXECUTE format('DROP TABLE IF EXISTS %I.github_connections CASCADE',
                       schema_rec.schema_name);
    END LOOP;
END;
$$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
