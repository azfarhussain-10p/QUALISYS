"""
QUALISYS — pgvector Pattern Spike
Epic 2 / C2 (Retro 2026-02-26): Approved pattern for vector embedding storage and search.

CONTRACT — every vector operation in Epic 2 MUST follow this pattern:

INSERT:
  insert_embedding(db, schema_name, chunk_id, embedding)
  - embedding: list[float] of exactly 1536 dimensions (text-embedding-ada-002)
  - Uses schema-qualified table: "{schema_name}".document_embeddings
  - Uses SQLAlchemy text() with bound parameters — NO f-string interpolation of values

SEARCH:
  similarity_search(db, schema_name, query_embedding, limit) -> list[ChunkMatch]
  - Uses <=> operator (cosine distance, requires ivfflat index with vector_cosine_ops)
  - Joins document_chunks for text content; returns ordered by similarity DESC
  - limit: 1–20 (enforced in function; callers should not exceed 10 for performance)

Tenant isolation:
  - schema_name MUST be derived via slug_to_schema_name(current_tenant_slug.get())
  - NEVER pass a raw string literal as schema_name from caller code
  - Table names are schema-qualified and double-quoted to prevent identifier injection

Index (migration 013):
  CREATE INDEX idx_document_embeddings_vector
      ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Expected embedding dimensionality for OpenAI text-embedding-ada-002
_EXPECTED_DIMS = 1536
_MAX_SEARCH_LIMIT = 20


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ChunkMatch:
    """A document chunk returned by similarity_search(), ordered by relevance."""
    chunk_id:    uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content:     str
    distance:    float  # cosine distance (0.0 = identical, 2.0 = opposite)

    @property
    def similarity(self) -> float:
        """Convert cosine distance to similarity score [0, 1]."""
        return 1.0 - (self.distance / 2.0)


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------

async def insert_embedding(
    db:          AsyncSession,
    schema_name: str,
    chunk_id:    uuid.UUID,
    embedding:   list[float],
) -> uuid.UUID:
    """
    Insert a single embedding vector for a document chunk.

    Args:
        db:          Tenant-scoped AsyncSession.
        schema_name: Pre-validated schema name from slug_to_schema_name().
        chunk_id:    UUID of the document_chunks row this embedding belongs to.
        embedding:   1536-dimensional float list from text-embedding-ada-002.

    Returns:
        UUID of the newly created document_embeddings row.

    Raises:
        ValueError: If embedding dimensionality != 1536.
    """
    if len(embedding) != _EXPECTED_DIMS:
        raise ValueError(
            f"Embedding must have {_EXPECTED_DIMS} dimensions; "
            f"got {len(embedding)}."
        )

    # Cast to pgvector type via ::vector — SQLAlchemy text() with bound param
    sql = text(f"""
        INSERT INTO "{schema_name}".document_embeddings (chunk_id, embedding)
        VALUES (:chunk_id, :embedding::vector)
        RETURNING id
    """)

    row = await db.execute(
        sql,
        {
            "chunk_id":  str(chunk_id),
            "embedding": "[" + ",".join(str(v) for v in embedding) + "]",
        },
    )
    embedding_id = row.scalar_one()
    return uuid.UUID(str(embedding_id))


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------

async def similarity_search(
    db:             AsyncSession,
    schema_name:    str,
    query_embedding: list[float],
    limit:          int = 5,
) -> list[ChunkMatch]:
    """
    Find the top-N most similar chunks to query_embedding using cosine distance.

    Args:
        db:              Tenant-scoped AsyncSession.
        schema_name:     Pre-validated schema name from slug_to_schema_name().
        query_embedding: 1536-dimensional query vector.
        limit:           Number of results to return (1–20, default 5).

    Returns:
        List of ChunkMatch ordered by similarity descending (most similar first).

    Raises:
        ValueError: If embedding dimensionality != 1536 or limit out of range.
    """
    if len(query_embedding) != _EXPECTED_DIMS:
        raise ValueError(
            f"Query embedding must have {_EXPECTED_DIMS} dimensions; "
            f"got {len(query_embedding)}."
        )
    if not (1 <= limit <= _MAX_SEARCH_LIMIT):
        raise ValueError(f"limit must be between 1 and {_MAX_SEARCH_LIMIT}.")

    query_vec_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    # <=> is the pgvector cosine distance operator (requires ivfflat vector_cosine_ops index)
    sql = text(f"""
        SELECT
            dc.id            AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            de.embedding <=> :query_embedding::vector AS distance
        FROM "{schema_name}".document_embeddings de
        JOIN "{schema_name}".document_chunks dc ON dc.id = de.chunk_id
        ORDER BY distance ASC
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {"query_embedding": query_vec_str, "limit": limit},
    )
    rows = result.mappings().all()

    return [
        ChunkMatch(
            chunk_id=uuid.UUID(str(row["chunk_id"])),
            document_id=uuid.UUID(str(row["document_id"])),
            chunk_index=int(row["chunk_index"]),
            content=str(row["content"]),
            distance=float(row["distance"]),
        )
        for row in rows
    ]
