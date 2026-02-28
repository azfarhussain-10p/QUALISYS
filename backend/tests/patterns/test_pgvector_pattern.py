"""
Contract tests for pgvector_pattern.py — Epic 2 / C2 (Retro 2026-02-26)

These tests verify INTERFACE CONTRACTS and BEHAVIOUR GUARANTEES of the pgvector pattern.
No real database connection is made. SQLAlchemy sessions are fully mocked.

Contracts verified:
  - insert_embedding: SQL uses schema-qualified table name (tenant isolation)
  - insert_embedding: embedding cast to ::vector in SQL (pgvector type)
  - insert_embedding: wrong dimensionality raises ValueError
  - similarity_search: SQL uses <=> cosine distance operator
  - similarity_search: SQL uses schema-qualified tables (tenant isolation)
  - similarity_search: out-of-range limit raises ValueError
  - similarity_search: wrong dimensionality raises ValueError
  - ChunkMatch.similarity: converts cosine distance to [0, 1] correctly
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.patterns.pgvector_pattern import (
    ChunkMatch,
    _EXPECTED_DIMS,
    _MAX_SEARCH_LIMIT,
    insert_embedding,
    similarity_search,
)

SCHEMA_NAME = "tenant_acme_corp"
CHUNK_ID    = uuid.uuid4()
EMBEDDING   = [0.1] * _EXPECTED_DIMS  # valid 1536-dim vector


# ---------------------------------------------------------------------------
# insert_embedding — schema isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_uses_schema_qualified_table():
    # Proves: INSERT SQL contains the tenant schema name to enforce row isolation
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = str(uuid.uuid4())
    mock_db.execute.return_value = mock_result

    await insert_embedding(mock_db, SCHEMA_NAME, CHUNK_ID, EMBEDDING)

    call_args = mock_db.execute.call_args
    sql_text  = str(call_args[0][0])
    assert f'"{SCHEMA_NAME}"' in sql_text, "INSERT must use double-quoted schema name"
    assert "document_embeddings" in sql_text


@pytest.mark.asyncio
async def test_insert_casts_embedding_to_vector_type():
    # Proves: embedding is cast via ::vector so pgvector interprets it correctly
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = str(uuid.uuid4())
    mock_db.execute.return_value = mock_result

    await insert_embedding(mock_db, SCHEMA_NAME, CHUNK_ID, EMBEDDING)

    sql_text = str(mock_db.execute.call_args[0][0])
    assert "::vector" in sql_text, "Embedding parameter must be cast to ::vector type"


@pytest.mark.asyncio
async def test_insert_returns_uuid():
    # Proves: return value is a UUID (the new document_embeddings row id)
    mock_db = AsyncMock()
    new_id   = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = str(new_id)
    mock_db.execute.return_value = mock_result

    result = await insert_embedding(mock_db, SCHEMA_NAME, CHUNK_ID, EMBEDDING)

    assert isinstance(result, uuid.UUID)
    assert result == new_id


# ---------------------------------------------------------------------------
# insert_embedding — dimension validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_insert_raises_on_wrong_dimensions():
    # Proves: passing a non-1536 embedding raises ValueError before any DB call
    mock_db = AsyncMock()
    bad_embedding = [0.1] * 512  # wrong dimension

    with pytest.raises(ValueError, match=str(_EXPECTED_DIMS)):
        await insert_embedding(mock_db, SCHEMA_NAME, CHUNK_ID, bad_embedding)

    mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# similarity_search — schema isolation + operator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_similarity_search_uses_schema_qualified_tables():
    # Proves: SELECT SQL uses tenant schema for both document_embeddings and document_chunks
    mock_db      = AsyncMock()
    mock_result  = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    await similarity_search(mock_db, SCHEMA_NAME, EMBEDDING, limit=3)

    sql_text = str(mock_db.execute.call_args[0][0])
    assert f'"{SCHEMA_NAME}".document_embeddings' in sql_text
    assert f'"{SCHEMA_NAME}".document_chunks'     in sql_text


@pytest.mark.asyncio
async def test_similarity_search_uses_cosine_distance_operator():
    # Proves: <=> operator is used (cosine distance), not <-> (L2) or <#> (inner product)
    mock_db     = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    await similarity_search(mock_db, SCHEMA_NAME, EMBEDDING)

    sql_text = str(mock_db.execute.call_args[0][0])
    assert "<=>" in sql_text, "Must use <=> cosine distance operator for ivfflat index"


@pytest.mark.asyncio
async def test_similarity_search_returns_chunk_matches_in_order():
    # Proves: results are returned as ChunkMatch instances with all required fields
    mock_db     = AsyncMock()
    chunk_id_1  = uuid.uuid4()
    doc_id_1    = uuid.uuid4()

    mock_rows = [
        {
            "chunk_id":    str(chunk_id_1),
            "document_id": str(doc_id_1),
            "chunk_index": 0,
            "content":     "requirement: user must log in",
            "distance":    0.12,
        }
    ]
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = mock_rows
    mock_db.execute.return_value = mock_result

    results = await similarity_search(mock_db, SCHEMA_NAME, EMBEDDING, limit=1)

    assert len(results) == 1
    m = results[0]
    assert isinstance(m, ChunkMatch)
    assert m.chunk_id    == chunk_id_1
    assert m.document_id == doc_id_1
    assert m.chunk_index == 0
    assert m.content     == "requirement: user must log in"
    assert m.distance    == pytest.approx(0.12)


# ---------------------------------------------------------------------------
# similarity_search — limit validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_similarity_search_raises_on_zero_limit():
    # Proves: limit=0 is rejected before DB call (boundary guard)
    mock_db = AsyncMock()
    with pytest.raises(ValueError):
        await similarity_search(mock_db, SCHEMA_NAME, EMBEDDING, limit=0)
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_similarity_search_raises_on_over_max_limit():
    # Proves: limit > MAX_SEARCH_LIMIT is rejected (performance guard)
    mock_db = AsyncMock()
    with pytest.raises(ValueError):
        await similarity_search(mock_db, SCHEMA_NAME, EMBEDDING, limit=_MAX_SEARCH_LIMIT + 1)
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_similarity_search_raises_on_wrong_dimensions():
    # Proves: query embedding dimensionality is validated before DB call
    mock_db = AsyncMock()
    with pytest.raises(ValueError, match=str(_EXPECTED_DIMS)):
        await similarity_search(mock_db, SCHEMA_NAME, [0.1] * 768)
    mock_db.execute.assert_not_called()


# ---------------------------------------------------------------------------
# ChunkMatch.similarity property
# ---------------------------------------------------------------------------

def test_chunk_match_similarity_is_one_minus_half_distance():
    # Proves: similarity property converts cosine distance [0,2] to [0,1] correctly
    # distance=0.0 → similarity=1.0 (identical vectors)
    # distance=1.0 → similarity=0.5 (orthogonal vectors)
    # distance=2.0 → similarity=0.0 (opposite vectors)
    m = ChunkMatch(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        content="test",
        distance=0.4,
    )
    assert m.similarity == pytest.approx(0.8)


def test_chunk_match_similarity_at_zero_distance():
    # Proves: perfect match (distance=0) yields similarity=1.0
    m = ChunkMatch(uuid.uuid4(), uuid.uuid4(), 0, "x", distance=0.0)
    assert m.similarity == pytest.approx(1.0)
