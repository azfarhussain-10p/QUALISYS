"""
QUALISYS — Document Service
Story: 2-1-document-upload-parsing + 2-2-vector-embeddings-generation
AC: #1 — upload_document(): file size + MIME validation, S3 upload, DB insert, background parse
AC: #2 — parse_document(): arq-style background function; PDF/DOCX/MD/TXT parsing; parse_status transitions
AC: #3 — get_document(): returns single document row; 404 if wrong project
AC: #4 — parse failure for empty PDF text; generic error for corrupt files
AC: #5 — list_documents(): paginated, created_at DESC, preview_text truncated to 100 chars
AC: #6 — delete_document(): best-effort S3 delete, CASCADE DB delete
AC: #8 — S3 key: documents/{tenant_id}/{project_id}/{document_id}/{sanitized_filename}
AC: #9 — AuditService.log_action_async() for document.uploaded and document.deleted
Story 2-2 AC: #5,#6,#7,#8 — embedding_service.generate_and_store() called after parse

Security (C1, C2):
  - All queries use SQLAlchemy text() with named :params (no f-string on user data)
  - Schema name always via slug_to_schema_name(current_tenant_slug.get()), double-quoted
  - tenant_id always from JWT context (TenantUser), never from request body
"""

import io
import math
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from docx import Document
from fastapi import UploadFile
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.documents.schemas import FileTooLargeError, UnsupportedFileTypeError
from src.config import get_settings
from src.db import AsyncSessionLocal
from src.logger import logger
from src.services.audit_service import AuditService
from src.services.embedding_service import embedding_service

settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

# Accepted MIME types and their canonical file_type strings
_ACCEPTED_MIME_TYPES: dict[str, str] = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "md",
    "text/markdown": "md",
}

_ACCEPTED_EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".md": "md",
    ".txt": "md",  # stored as md type
}

_audit_service = AuditService()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_filename(filename: str) -> str:
    """Replace spaces with _, strip non-ASCII characters (AC8)."""
    # Normalize unicode → ASCII where possible
    normalized = unicodedata.normalize("NFKD", filename)
    ascii_only = normalized.encode("ascii", errors="ignore").decode("ascii")
    # Replace spaces with underscore
    sanitized = ascii_only.replace(" ", "_")
    # Remove any characters that aren't alphanumeric, underscore, hyphen, or dot
    sanitized = re.sub(r"[^\w.\-]", "", sanitized)
    return sanitized or "document"


def _make_s3_client():
    """Create boto3 S3 client using settings credentials (mirrors export_service pattern)."""
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def _truncate_to_word_boundary(text: str, limit: int) -> str:
    """Truncate text to last word boundary at or before `limit` chars (C7)."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def _detect_file_type(filename: str, content_type: str) -> str:
    """
    Detect file type from extension (primary) and MIME type (fallback).
    Returns canonical type: 'pdf' | 'docx' | 'md'.
    Raises UnsupportedFileTypeError if not accepted.
    """
    ext = os.path.splitext(filename.lower())[1]
    if ext in _ACCEPTED_EXTENSIONS:
        return _ACCEPTED_EXTENSIONS[ext]
    # Fallback: check MIME type
    if content_type in _ACCEPTED_MIME_TYPES:
        return _ACCEPTED_MIME_TYPES[content_type]
    raise UnsupportedFileTypeError(
        f"Unsupported file type: {ext or content_type}"
    )


# ---------------------------------------------------------------------------
# DocumentService
# ---------------------------------------------------------------------------

class DocumentService:
    """
    Handles document upload, background parsing, listing, and deletion.
    All data operations are tenant-schema-scoped.
    """

    # ------------------------------------------------------------------
    # 2.2 — upload_document
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
    ) -> dict[str, Any]:
        """
        Validate, store in S3, insert DB record, enqueue background parse.
        Returns document dict with parse_status='pending'.

        Raises:
            FileTooLargeError if file exceeds 25MB (AC1)
            UnsupportedFileTypeError if extension/MIME not accepted (AC1)
        """
        # Validate file type (AC1) — check before reading bytes
        file_type = _detect_file_type(
            file.filename or "upload", file.content_type or ""
        )

        # Read file bytes — needed for size check and S3 upload
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # Validate file size ≤ 25MB (AC1)
        if file_size > _MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(
                f"File size {file_size} exceeds 25MB limit"
            )

        # Sanitize filename (AC8)
        original_filename = file.filename or "upload"
        sanitized_filename = _sanitize_filename(original_filename)

        # Generate document UUID (needed for S3 key before DB insert)
        document_id = uuid.uuid4()

        # Build S3 key: documents/{tenant_id}/{project_id}/{document_id}/{sanitized_filename}
        s3_key = f"documents/{tenant_id}/{project_id}/{document_id}/{sanitized_filename}"

        # Upload to S3 (AC8)
        if settings.s3_bucket_name:
            try:
                s3_client = _make_s3_client()
                s3_client.put_object(
                    Bucket=settings.s3_bucket_name,
                    Key=s3_key,
                    Body=file_bytes,
                    ContentType=file.content_type or "application/octet-stream",
                )
            except ClientError as exc:
                logger.error(
                    "S3 upload failed during document upload",
                    document_id=str(document_id),
                    exc=str(exc),
                )
                raise
        else:
            logger.warning(
                "S3 not configured — document not persisted to object storage",
                document_id=str(document_id),
            )

        # Insert documents record with parse_status='pending'
        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".documents '
                "(id, project_id, filename, file_type, file_size_bytes, s3_key, "
                " parse_status, created_by) "
                "VALUES (:id, :project_id, :filename, :file_type, :file_size_bytes, "
                "        :s3_key, 'pending', :created_by)"
            ),
            {
                "id": str(document_id),
                "project_id": str(project_id),
                "filename": original_filename,
                "file_type": file_type,
                "file_size_bytes": file_size,
                "s3_key": s3_key,
                "created_by": str(user_id),
            },
        )
        await db.commit()

        logger.info(
            "Document uploaded",
            document_id=str(document_id),
            project_id=str(project_id),
            file_type=file_type,
            file_size=file_size,
        )

        # Fire-and-forget audit log (AC9)
        await _audit_service.log_action_async(
            schema_name=schema_name,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="document.uploaded",
            resource_type="document",
            resource_id=document_id,
        )

        return {
            "id": str(document_id),
            "filename": original_filename,
            "file_type": file_type,
            "file_size_bytes": file_size,
            "parse_status": "pending",
            "preview_text": None,
            "page_count": None,
            "chunk_count": 0,
            "error_message": None,
            "created_by": str(user_id),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 2.3 — parse_document (background task body)
    # ------------------------------------------------------------------

    async def parse_document(
        self,
        document_id: str,
        schema_name: str,
        tenant_id: str,
    ) -> None:
        """
        Background parsing job — idempotent (C4).
        Downloads file from S3, parses by file_type, updates documents row.

        Called as a FastAPI BackgroundTasks callback (opens its own DB session).
        """
        async with AsyncSessionLocal() as db:
            try:
                # Idempotency gate (C4): skip if already processing/completed/failed
                result = await db.execute(
                    text(
                        f'SELECT id, parse_status, s3_key, file_type '
                        f'FROM "{schema_name}".documents '
                        f'WHERE id = :id'
                    ),
                    {"id": document_id},
                )
                row = result.mappings().fetchone()
                if row is None:
                    logger.warning(
                        "parse_document: document not found",
                        document_id=document_id,
                    )
                    return

                if row["parse_status"] != "pending":
                    logger.info(
                        "parse_document: already processed, skipping",
                        document_id=document_id,
                        parse_status=row["parse_status"],
                    )
                    return

                s3_key: str = row["s3_key"]
                file_type: str = row["file_type"]

                # Mark processing (AC2)
                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".documents '
                        "SET parse_status = 'processing', updated_at = NOW() "
                        "WHERE id = :id"
                    ),
                    {"id": document_id},
                )
                await db.commit()

                # Download file from S3
                file_bytes = self._download_from_s3(s3_key)

                # Parse by file type (AC2)
                parsed_text, page_count = self._parse_file(file_bytes, file_type)

                # Empty text check (AC4 — scanned PDF)
                if not parsed_text or not parsed_text.strip():
                    if file_type == "pdf":
                        error_msg = (
                            "Could not extract text from this PDF. "
                            "Try uploading a Markdown or Word version of your document for best results."
                        )
                    else:
                        error_msg = "Could not extract any text from the uploaded file."

                    await db.execute(
                        text(
                            f'UPDATE "{schema_name}".documents '
                            "SET parse_status = 'failed', error_message = :error, updated_at = NOW() "
                            "WHERE id = :id"
                        ),
                        {"error": error_msg, "id": document_id},
                    )
                    await db.commit()
                    logger.info(
                        "parse_document: empty text → failed",
                        document_id=document_id,
                        file_type=file_type,
                    )
                    return

                # Compute preview_text (AC2, C7)
                preview_text = _truncate_to_word_boundary(parsed_text, 500)

                # Write parsed text, preview, page_count; keep status='processing'
                # (status moves to 'completed' only after embedding succeeds — Story 2-2 AC-05/06)
                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".documents '
                        "SET parsed_text = :parsed_text, "
                        "    preview_text = :preview_text, "
                        "    page_count = :page_count, "
                        "    updated_at = NOW() "
                        "WHERE id = :id"
                    ),
                    {
                        "parsed_text": parsed_text,
                        "preview_text": preview_text,
                        "page_count": page_count,
                        "id": document_id,
                    },
                )
                await db.commit()

                logger.info(
                    "parse_document: text extracted, starting embedding",
                    document_id=document_id,
                    file_type=file_type,
                    text_length=len(parsed_text),
                )

                # Story 2-2: Generate embeddings (AC-05, AC-06, AC-07, AC-08)
                chunk_count = await embedding_service.generate_and_store(
                    db=db,
                    schema_name=schema_name,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    parsed_text=parsed_text,
                )

                # Update chunk_count + set status='completed'
                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".documents '
                        "SET parse_status = 'completed', "
                        "    chunk_count = :chunk_count, "
                        "    updated_at = NOW() "
                        "WHERE id = :id"
                    ),
                    {"chunk_count": chunk_count, "id": document_id},
                )
                await db.commit()

                logger.info(
                    "parse_document: completed",
                    document_id=document_id,
                    file_type=file_type,
                    text_length=len(parsed_text),
                    chunk_count=chunk_count,
                )

            except Exception as exc:
                # AC4: generic parse errors → failed + truncated error_message (no stack traces)
                error_msg = str(exc)[:500]
                logger.error(
                    "parse_document: exception",
                    document_id=document_id,
                    exc=str(exc),
                )
                try:
                    await db.execute(
                        text(
                            f'UPDATE "{schema_name}".documents '
                            "SET parse_status = 'failed', error_message = :error, updated_at = NOW() "
                            "WHERE id = :id"
                        ),
                        {"error": error_msg, "id": document_id},
                    )
                    await db.commit()
                except Exception:
                    pass

    def _download_from_s3(self, s3_key: str) -> bytes:
        """Download file bytes from S3 for parsing."""
        if not settings.s3_bucket_name:
            # Dev mode: no S3 — return empty bytes (parse will fail gracefully)
            logger.warning("S3 not configured — parse_document returning empty bytes")
            return b""

        s3_client = _make_s3_client()
        response = s3_client.get_object(Bucket=settings.s3_bucket_name, Key=s3_key)
        return response["Body"].read()

    def _parse_file(self, file_bytes: bytes, file_type: str) -> tuple[str, Optional[int]]:
        """
        Parse file bytes by file_type. Returns (parsed_text, page_count).
        page_count is only populated for PDFs.
        """
        if file_type == "pdf":
            return self._parse_pdf(file_bytes)
        elif file_type == "docx":
            return self._parse_docx(file_bytes), None
        else:
            # MD / TXT — read as UTF-8 (AC2)
            return file_bytes.decode("utf-8", errors="replace"), None

    def _parse_pdf(self, file_bytes: bytes) -> tuple[str, int]:
        """Extract text from PDF using pypdf (AC2, C8). Returns (text, page_count)."""
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        pages_text = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            pages_text.append(extracted)
        full_text = "\n".join(pages_text)
        return full_text, page_count

    def _parse_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX using python-docx (AC2, C9)."""
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

    # ------------------------------------------------------------------
    # 2.4 — get_document
    # ------------------------------------------------------------------

    async def get_document(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> Optional[dict[str, Any]]:
        """
        Fetch single document. Returns None if not found or wrong project (AC3, AC7).
        """
        result = await db.execute(
            text(
                f'SELECT id, project_id, filename, file_type, file_size_bytes, '
                f'parse_status, preview_text, page_count, chunk_count, '
                f'error_message, created_by, created_at '
                f'FROM "{schema_name}".documents '
                f'WHERE id = :id AND project_id = :project_id'
            ),
            {"id": str(document_id), "project_id": str(project_id)},
        )
        row = result.mappings().fetchone()
        if row is None:
            return None

        return {
            "id": str(row["id"]),
            "filename": row["filename"],
            "file_type": row["file_type"],
            "file_size_bytes": row["file_size_bytes"],
            "parse_status": row["parse_status"],
            "preview_text": row["preview_text"],
            "page_count": row["page_count"],
            "chunk_count": row["chunk_count"],
            "error_message": row["error_message"],
            "created_by": str(row["created_by"]),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        }

    # ------------------------------------------------------------------
    # 2.5 — list_documents
    # ------------------------------------------------------------------

    async def list_documents(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        Paginated list of documents for a project, ordered by created_at DESC (AC5).
        preview_text in list view truncated to 100 chars (C7).
        """
        offset = (page - 1) * page_size

        # Total count
        count_result = await db.execute(
            text(
                f'SELECT COUNT(*) FROM "{schema_name}".documents '
                f'WHERE project_id = :project_id'
            ),
            {"project_id": str(project_id)},
        )
        total = count_result.scalar() or 0

        # Paginated rows
        result = await db.execute(
            text(
                f'SELECT id, filename, file_type, file_size_bytes, '
                f'parse_status, preview_text, created_by, created_at '
                f'FROM "{schema_name}".documents '
                f'WHERE project_id = :project_id '
                f'ORDER BY created_at DESC '
                f'LIMIT :limit OFFSET :offset'
            ),
            {"project_id": str(project_id), "limit": page_size, "offset": offset},
        )
        rows = result.mappings().fetchall()

        items = []
        for row in rows:
            # Truncate preview_text to 100 chars in list view (AC5, C7)
            preview = row["preview_text"]
            if preview:
                preview = _truncate_to_word_boundary(preview, 100)

            items.append({
                "id": str(row["id"]),
                "filename": row["filename"],
                "file_type": row["file_type"],
                "file_size_bytes": row["file_size_bytes"],
                "parse_status": row["parse_status"],
                "preview_text": preview,
                "created_by": str(row["created_by"]),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            })

        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # ------------------------------------------------------------------
    # 2.6 — delete_document
    # ------------------------------------------------------------------

    async def delete_document(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """
        Delete document record + best-effort S3 object deletion (AC6, C5).
        CASCADE removes document_chunks and document_embeddings.
        Returns False if document not found.
        """
        # Fetch document to get s3_key (and verify project ownership — AC7)
        result = await db.execute(
            text(
                f'SELECT id, s3_key FROM "{schema_name}".documents '
                f'WHERE id = :id AND project_id = :project_id'
            ),
            {"id": str(document_id), "project_id": str(project_id)},
        )
        row = result.mappings().fetchone()
        if row is None:
            return False

        s3_key: str = row["s3_key"]

        # Best-effort S3 delete (AC6, C5) — log warning on failure, do NOT raise
        if settings.s3_bucket_name:
            try:
                s3_client = _make_s3_client()
                s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
            except ClientError as exc:
                logger.warning(
                    "S3 delete failed (best-effort — DB record still deleted)",
                    document_id=str(document_id),
                    s3_key=s3_key,
                    exc=str(exc),
                )

        # Delete DB record (CASCADE removes document_chunks, document_embeddings — AC6)
        await db.execute(
            text(
                f'DELETE FROM "{schema_name}".documents WHERE id = :id'
            ),
            {"id": str(document_id)},
        )
        await db.commit()

        # Fire-and-forget audit log (AC9)
        await _audit_service.log_action_async(
            schema_name=schema_name,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            action="document.deleted",
            resource_type="document",
            resource_id=document_id,
        )

        logger.info(
            "Document deleted",
            document_id=str(document_id),
            project_id=str(project_id),
        )
        return True


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

document_service = DocumentService()


# ---------------------------------------------------------------------------
# Background task entry point (called via BackgroundTasks.add_task)
# ---------------------------------------------------------------------------

async def parse_document_task(
    document_id: str,
    schema_name: str,
    tenant_id: str,
) -> None:
    """
    Top-level arq-style background function for document parsing (Task 5.3).
    Delegates to document_service.parse_document().
    """
    await document_service.parse_document(
        document_id=document_id,
        schema_name=schema_name,
        tenant_id=tenant_id,
    )
