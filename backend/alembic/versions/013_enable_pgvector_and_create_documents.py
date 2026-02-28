"""Enable pgvector extension and create documents, document_chunks, document_embeddings tables

Revision ID: 013
Revises: 012
Create Date: 2026-02-26

Story: 2-1-document-upload-parsing
AC: #1, #6, #8 — documents table with S3 key, parse_status, filename, file_type columns
AC: #2 — parse_status, parsed_text, preview_text, page_count columns
AC: #6 — CASCADE delete propagates to document_chunks and document_embeddings
DoD C3 — vector(1536) column and ivfflat index must match pgvector_pattern.py spike contract

Approach:
  - Step 1: CREATE EXTENSION IF NOT EXISTS vector SCHEMA public (public schema, once globally)
  - Step 2: DO block iterates all tenant_% schemas and creates tables + indexes idempotently
  - documents table lives in tenant schema; project_id references projects table (same tenant schema)
  - document_chunks and document_embeddings are pre-created here to avoid blocking Story 2-2
  - ivfflat index on vector(1536) column uses vector_cosine_ops (matches pgvector_pattern.py)
"""

from alembic import op
from sqlalchemy import text


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Step 1: Enable pgvector extension globally (public schema, idempotent)
# ---------------------------------------------------------------------------

_ENABLE_PGVECTOR_SQL = """
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;
"""

# ---------------------------------------------------------------------------
# Step 2: PL/pgSQL DO block — iterate all tenant_% schemas, create tables + indexes
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

        -- 1.3 Create documents table (upload metadata + parse state)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'documents'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE TABLE %I.documents (
                    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
                    project_id      UUID         NOT NULL REFERENCES %I.projects(id) ON DELETE CASCADE,
                    filename        VARCHAR(255) NOT NULL,
                    file_type       VARCHAR(20)  NOT NULL,
                    file_size_bytes INTEGER      NOT NULL,
                    s3_key          TEXT         NOT NULL,
                    parse_status    VARCHAR(50)  NOT NULL DEFAULT 'pending'
                                    CHECK (parse_status IN ('pending', 'processing', 'completed', 'failed')),
                    parsed_text     TEXT,
                    preview_text    TEXT,
                    page_count      INTEGER,
                    chunk_count     INTEGER      NOT NULL DEFAULT 0,
                    error_message   TEXT,
                    created_by      UUID         NOT NULL REFERENCES public.users(id),
                    created_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                $sql$,
                schema_rec.schema_name,
                schema_rec.schema_name
            );
        END IF;

        -- 1.4 Create document_chunks table (1000-token segments — used in Story 2-2)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'document_chunks'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE TABLE %I.document_chunks (
                    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID    NOT NULL REFERENCES %I.documents(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content     TEXT    NOT NULL,
                    token_count INTEGER NOT NULL,
                    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                $sql$,
                schema_rec.schema_name,
                schema_rec.schema_name
            );
        END IF;

        -- 1.5 Create document_embeddings table with vector(1536) — Story 2-2 contract gate
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE  table_schema = schema_rec.schema_name
              AND  table_name   = 'document_embeddings'
        ) THEN
            EXECUTE format(
                $sql$
                CREATE TABLE %I.document_embeddings (
                    id         UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
                    chunk_id   UUID                    NOT NULL REFERENCES %I.document_chunks(id) ON DELETE CASCADE,
                    embedding  public.vector(1536),
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                )
                $sql$,
                schema_rec.schema_name,
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 Index: idx_documents_project_id — list documents by project
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'documents'
              AND  indexname  = format('idx_%s_docs_project_id',
                                      replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.documents (project_id)',
                format('idx_%s_docs_project_id', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 Index: idx_documents_parse_status — filter pending/processing for polling
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'documents'
              AND  indexname  = format('idx_%s_docs_parse_status',
                                      replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.documents (parse_status)',
                format('idx_%s_docs_parse_status', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 Index: idx_document_chunks_document_id — lookup chunks by document
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'document_chunks'
              AND  indexname  = format('idx_%s_chunks_document_id',
                                      replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.document_chunks (document_id)',
                format('idx_%s_chunks_document_id', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

        -- 1.6 Index: idx_document_embeddings_vector — ivfflat cosine similarity (pgvector contract)
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE  schemaname = schema_rec.schema_name
              AND  tablename  = 'document_embeddings'
              AND  indexname  = format('idx_%s_embeddings_vector',
                                      replace(schema_rec.schema_name, '-', '_'))
        ) THEN
            EXECUTE format(
                'CREATE INDEX %I ON %I.document_embeddings USING ivfflat (embedding vector_cosine_ops)',
                format('idx_%s_embeddings_vector', replace(schema_rec.schema_name, '-', '_')),
                schema_rec.schema_name
            );
        END IF;

    END LOOP;
END $$;
"""

# ---------------------------------------------------------------------------
# Downgrade — 1.7 rollback: drop all three tables from all tenant schemas
# ---------------------------------------------------------------------------

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
            'DROP TABLE IF EXISTS %I.document_embeddings CASCADE',
            schema_rec.schema_name
        );
        EXECUTE format(
            'DROP TABLE IF EXISTS %I.document_chunks CASCADE',
            schema_rec.schema_name
        );
        EXECUTE format(
            'DROP TABLE IF EXISTS %I.documents CASCADE',
            schema_rec.schema_name
        );
    END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(text(_ENABLE_PGVECTOR_SQL))
    op.execute(text(_UPGRADE_SQL))


def downgrade() -> None:
    op.execute(text(_DOWNGRADE_SQL))
