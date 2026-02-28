"""
QUALISYS — Embedding Service
Story: 2-2-vector-embeddings-generation
AC: #5 — chunk_text(): 1000-token windows with 200-token overlap → document_chunks
AC: #6 — generate_and_store(): OpenAI text-embedding-ada-002 (1536-dim) → document_embeddings
AC: #7 — progress logging: "Processing chunk {n} of {total}"
AC: #8 — token budget: consume_tokens() after each embedding batch

Pattern compliance (C2 Spike Contract — pgvector_pattern.py):
  - INSERT uses CAST(:embedding AS vector) — asyncpg cannot serialize lists natively
  - cosine ivfflat index already created in migration 013

Security (C1):
  - All SQL uses text() with :params — no user data in f-string interpolation
  - schema_name always double-quoted; no tenant data appended to SQL strings
"""

from __future__ import annotations

import uuid
from typing import Any

import tiktoken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.services.token_budget_service import token_budget_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMBEDDING_MODEL    = "text-embedding-ada-002"
_TIKTOKEN_ENCODING  = "cl100k_base"   # encoding used by ada-002
_CHUNK_SIZE_TOKENS  = 1_000
_CHUNK_OVERLAP      = 200
_CHUNK_STEP         = _CHUNK_SIZE_TOKENS - _CHUNK_OVERLAP  # 800 tokens
_BATCH_SIZE         = 100              # max chunks per OpenAI embeddings call (C5)


# ---------------------------------------------------------------------------
# EmbeddingService
# ---------------------------------------------------------------------------

class EmbeddingService:
    """
    Chunks document text and generates OpenAI embeddings stored via pgvector.
    Designed to be called from parse_document() background task after parse completes.
    """

    # ------------------------------------------------------------------
    # AC-05: Text chunking
    # ------------------------------------------------------------------

    def _chunk_text(
        self,
        text: str,
        chunk_size: int = _CHUNK_SIZE_TOKENS,
        overlap: int = _CHUNK_OVERLAP,
    ) -> list[dict[str, Any]]:
        """
        Tokenise `text` with tiktoken cl100k_base and produce sliding-window chunks.
        Each chunk dict: {"content": str, "token_count": int, "chunk_index": int}
        Returns [] for empty/whitespace-only input.
        """
        if not text or not text.strip():
            return []

        enc    = tiktoken.get_encoding(_TIKTOKEN_ENCODING)
        tokens = enc.encode(text)

        if not tokens:
            return []

        step   = chunk_size - overlap  # 800 tokens
        chunks = []
        idx    = 0

        for start in range(0, len(tokens), step):
            window = tokens[start : start + chunk_size]
            if not window:
                break
            content = enc.decode(window)
            if content.strip():
                chunks.append({
                    "content":     content,
                    "token_count": len(window),
                    "chunk_index": idx,
                })
                idx += 1

        return chunks

    # ------------------------------------------------------------------
    # AC-06 + AC-07 + AC-08: Generate embeddings and store
    # ------------------------------------------------------------------

    async def generate_and_store(
        self,
        db:           AsyncSession,
        schema_name:  str,
        tenant_id:    str,
        document_id:  str,
        parsed_text:  str,
    ) -> int:
        """
        Chunk `parsed_text`, generate OpenAI embeddings, insert document_chunks +
        document_embeddings rows, and consume budget tokens.

        Idempotent (C3): if document_chunks already exist for this document, skip.
        Returns chunk_count (0 if text empty or already processed).
        """
        # C3 — Idempotency gate: skip if already embedded
        existing = await db.execute(
            text(
                f'SELECT COUNT(*) FROM "{schema_name}".document_chunks '
                f'WHERE document_id = :doc_id'
            ),
            {"doc_id": document_id},
        )
        existing_count = existing.scalar() or 0
        if existing_count > 0:
            logger.info(
                "embedding: chunks already exist — skipping",
                document_id=document_id,
                existing_count=existing_count,
            )
            return existing_count

        # AC-05: Chunk text
        chunks = self._chunk_text(parsed_text)
        if not chunks:
            logger.info(
                "embedding: no chunks produced (empty text)",
                document_id=document_id,
            )
            return 0

        total_chunks = len(chunks)
        logger.info(
            "embedding: starting",
            document_id=document_id,
            total_chunks=total_chunks,
        )

        # AC-05: Insert document_chunks rows (all at once)
        chunk_ids: list[str] = []
        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            await db.execute(
                text(
                    f'INSERT INTO "{schema_name}".document_chunks '
                    f'(id, document_id, chunk_index, content, token_count) '
                    f'VALUES (:id, :doc_id, :idx, :content, :token_count)'
                ),
                {
                    "id":          chunk_id,
                    "doc_id":      document_id,
                    "idx":         chunk["chunk_index"],
                    "content":     chunk["content"],
                    "token_count": chunk["token_count"],
                },
            )
        await db.commit()

        # AC-06 + AC-07: Batch embedding calls, progress logging
        total_tokens_used = 0

        for batch_start in range(0, total_chunks, _BATCH_SIZE):
            batch_end    = min(batch_start + _BATCH_SIZE, total_chunks)
            batch_chunks = chunks[batch_start:batch_end]
            batch_ids    = chunk_ids[batch_start:batch_end]

            # AC-07: Progress log per batch
            logger.info(
                f"Processing chunk {batch_start + 1} of {total_chunks}",
                document_id=document_id,
                batch_start=batch_start + 1,
                batch_end=batch_end,
            )

            # AC-06: Call OpenAI embeddings API
            embeddings, tokens_used = await self._call_openai_embeddings(
                [c["content"] for c in batch_chunks]
            )

            # Insert document_embeddings rows — CAST(:embedding AS vector) per pgvector pattern
            for emb_vec, chunk_id in zip(embeddings, batch_ids):
                emb_str = "[" + ",".join(str(v) for v in emb_vec) + "]"
                await db.execute(
                    text(
                        f'INSERT INTO "{schema_name}".document_embeddings '
                        f'(id, chunk_id, embedding) '
                        f"VALUES (:id, :chunk_id, CAST(:embedding AS vector))"
                    ),
                    {
                        "id":        str(uuid.uuid4()),
                        "chunk_id":  chunk_id,
                        "embedding": emb_str,
                    },
                )

            await db.commit()

            # AC-08: Consume budget tokens
            total_tokens_used += tokens_used
            await token_budget_service.consume_tokens(tenant_id, tokens_used)

        logger.info(
            "embedding: completed",
            document_id=document_id,
            chunk_count=total_chunks,
            total_tokens_used=total_tokens_used,
        )
        return total_chunks

    async def _call_openai_embeddings(
        self, texts: list[str]
    ) -> tuple[list[list[float]], int]:
        """
        Call OpenAI text-embedding-ada-002 for a batch of texts.
        Returns (list_of_embedding_vectors, tokens_used).
        Deferred import keeps openai out of test collection scope (C6).
        """
        import openai  # deferred — not installed in all test environments

        client   = openai.AsyncOpenAI()
        response = await client.embeddings.create(
            model=_EMBEDDING_MODEL,
            input=texts,
        )

        embeddings  = [item.embedding for item in response.data]
        tokens_used = response.usage.total_tokens if response.usage else sum(len(t.split()) for t in texts)

        return embeddings, tokens_used


# Module-level singleton
embedding_service = EmbeddingService()
