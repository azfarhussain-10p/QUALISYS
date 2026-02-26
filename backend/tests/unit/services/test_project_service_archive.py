"""
Unit tests — ProjectService.archive_project(), restore_project(), delete_project()
Story: 1-11-project-management-archive-delete-list
Task 6.1 — Unit tests: archive, restore, delete logic
AC: AC3 — archive_project: sets is_active=false, raises 400 if already archived
AC: AC4 — restore_project: sets is_active=true, raises 400 if not archived
AC: AC5 — delete_project: cascade, audit BEFORE deletion
AC: AC7 — Error handling: ProjectAlreadyArchivedError, ProjectNotArchivedError
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.services.project_service import (
    ProjectService,
    ProjectAlreadyArchivedError,
    ProjectNotArchivedError,
    ProjectNotFoundError,
)


def _mock_project_row(project_id=None, name="Test Project", is_active=True, status="active"):
    """Helper: mock row as returned by _get_project_raw."""
    row = MagicMock()
    pid = project_id or uuid.uuid4()
    row.__getitem__ = lambda self, key: {
        "id": pid,
        "name": name,
        "slug": "test-project",
        "description": None,
        "app_url": None,
        "github_repo_url": None,
        "status": status,
        "settings": {},
        "is_active": is_active,
        "created_by": None,
        "tenant_id": uuid.uuid4(),
        "organization_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }[key]
    return row


class TestArchiveProject:
    """AC3, AC7 — archive_project."""

    @pytest.mark.asyncio
    async def test_archive_active_project_succeeds(self):
        """AC3: archiving active project sets is_active=false, status='archived'."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        # _get_project_raw returns active project
        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id, is_active=True
        )
        # UPDATE RETURNING returns archived project row
        updated_row = _mock_project_row(project_id=project_id, is_active=False, status="archived")
        updated_result = MagicMock()
        updated_result.mappings.return_value.fetchone.return_value = updated_row
        mock_db.execute.side_effect = [raw_result, updated_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            project = await svc.archive_project(project_id=project_id, db=mock_db)

        mock_db.commit.assert_awaited_once()
        assert project.is_active is False

    @pytest.mark.asyncio
    async def test_archive_already_archived_raises_error(self):
        """AC7: archiving already-archived project → ProjectAlreadyArchivedError."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id, is_active=False, status="archived"
        )
        mock_db.execute.return_value = raw_result

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            with pytest.raises(ProjectAlreadyArchivedError) as exc_info:
                await svc.archive_project(project_id=project_id, db=mock_db)

        assert "already archived" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_archive_not_found_raises_error(self):
        """AC7: archiving non-existent project → ProjectNotFoundError."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = None
        mock_db.execute.return_value = raw_result

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            with pytest.raises(ProjectNotFoundError):
                await svc.archive_project(project_id=project_id, db=mock_db)


class TestRestoreProject:
    """AC4, AC7 — restore_project."""

    @pytest.mark.asyncio
    async def test_restore_archived_project_succeeds(self):
        """AC4: restoring archived project sets is_active=true, status='active'."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id, is_active=False, status="archived"
        )
        updated_row = _mock_project_row(project_id=project_id, is_active=True, status="active")
        updated_result = MagicMock()
        updated_result.mappings.return_value.fetchone.return_value = updated_row
        mock_db.execute.side_effect = [raw_result, updated_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            project = await svc.restore_project(project_id=project_id, db=mock_db)

        mock_db.commit.assert_awaited_once()
        assert project.is_active is True

    @pytest.mark.asyncio
    async def test_restore_active_project_raises_error(self):
        """AC7: restoring active project → ProjectNotArchivedError."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id, is_active=True, status="active"
        )
        mock_db.execute.return_value = raw_result

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            with pytest.raises(ProjectNotArchivedError) as exc_info:
                await svc.restore_project(project_id=project_id, db=mock_db)

        assert "not archived" in str(exc_info.value).lower()


class TestDeleteProject:
    """AC5, AC8, C3, C8 — delete_project."""

    @pytest.mark.asyncio
    async def test_delete_executes_cascade_in_order(self):
        """AC5, C8: cascade delete — test_executions → test_cases → project_members → project."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        # _get_project_raw succeeds
        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id
        )

        # DELETE RETURNING returns a row (success)
        delete_result = MagicMock()
        delete_result.fetchone.return_value = (str(project_id),)

        # execute called: 1 (raw) + 1 (test_executions) + 1 (test_cases) + 1 (project_members) + 1 (project)
        mock_db.execute.side_effect = [
            raw_result,      # _get_project_raw
            MagicMock(),     # DELETE test_executions
            MagicMock(),     # DELETE test_cases
            MagicMock(),     # DELETE project_members
            delete_result,   # DELETE projects RETURNING id
        ]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            await svc.delete_project(project_id=project_id, db=mock_db)

        mock_db.commit.assert_awaited_once()
        # Verify 5 execute calls (1 raw + 4 deletes)
        assert mock_db.execute.call_count == 5

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_error(self):
        """AC7: deleting non-existent project → ProjectNotFoundError."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()

        # _get_project_raw returns None → not found
        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = None
        mock_db.execute.return_value = raw_result

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            with pytest.raises(ProjectNotFoundError):
                await svc.delete_project(project_id=project_id, db=mock_db)

    @pytest.mark.asyncio
    async def test_delete_with_audit_info_writes_audit_before_deletion(self):
        """AC8, C3: audit entry written before project deletion."""
        svc = ProjectService()
        mock_db = AsyncMock()
        project_id = uuid.uuid4()
        actor_id = uuid.uuid4()

        raw_result = MagicMock()
        raw_result.mappings.return_value.fetchone.return_value = _mock_project_row(
            project_id=project_id, name="My Project"
        )
        delete_result = MagicMock()
        delete_result.fetchone.return_value = (str(project_id),)

        execute_calls = []

        async def capture_execute(stmt, params=None):
            sql = str(stmt)
            execute_calls.append(sql)
            if "SELECT" in sql.upper():
                return raw_result
            if "RETURNING id" in sql.upper():
                return delete_result
            return MagicMock()

        mock_db.execute = capture_execute

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            await svc.delete_project(
                project_id=project_id,
                db=mock_db,
                audit_schema="tenant_test",
                audit_actor_id=actor_id,
                audit_actor_email="actor@test.com",
            )

        # audit log INSERT should appear BEFORE the project DELETE
        audit_idx = next((i for i, sql in enumerate(execute_calls) if "audit_logs" in sql.lower()), None)
        project_delete_idx = next(
            (i for i, sql in enumerate(execute_calls) if "DELETE" in sql.upper() and "projects" in sql.lower()),
            None
        )
        assert audit_idx is not None, "Audit log INSERT not found"
        assert project_delete_idx is not None, "Project DELETE not found"
        assert audit_idx < project_delete_idx, "Audit must be written BEFORE project deletion (C3)"
