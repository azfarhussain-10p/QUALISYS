"""
QUALISYS — Document API Schemas
Story: 2-1-document-upload-parsing
AC: #1 — FileTooLargeError (400 FILE_TOO_LARGE), UnsupportedFileTypeError (400 UNSUPPORTED_FILE_TYPE)
AC: #3 — DocumentResponse with preview_text, page_count, parse_status
AC: #5 — DocumentListItem (100-char preview), PaginatedDocumentListResponse
"""

from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Domain errors raised by DocumentService
# ---------------------------------------------------------------------------

class FileTooLargeError(Exception):
    """Raised when uploaded file exceeds 25MB limit (AC1)."""


class UnsupportedFileTypeError(Exception):
    """Raised when uploaded file type is not PDF, DOCX, MD, or TXT (AC1)."""


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    """Full document detail response — AC3, returned from POST (201) and GET detail."""

    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    parse_status: str
    preview_text: Optional[str]
    page_count: Optional[int]
    chunk_count: int
    error_message: Optional[str]
    created_by: str
    created_at: str


class DocumentListItem(BaseModel):
    """Document item in list view — AC5. preview_text truncated to 100 chars."""

    id: str
    filename: str
    file_type: str
    file_size_bytes: int
    parse_status: str
    preview_text: Optional[str]
    created_by: str
    created_at: str


class PaginatedDocumentListResponse(BaseModel):
    """Paginated document list response — AC5."""

    items: List[DocumentListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
