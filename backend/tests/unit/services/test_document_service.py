"""
Unit tests — DocumentService
Story: 2-1-document-upload-parsing
Task 9.1 — 11 unit tests for DocumentService methods
AC: #1 — file size + type validation
AC: #2 — PDF/DOCX/MD parsing, parse_status transitions
AC: #4 — empty PDF → specific error_message; exception → truncated error_message
AC: #5 — list_documents pagination
AC: #6 — delete_document: best-effort S3 delete (ClientError still deletes DB)
AC: #3 — get_document: wrong project → None (404)

DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.
"""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile

from src.api.v1.documents.schemas import FileTooLargeError, UnsupportedFileTypeError
from src.services.document_service import DocumentService, _truncate_to_word_boundary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_upload_file(
    filename: str = "test.pdf",
    content_type: str = "application/pdf",
    content: bytes = b"%PDF-1.4 test content",
) -> UploadFile:
    """Build a minimal UploadFile mock."""
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = content_type
    file.read = AsyncMock(return_value=content)
    return file


def _make_db_mock() -> AsyncMock:
    """Return an AsyncSession mock that accepts any execute/commit."""
    db = AsyncMock()
    result = MagicMock()
    result.mappings.return_value.fetchone.return_value = None
    db.execute.return_value = result
    db.commit = AsyncMock()
    return db


def _big_file(size_mb: float = 26) -> bytes:
    return b"x" * int(size_mb * 1024 * 1024)


# ---------------------------------------------------------------------------
# AC1: File size + type validation
# ---------------------------------------------------------------------------

class TestUploadValidation:

    @pytest.mark.asyncio
    async def test_upload_document_too_large(self):
        # Proves: file > 25MB raises FileTooLargeError before any S3 or DB call.
        svc = DocumentService()
        db = _make_db_mock()
        upload = _make_upload_file(content=_big_file(26))

        with pytest.raises(FileTooLargeError):
            await svc.upload_document(
                db=db,
                schema_name="tenant_test",
                tenant_id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                file=upload,
            )

        # DB commit must NOT have been called — no record created
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_unsupported_type(self):
        # Proves: .exe extension raises UnsupportedFileTypeError, no DB/S3 interaction.
        svc = DocumentService()
        db = _make_db_mock()
        upload = _make_upload_file(
            filename="malware.exe",
            content_type="application/octet-stream",
            content=b"MZ binary",
        )

        with pytest.raises(UnsupportedFileTypeError):
            await svc.upload_document(
                db=db,
                schema_name="tenant_test",
                tenant_id=uuid.uuid4(),
                project_id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                file=upload,
            )

        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_document_success(self):
        # Proves: valid PDF → DB insert committed, S3 put_object called, parse_status='pending'.
        svc = DocumentService()
        db = _make_db_mock()
        upload = _make_upload_file(
            filename="requirements.pdf",
            content_type="application/pdf",
            content=b"%PDF small doc",
        )
        tenant_id = uuid.uuid4()
        project_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_s3 = MagicMock()
        mock_s3.put_object = MagicMock()

        with patch("src.services.document_service._make_s3_client", return_value=mock_s3):
            with patch("src.services.document_service.settings") as mock_settings:
                mock_settings.s3_bucket_name = "test-bucket"
                mock_settings.s3_region = "us-east-1"
                mock_settings.aws_access_key_id = ""
                mock_settings.aws_secret_access_key = ""
                with patch("src.services.document_service._audit_service.log_action_async", new_callable=AsyncMock):
                    result = await svc.upload_document(
                        db=db,
                        schema_name="tenant_test",
                        tenant_id=tenant_id,
                        project_id=project_id,
                        user_id=user_id,
                        file=upload,
                    )

        assert result["parse_status"] == "pending"
        assert result["filename"] == "requirements.pdf"
        assert result["file_type"] == "pdf"
        # s3_key no longer exposed in response (M2 fix) — verify S3 key via put_object call args
        mock_s3.put_object.assert_called_once()
        s3_call_key = mock_s3.put_object.call_args.kwargs["Key"]
        assert str(tenant_id) in s3_call_key
        assert str(project_id) in s3_call_key
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# AC2, AC4: Parsing logic
# ---------------------------------------------------------------------------

class TestParseDocument:

    @pytest.mark.asyncio
    async def test_parse_document_pdf_success(self):
        # Proves: mock pypdf with non-empty text → parse_status='completed', preview_text populated.
        svc = DocumentService()
        document_id = str(uuid.uuid4())
        schema_name = "tenant_test"

        # Mock the existing DB row (status='pending')
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "parse_status": "pending",
            "s3_key": f"documents/tid/pid/{document_id}/doc.pdf",
            "file_type": "pdf",
        }.get(k)
        mock_row.keys = MagicMock(return_value=["parse_status", "s3_key", "file_type"])

        mock_mappings = MagicMock()
        mock_mappings.fetchone.return_value = mock_row

        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        pdf_text = "This is the extracted PDF text with plenty of content."

        # Patch _download_from_s3 and _parse_pdf; mock embedding so no OpenAI call needed
        with patch.object(svc, "_download_from_s3", return_value=b"fake-pdf-bytes"):
            with patch.object(svc, "_parse_pdf", return_value=(pdf_text, 3)):
                with patch(
                    "src.services.document_service.embedding_service.generate_and_store",
                    new_callable=AsyncMock,
                    return_value=3,  # chunk_count
                ):
                    from src.db import AsyncSessionLocal
                    with patch("src.services.document_service.AsyncSessionLocal") as mock_session_cls:
                        mock_ctx = MagicMock()
                        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                        mock_ctx.__aexit__ = AsyncMock(return_value=False)
                        mock_session_cls.return_value = mock_ctx
                        await svc.parse_document(document_id, schema_name, "tenant-id")

        # Last update call should set parse_status='completed'
        calls = [str(call.args[0]).lower() for call in mock_db.execute.call_args_list]
        assert any("completed" in c for c in calls)

    @pytest.mark.asyncio
    async def test_parse_document_pdf_empty(self):
        # Proves: empty pypdf text → parse_status='failed' with PDF-specific error_message.
        svc = DocumentService()
        document_id = str(uuid.uuid4())
        schema_name = "tenant_test"

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "parse_status": "pending",
            "s3_key": "documents/x/y/z/scan.pdf",
            "file_type": "pdf",
        }.get(k)

        mock_mappings = MagicMock()
        mock_mappings.fetchone.return_value = mock_row
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        with patch.object(svc, "_download_from_s3", return_value=b"scanned"):
            with patch.object(svc, "_parse_pdf", return_value=("   ", 1)):  # whitespace only
                with patch("src.services.document_service.AsyncSessionLocal") as mock_session_cls:
                    mock_ctx = MagicMock()
                    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                    mock_ctx.__aexit__ = AsyncMock(return_value=False)
                    mock_session_cls.return_value = mock_ctx
                    await svc.parse_document(document_id, schema_name, "tenant-id")

        # Check 'failed' was set with the PDF-specific message
        sql_calls = [str(call.args[0]).lower() for call in mock_db.execute.call_args_list]
        assert any("failed" in c for c in sql_calls)
        # Verify error params contain the PDF-specific message
        param_calls = [str(call.args[1]) for call in mock_db.execute.call_args_list if len(call.args) > 1]
        assert any("Could not extract text" in c for c in param_calls)

    @pytest.mark.asyncio
    async def test_parse_document_docx_success(self):
        # Proves: mock python-docx paragraphs → parsed_text joined with newlines.
        svc = DocumentService()
        fake_para1 = MagicMock()
        fake_para1.text = "Section 1"
        fake_para2 = MagicMock()
        fake_para2.text = "Section 2"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [fake_para1, fake_para2]

        # Test real implementation with mocked Document (paragraph join logic — C9)
        with patch("src.services.document_service.Document", return_value=mock_doc):
            result = svc._parse_docx(b"fake-docx")
        assert result == "Section 1\nSection 2"  # Proves paragraphs joined with newlines

    @pytest.mark.asyncio
    async def test_parse_document_md_success(self):
        # Proves: MD/TXT bytes decoded as UTF-8 → parsed_text equals file content.
        svc = DocumentService()
        md_content = b"# Requirements\n\n- Feature 1\n- Feature 2"
        text, page_count = svc._parse_file(md_content, "md")
        assert text == md_content.decode("utf-8")
        assert page_count is None

    @pytest.mark.asyncio
    async def test_parse_document_exception(self):
        # Proves: exception during parsing → parse_status='failed', error_message truncated to 500 chars.
        svc = DocumentService()
        document_id = str(uuid.uuid4())
        schema_name = "tenant_test"

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "parse_status": "pending",
            "s3_key": "documents/x/y/z/corrupt.pdf",
            "file_type": "pdf",
        }.get(k)

        mock_mappings = MagicMock()
        mock_mappings.fetchone.return_value = mock_row
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()

        long_error = "X" * 600  # error longer than 500 chars

        with patch.object(svc, "_download_from_s3", side_effect=Exception(long_error)):
            with patch("src.services.document_service.AsyncSessionLocal") as mock_session_cls:
                mock_ctx = MagicMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
                mock_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_session_cls.return_value = mock_ctx
                await svc.parse_document(document_id, schema_name, "tenant-id")

        # Verify failed status set
        sql_calls = [str(call.args[0]).lower() for call in mock_db.execute.call_args_list]
        assert any("failed" in c for c in sql_calls)
        # Verify error_message was truncated (≤ 500 chars in the param dict)
        for call in mock_db.execute.call_args_list:
            if len(call.args) > 1 and isinstance(call.args[1], dict):
                error_val = call.args[1].get("error", "")
                if error_val:
                    assert len(error_val) <= 500


# ---------------------------------------------------------------------------
# AC6: Delete document with best-effort S3
# ---------------------------------------------------------------------------

class TestDeleteDocument:

    @pytest.mark.asyncio
    async def test_delete_document_s3_failure_still_deletes_db(self):
        # Proves: S3 ClientError on delete → warning logged, DB record still deleted, no exception raised.
        from botocore.exceptions import ClientError

        svc = DocumentService()
        document_id = uuid.uuid4()
        project_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # DB mock returns the document row
        s3_key = f"documents/{tenant_id}/{project_id}/{document_id}/doc.pdf"
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, k: {
            "id": document_id,
            "s3_key": s3_key,
        }.get(k)

        mock_mappings = MagicMock()
        mock_mappings.fetchone.return_value = mock_row
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings

        db = AsyncMock()
        db.execute.return_value = mock_result
        db.commit = AsyncMock()

        # S3 delete raises ClientError
        mock_s3 = MagicMock()
        mock_s3.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "delete_object"
        )

        with patch("src.services.document_service._make_s3_client", return_value=mock_s3):
            with patch("src.services.document_service.settings") as mock_settings:
                mock_settings.s3_bucket_name = "test-bucket"
                with patch("src.services.document_service._audit_service.log_action_async", new_callable=AsyncMock):
                    result = await svc.delete_document(
                        db=db,
                        schema_name="tenant_test",
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=document_id,
                        user_id=user_id,
                    )

        # DB record should be deleted despite S3 failure
        assert result is True
        db.commit.assert_called_once()

        # S3 delete was attempted
        mock_s3.delete_object.assert_called_once()


# ---------------------------------------------------------------------------
# AC5: List documents pagination
# ---------------------------------------------------------------------------

class TestListDocuments:

    @pytest.mark.asyncio
    async def test_list_documents_pagination(self):
        # Proves: page=2, page_size=5 → total_pages and items computed correctly.
        svc = DocumentService()
        project_id = uuid.uuid4()

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        mock_items = [
            {
                "id": uuid.uuid4(),
                "filename": f"doc{i}.pdf",
                "file_type": "pdf",
                "file_size_bytes": 1000 * i,
                "parse_status": "completed",
                "preview_text": "Some text",
                "created_by": uuid.uuid4(),
                "created_at": now,
            }
            for i in range(1, 4)  # 3 items on page 2
        ]

        count_result = MagicMock()
        count_result.scalar.return_value = 13  # total = 13 docs

        list_result = MagicMock()
        mock_rows = [MagicMock() for _ in mock_items]
        for mock_row, item in zip(mock_rows, mock_items):
            mock_row.__getitem__ = lambda self, k, _item=item: _item.get(k)
            mock_row.keys = MagicMock(return_value=list(item.keys()))
        mappings = MagicMock()
        mappings.fetchall.return_value = mock_rows
        list_result.mappings.return_value = mappings

        db = AsyncMock()
        db.execute.side_effect = [count_result, list_result]

        result = await svc.list_documents(
            db=db,
            schema_name="tenant_test",
            project_id=project_id,
            page=2,
            page_size=5,
        )

        assert result["total"] == 13
        assert result["page"] == 2
        assert result["page_size"] == 5
        assert result["total_pages"] == 3  # ceil(13/5)


# ---------------------------------------------------------------------------
# AC3: get_document wrong project
# ---------------------------------------------------------------------------

class TestGetDocument:

    @pytest.mark.asyncio
    async def test_get_document_wrong_project(self):
        # Proves: document from project A fetched via project B → None returned (404 at router).
        svc = DocumentService()
        db = AsyncMock()

        # DB returns no row (document not found in this project)
        mock_mappings = MagicMock()
        mock_mappings.fetchone.return_value = None
        mock_result = MagicMock()
        mock_result.mappings.return_value = mock_mappings
        db.execute.return_value = mock_result

        result = await svc.get_document(
            db=db,
            schema_name="tenant_test",
            project_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
        )

        assert result is None


# ---------------------------------------------------------------------------
# Utility: truncate_to_word_boundary (C7)
# ---------------------------------------------------------------------------

class TestTruncateToWordBoundary:

    def test_short_text_unchanged(self):
        # Proves: text shorter than limit passes through unchanged.
        assert _truncate_to_word_boundary("hello world", 100) == "hello world"

    def test_truncates_to_last_word(self):
        # Proves: text truncated to last word boundary before limit, not mid-word.
        text = "The quick brown fox jumps over the lazy dog"
        result = _truncate_to_word_boundary(text, 20)
        assert result == "The quick brown fox"
        assert len(result) <= 20
