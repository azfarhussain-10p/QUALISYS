"""Create agent_runs, agent_run_steps, artifacts, and artifact_versions tables

Revision ID: 015
Revises: 014
Create Date: 2026-02-28

Story: 2-6-ai-agent-selection-ui
AC: #15 — POST /agent-runs creates queued run + per-agent steps
Stories 2-7 through 2-11 prerequisites: agent_runs, agent_run_steps, artifacts, artifact_versions

Approach:
  - PL/pgSQL DO block iterates all tenant_% schemas (idempotent IF NOT EXISTS)
  - agent_runs: tracks the overall pipeline run (queued → running → completed/failed/cancelled)
  - agent_run_steps: per-agent progress tracking within a run
  - artifacts: LLM-generated outputs (coverage_matrix, manual_checklist, playwright_script, bdd_scenario)
  - artifact_versions: full version history + unified diff (AC-28/29)
  - Note: artifact_versions depends on artifacts; agent_run_steps depends on agent_runs
    — create agent_runs before agent_run_steps, artifacts before artifact_versions
"""

from alembic import op
from sqlalchemy import text


revision = "015"
down_revision = "014"
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

        -- agent_runs: one row per pipeline execution
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'agent_runs'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.agent_runs (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id       UUID NOT NULL,
                    pipeline_mode    VARCHAR(20) NOT NULL DEFAULT ''sequential'',
                    agents_selected  JSONB NOT NULL,
                    status           VARCHAR(50) NOT NULL DEFAULT ''queued'',
                    total_tokens     INTEGER NOT NULL DEFAULT 0,
                    total_cost_usd   NUMERIC(10, 4) NOT NULL DEFAULT 0,
                    started_at       TIMESTAMPTZ,
                    completed_at     TIMESTAMPTZ,
                    error_message    TEXT,
                    created_by       UUID NOT NULL,
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )', schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_agent_runs_project_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_agent_runs_project_id
                ON %I.agent_runs (project_id)',
                schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_agent_runs_status'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_agent_runs_status
                ON %I.agent_runs (status)',
                schema_rec.schema_name);
        END IF;

        -- agent_run_steps: per-agent progress within a run
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'agent_run_steps'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.agent_run_steps (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    run_id          UUID NOT NULL,
                    agent_type      VARCHAR(50) NOT NULL,
                    status          VARCHAR(50) NOT NULL DEFAULT ''queued'',
                    progress_pct    INTEGER NOT NULL DEFAULT 0,
                    progress_label  TEXT,
                    tokens_used     INTEGER NOT NULL DEFAULT 0,
                    started_at      TIMESTAMPTZ,
                    completed_at    TIMESTAMPTZ,
                    error_message   TEXT
                )', schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_agent_run_steps_run_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_agent_run_steps_run_id
                ON %I.agent_run_steps (run_id)',
                schema_rec.schema_name);
        END IF;

        -- artifacts: LLM-generated test outputs
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'artifacts'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.artifacts (
                    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id       UUID NOT NULL,
                    run_id           UUID,
                    agent_type       VARCHAR(50) NOT NULL,
                    artifact_type    VARCHAR(100) NOT NULL,
                    title            VARCHAR(255) NOT NULL,
                    current_version  INTEGER NOT NULL DEFAULT 1,
                    metadata         JSONB,
                    created_by       UUID NOT NULL,
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )', schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_artifacts_project_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_artifacts_project_id
                ON %I.artifacts (project_id)',
                schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_artifacts_artifact_type'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_artifacts_artifact_type
                ON %I.artifacts (artifact_type)',
                schema_rec.schema_name);
        END IF;

        -- artifact_versions: full version history (AC-28/29)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'artifact_versions'
        ) THEN
            EXECUTE format('
                CREATE TABLE %I.artifact_versions (
                    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    artifact_id     UUID NOT NULL,
                    version         INTEGER NOT NULL,
                    content         TEXT NOT NULL,
                    content_type    VARCHAR(50) NOT NULL,
                    diff_from_prev  TEXT,
                    edited_by       UUID,
                    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (artifact_id, version)
                )', schema_rec.schema_name);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  indexname  = 'idx_artifact_versions_artifact_id'
        ) THEN
            EXECUTE format('
                CREATE INDEX idx_artifact_versions_artifact_id
                ON %I.artifact_versions (artifact_id)',
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
        EXECUTE format('DROP TABLE IF EXISTS %I.artifact_versions CASCADE',
                       schema_rec.schema_name);
        EXECUTE format('DROP TABLE IF EXISTS %I.artifacts CASCADE',
                       schema_rec.schema_name);
        EXECUTE format('DROP TABLE IF EXISTS %I.agent_run_steps CASCADE',
                       schema_rec.schema_name);
        EXECUTE format('DROP TABLE IF EXISTS %I.agent_runs CASCADE',
                       schema_rec.schema_name);
    END LOOP;
END;
$$;
"""


def upgrade() -> None:
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
