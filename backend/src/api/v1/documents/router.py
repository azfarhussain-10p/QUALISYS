"""
QUALISYS — Document API Router
Story: 2-1-document-upload-parsing
AC: #1 — POST /documents: multipart upload, 201 on success, 400 on size/type errors
AC: #3 — GET /documents/{id}: document detail with preview_text, page_count
AC: #5 — GET /documents: paginated list, page/page_size query params
AC: #6 — DELETE /documents/{id}: 204 on success, 404 if not found
AC: #7 — require_project_role("owner", "admin", "qa-automation") on all endpoints
         Cross-project document access → 404; unauthenticated → 401

Endpoints (mounted under /api/v1/projects/{project_id}):
  POST   /documents            — Upload document (multipart/form-data)
  GET    /documents            — List documents (paginated)
  GET    /documents/{doc_id}   — Document detail
  DELETE /documents/{doc_id}   — Delete document + S3 object
"""

import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.documents.schemas import (
    DocumentListItem,
    DocumentResponse,
    FileTooLargeError,
    PaginatedDocumentListResponse,
    UnsupportedFileTypeError,
)
from src.db import get_db
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.document_service import document_service, parse_document_task
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/documents",
    tags=["documents"],
)


# ---------------------------------------------------------------------------
# 3.3 — POST /api/v1/projects/{project_id}/documents
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
async def upload_document(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> DocumentResponse:
    """Upload a document (PDF, DOCX, MD, TXT ≤ 25MB) and queue background parsing."""
    user, tenant_user = auth
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    tenant_id = tenant_user.tenant_id

    try:
        doc = await document_service.upload_document(
            db=db,
            schema_name=schema_name,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user.id,
            file=file,
        )
    except FileTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "FILE_TOO_LARGE", "message": "File size exceeds 25MB limit"},
        )
    except UnsupportedFileTypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "UNSUPPORTED_FILE_TYPE", "message": "Supported formats: PDF, DOCX, MD"},
        )

    # Enqueue background parsing job (Task 5.3 — BackgroundTasks pattern)
    background_tasks.add_task(
        parse_document_task,
        document_id=doc["id"],
        schema_name=schema_name,
        tenant_id=str(tenant_id),
    )

    return DocumentResponse(**doc)


# ---------------------------------------------------------------------------
# 3.4 — GET /api/v1/projects/{project_id}/documents
# ---------------------------------------------------------------------------

@router.get("", response_model=PaginatedDocumentListResponse)
async def list_documents(
    project_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> PaginatedDocumentListResponse:
    """Return paginated list of documents for the project (AC5)."""
    _, tenant_user = auth
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)

    result = await document_service.list_documents(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )

    return PaginatedDocumentListResponse(
        items=[DocumentListItem(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


# ---------------------------------------------------------------------------
# 3.5 — GET /api/v1/projects/{project_id}/documents/{document_id}
# ---------------------------------------------------------------------------

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> DocumentResponse:
    """Return document detail including preview_text, page_count, parse_status (AC3)."""
    _, tenant_user = auth
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)

    doc = await document_service.get_document(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        document_id=document_id,
    )

    if doc is None:
        # Cross-project access returns 404 (AC7)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentResponse(**doc)


# ---------------------------------------------------------------------------
# 3.6 — DELETE /api/v1/projects/{project_id}/documents/{document_id}
# ---------------------------------------------------------------------------

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> None:
    """Delete document record and S3 object (AC6). Returns 204 on success."""
    user, tenant_user = auth
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    tenant_id = tenant_user.tenant_id

    deleted = await document_service.delete_document(
        db=db,
        schema_name=schema_name,
        tenant_id=tenant_id,
        project_id=project_id,
        document_id=document_id,
        user_id=user.id,
    )

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
