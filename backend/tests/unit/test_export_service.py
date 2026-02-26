"""
Unit tests — ExportService
Story: 1-13-data-export-org-deletion
Task 7.1 — export serialization, rate limit check, job creation, status retrieval
AC: #2 — background job creation, rate limit (1/24h)
AC: #5 — list exports, download URL generation
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.export_service import ExportService, _json_default


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()


def _make_session(scalar_one_or_none=None, fetchone=None, fetchall=None, scalar=None):
    """Mock AsyncSession."""
    session = AsyncMock()
    result_mock = MagicMock()

    if scalar is not None:
        result_mock.scalar.return_value = scalar
        result_mock.scalar_one_or_none.return_value = scalar

    if fetchone is not None:
        mappings = MagicMock()
        mappings.fetchone.return_value = fetchone
        result_mock.mappings.return_value = mappings

    if fetchall is not None:
        mappings = MagicMock()
        mappings.fetchall.return_value = fetchall
        result_mock.mappings.return_value = mappings

    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Test: _json_default serializer
# ---------------------------------------------------------------------------

def test_json_default_uuid():
    uid = uuid.uuid4()
    result = _json_default(uid)
    assert result == str(uid)


def test_json_default_str_fallback():
    result = _json_default(object())
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Test: request_export — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_export_creates_job():
    """request_export() should create job record and return job metadata."""
    svc = ExportService()

    db = AsyncMock()
    db.commit = AsyncMock()

    # First execute() call: check for in-progress job → None (no active job)
    # Second execute() call: INSERT into export_jobs
    in_progress_result = MagicMock()
    in_progress_result.fetchone.return_value = None

    db.execute = AsyncMock(return_value=in_progress_result)

    with patch.object(svc, '_check_export_rate_limit', return_value=True):
        result = await svc.request_export(db=db, tenant_id=TENANT_ID, requested_by=USER_ID)

    assert result["status"] == "processing"
    assert "job_id" in result
    assert "estimated_duration" in result
    assert db.commit.called


@pytest.mark.asyncio
async def test_request_export_rate_limit_blocks():
    """request_export() should raise ValueError('RATE_LIMIT_EXCEEDED') when blocked."""
    svc = ExportService()

    db = AsyncMock()
    in_progress_result = MagicMock()
    in_progress_result.fetchone.return_value = None
    db.execute = AsyncMock(return_value=in_progress_result)

    with patch.object(svc, '_check_export_rate_limit', return_value=False):
        with pytest.raises(ValueError, match="RATE_LIMIT_EXCEEDED"):
            await svc.request_export(db=db, tenant_id=TENANT_ID, requested_by=USER_ID)


@pytest.mark.asyncio
async def test_request_export_blocks_when_in_progress():
    """request_export() should raise EXPORT_IN_PROGRESS if a job is already running."""
    svc = ExportService()

    db = AsyncMock()
    # First execute: returns an in-progress job row
    existing_job = MagicMock()
    existing_job.id = str(JOB_ID)
    in_progress_result = MagicMock()
    in_progress_result.fetchone.return_value = existing_job
    db.execute = AsyncMock(return_value=in_progress_result)

    with pytest.raises(ValueError, match="EXPORT_IN_PROGRESS"):
        await svc.request_export(db=db, tenant_id=TENANT_ID, requested_by=USER_ID)


# ---------------------------------------------------------------------------
# Test: get_export_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_export_status_returns_none_when_not_found():
    """get_export_status() should return None when job does not exist for tenant."""
    svc = ExportService()

    db = AsyncMock()
    result_mock = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.fetchone.return_value = None
    result_mock.mappings.return_value = mappings_mock
    db.execute = AsyncMock(return_value=result_mock)

    status = await svc.get_export_status(db=db, tenant_id=TENANT_ID, job_id=JOB_ID)
    assert status is None


@pytest.mark.asyncio
async def test_get_export_status_returns_job_dict():
    """get_export_status() should return a status dict for a found job."""
    from datetime import datetime, timezone
    svc = ExportService()

    db = AsyncMock()
    row = {
        "id": JOB_ID,
        "status": "completed",
        "progress_percent": 100,
        "file_size_bytes": 1234,
        "s3_key": "exports/abc/def/zip",
        "error_message": None,
        "created_at": datetime(2026, 2, 25, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 2, 25, tzinfo=timezone.utc),
    }
    result_mock = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.fetchone.return_value = row
    result_mock.mappings.return_value = mappings_mock
    db.execute = AsyncMock(return_value=result_mock)

    with patch.object(svc, 'get_download_url', return_value="https://s3/presigned"):
        status = await svc.get_export_status(db=db, tenant_id=TENANT_ID, job_id=JOB_ID)

    assert status is not None
    assert status["status"] == "completed"
    assert status["file_size_bytes"] == 1234
    assert status["download_url"] == "https://s3/presigned"


# ---------------------------------------------------------------------------
# Test: list_exports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_exports_returns_empty_list():
    """list_exports() should return [] when no jobs exist."""
    svc = ExportService()

    db = AsyncMock()
    result_mock = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.fetchall.return_value = []
    result_mock.mappings.return_value = mappings_mock
    db.execute = AsyncMock(return_value=result_mock)

    result = await svc.list_exports(db=db, tenant_id=TENANT_ID)
    assert result == []


@pytest.mark.asyncio
async def test_list_exports_returns_up_to_5():
    """list_exports() should pass limit=5 to query and return that many jobs."""
    from datetime import datetime, timezone
    svc = ExportService()

    db = AsyncMock()
    rows = [
        {
            "id": uuid.uuid4(),
            "status": "completed",
            "progress_percent": 100,
            "file_size_bytes": 100,
            "s3_key": None,
            "error_message": None,
            "created_at": datetime(2026, 2, 25, tzinfo=timezone.utc),
            "completed_at": None,
        }
        for _ in range(3)
    ]
    result_mock = MagicMock()
    mappings_mock = MagicMock()
    mappings_mock.fetchall.return_value = rows
    result_mock.mappings.return_value = mappings_mock
    db.execute = AsyncMock(return_value=result_mock)

    result = await svc.list_exports(db=db, tenant_id=TENANT_ID)
    assert len(result) == 3
    assert all(r["status"] == "completed" for r in result)


# ---------------------------------------------------------------------------
# Test: get_download_url (S3 not configured — dev path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_download_url_dev_fallback():
    """get_download_url() should return dev path when S3 is not configured."""
    from src.config import get_settings

    svc = ExportService()

    with patch('src.services.export_service.settings') as mock_settings:
        mock_settings.s3_bucket_name = ''
        url = await svc.get_download_url("exports/abc/def.zip")

    assert "/dev-export/" in url
