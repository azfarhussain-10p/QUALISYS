"""
Unit tests — ArtifactService (Story 2-10)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Mocks:
  - AsyncSession (mock_db) — no real DB required
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.services.artifact_service import ArtifactService


_SCHEMA = "tenant_testorg"
_PROJECT_ID = str(uuid.uuid4())
_ARTIFACT_ID = str(uuid.uuid4())
_VERSION_ID = str(uuid.uuid4())
_NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_artifact_row(
    artifact_id: str = _ARTIFACT_ID,
    project_id: str = _PROJECT_ID,
    artifact_type: str = "coverage_matrix",
    agent_type: str = "ba_consultant",
    title: str = "Requirements Coverage Matrix",
    current_version: int = 1,
) -> dict:
    return {
        "id": artifact_id,
        "agent_type": agent_type,
        "artifact_type": artifact_type,
        "title": title,
        "current_version": current_version,
        "metadata": {"tokens_used": 100},
        "created_by": str(uuid.uuid4()),
        "created_at": _NOW,
        "updated_at": _NOW,
    }


def _make_detail_row(
    artifact_id: str = _ARTIFACT_ID,
    artifact_type: str = "coverage_matrix",
    content: str = '[{"requirement_id": "REQ-001"}]',
    content_type: str = "application/json",
) -> dict:
    row = _make_artifact_row(artifact_id=artifact_id, artifact_type=artifact_type)
    row["content"] = content
    row["content_type"] = content_type
    return row


def _make_version_row(version: int = 1) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "version": version,
        "content_type": "application/json",
        "edited_by": None,
        "created_at": _NOW,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

service = ArtifactService()


@pytest.mark.asyncio
async def test_list_artifacts_returns_rows():
    # Proves: list_artifacts() executes SELECT and maps rows to dicts.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchall.return_value = [
        _make_artifact_row(),
        _make_artifact_row(artifact_id=str(uuid.uuid4()), artifact_type="manual_checklist"),
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    rows = await service.list_artifacts(mock_db, _SCHEMA, _PROJECT_ID)

    assert len(rows) == 2
    assert rows[0]["artifact_type"] == "coverage_matrix"
    assert rows[1]["artifact_type"] == "manual_checklist"
    assert "id" in rows[0]
    assert "created_at" in rows[0]


@pytest.mark.asyncio
async def test_list_artifacts_with_type_filter():
    # Proves: list_artifacts() with artifact_type appends AND clause to query.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchall.return_value = [_make_artifact_row()]
    mock_db.execute = AsyncMock(return_value=mock_result)

    rows = await service.list_artifacts(mock_db, _SCHEMA, _PROJECT_ID, artifact_type="coverage_matrix")

    assert len(rows) == 1
    call_args = mock_db.execute.call_args
    sql_text = str(call_args[0][0])
    assert "artifact_type" in sql_text


@pytest.mark.asyncio
async def test_get_artifact_returns_detail_with_content():
    # Proves: get_artifact() JOINs artifact_versions and returns content from current_version.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = _make_detail_row()
    mock_db.execute = AsyncMock(return_value=mock_result)

    row = await service.get_artifact(mock_db, _SCHEMA, _PROJECT_ID, _ARTIFACT_ID)

    assert row["content"] == '[{"requirement_id": "REQ-001"}]'
    assert row["content_type"] == "application/json"
    assert row["artifact_type"] == "coverage_matrix"


@pytest.mark.asyncio
async def test_get_artifact_raises_404_wrong_project():
    # Proves: get_artifact() raises HTTPException(404) when no row found (wrong project_id).
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_artifact(mock_db, _SCHEMA, _PROJECT_ID, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "ARTIFACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_versions_ordered_desc():
    # Proves: list_versions() returns versions ordered latest-first.
    mock_db = AsyncMock()

    # First call: ownership check
    owner_result = MagicMock()
    owner_result.fetchone.return_value = (_ARTIFACT_ID,)

    # Second call: version list
    version_result = MagicMock()
    version_result.mappings.return_value.fetchall.return_value = [
        _make_version_row(version=3),
        _make_version_row(version=2),
        _make_version_row(version=1),
    ]

    mock_db.execute = AsyncMock(side_effect=[owner_result, version_result])

    rows = await service.list_versions(mock_db, _SCHEMA, _PROJECT_ID, _ARTIFACT_ID)

    assert len(rows) == 3
    assert rows[0]["version"] == 3
    assert rows[1]["version"] == 2
    assert rows[2]["version"] == 1


@pytest.mark.asyncio
async def test_list_versions_raises_404_wrong_project():
    # Proves: list_versions() raises HTTPException(404) when artifact not found in project.
    mock_db = AsyncMock()
    owner_result = MagicMock()
    owner_result.fetchone.return_value = None
    mock_db.execute = AsyncMock(return_value=owner_result)

    with pytest.raises(HTTPException) as exc_info:
        await service.list_versions(mock_db, _SCHEMA, _PROJECT_ID, str(uuid.uuid4()))

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_version_raises_404_unknown_version():
    # Proves: get_version() raises HTTPException(404) when version number does not exist.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.mappings.return_value.fetchone.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_version(mock_db, _SCHEMA, _PROJECT_ID, _ARTIFACT_ID, 999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "VERSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# update_artifact() tests — AC-28 (Story 2-11)
# ---------------------------------------------------------------------------


def _make_result_for_detail(row: dict | None) -> MagicMock:
    """Build a mock execute result that returns row from mappings().fetchone()."""
    r = MagicMock()
    r.mappings.return_value.fetchone.return_value = row
    return r


def _make_blank_result() -> MagicMock:
    """Build a mock execute result for INSERT/UPDATE (no return value needed)."""
    return MagicMock()


@pytest.mark.asyncio
async def test_update_artifact_creates_new_version():
    # Proves: update_artifact() inserts a new version row and returns current_version == 2.
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    row_v1 = _make_detail_row(content="old content", content_type="text/plain")
    row_v2 = _make_detail_row(content="new content", content_type="text/plain")
    row_v2["current_version"] = 2

    # Call order: get_artifact SELECT, INSERT, UPDATE, get_artifact SELECT again
    mock_db.execute = AsyncMock(
        side_effect=[
            _make_result_for_detail(row_v1),
            _make_blank_result(),
            _make_blank_result(),
            _make_result_for_detail(row_v2),
        ]
    )

    result = await service.update_artifact(
        mock_db, _SCHEMA, _PROJECT_ID, _ARTIFACT_ID, "new content", str(uuid.uuid4())
    )

    assert result["current_version"] == 2
    assert result["content"] == "new content"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_artifact_computes_diff():
    # Proves: update_artifact() passes diff_from_prev containing '-line2' and '+line3' to INSERT.
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    old_content = "line1\nline2"
    new_content = "line1\nline3"

    row_v1 = _make_detail_row(content=old_content, content_type="text/plain")
    row_v2 = _make_detail_row(content=new_content, content_type="text/plain")
    row_v2["current_version"] = 2

    mock_db.execute = AsyncMock(
        side_effect=[
            _make_result_for_detail(row_v1),
            _make_blank_result(),
            _make_blank_result(),
            _make_result_for_detail(row_v2),
        ]
    )

    await service.update_artifact(
        mock_db, _SCHEMA, _PROJECT_ID, _ARTIFACT_ID, new_content, str(uuid.uuid4())
    )

    # Second execute call (index 1) is the INSERT; params are the second positional arg
    insert_call = mock_db.execute.call_args_list[1]
    insert_params = insert_call[0][1]  # positional args: (text_clause, params_dict)
    diff_stored = insert_params["diff"]

    assert "-line2" in diff_stored
    assert "+line3" in diff_stored


@pytest.mark.asyncio
async def test_update_artifact_raises_404_if_not_found():
    # Proves: update_artifact() raises HTTPException(404) and makes no INSERT when artifact missing.
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_db.execute = AsyncMock(return_value=_make_result_for_detail(None))

    with pytest.raises(HTTPException) as exc_info:
        await service.update_artifact(
            mock_db, _SCHEMA, _PROJECT_ID, str(uuid.uuid4()), "content", str(uuid.uuid4())
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "ARTIFACT_NOT_FOUND"
    # Only one db.execute call — no INSERT or UPDATE attempted
    assert mock_db.execute.call_count == 1
    mock_db.commit.assert_not_called()
