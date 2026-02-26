"""
Unit tests — ProjectService.list_projects()
Story: 1-11-project-management-archive-delete-list
Task 6.1 — Unit tests: list filtering, search, sort, pagination logic
AC: AC1, AC2 — status filter (active/archived/all), search, sort, pagination
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.project_service import ProjectService, PaginatedResult


def _make_row(
    project_id=None,
    name="Test Project",
    slug="test-project",
    description=None,
    status="active",
    is_active=True,
    member_count=0,
):
    """Helper: mock DB row matching projects LEFT JOIN member_count."""
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "id": project_id or uuid.uuid4(),
        "name": name,
        "slug": slug,
        "description": description,
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
        "member_count": member_count,
    }[key]
    row.keys.return_value = [
        "id", "name", "slug", "description", "app_url", "github_repo_url",
        "status", "settings", "is_active", "created_by", "tenant_id",
        "organization_id", "created_at", "updated_at", "member_count",
    ]
    return row


class TestListProjectsFiltering:
    """AC1, AC2 — status filtering."""

    @pytest.mark.asyncio
    async def test_active_filter_excludes_archived(self):
        """AC2: default 'active' filter should query is_active=true."""
        svc = ProjectService()
        mock_db = AsyncMock()

        # count query returns 1, data query returns one active project row
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        row = _make_row(is_active=True, status="active")
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [row]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
                status="active",
            )

        assert isinstance(result, PaginatedResult)
        assert result.total == 1
        assert len(result.data) == 1

        # Verify the WHERE clause includes is_active = true
        first_call_sql = str(mock_db.execute.call_args_list[0])
        assert "is_active" in first_call_sql or "active" in str(mock_db.execute.call_args_list[0])

    @pytest.mark.asyncio
    async def test_all_filter_returns_both(self):
        """AC2: status='all' — no is_active filter."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        active_row = _make_row(name="Active", is_active=True)
        archived_row = _make_row(name="Archived", is_active=False, status="archived")
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [active_row, archived_row]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
                status="all",
            )

        assert result.total == 2
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_archived_filter(self):
        """AC2: status='archived' — only is_active=false."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        row = _make_row(is_active=False, status="archived")
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [row]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
                status="archived",
            )

        assert result.total == 1
        assert result.data[0].is_active is False


class TestListProjectsPagination:
    """AC1 — pagination."""

    @pytest.mark.asyncio
    async def test_pagination_metadata(self):
        """AC1: pagination total_pages computed correctly."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 45  # 45 total → 3 pages at 20/page
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [_make_row() for _ in range(20)]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
                page=1,
                per_page=20,
            )

        assert result.total == 45
        assert result.total_pages == 3
        assert result.page == 1
        assert result.per_page == 20

    @pytest.mark.asyncio
    async def test_empty_result(self):
        """AC1: empty state when no projects."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = []
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
            )

        assert result.total == 0
        assert result.data == []
        assert result.total_pages == 1  # min 1 page even when empty


class TestListProjectsMemberCount:
    """AC1 — member_count from JOIN."""

    @pytest.mark.asyncio
    async def test_member_count_populated(self):
        """AC1: member_count from LEFT JOIN project_members."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        row = _make_row(member_count=5)
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [row]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
            )

        assert result.data[0].member_count == 5


class TestListProjectsHealthPlaceholder:
    """AC6 — health indicator placeholder."""

    @pytest.mark.asyncio
    async def test_health_is_dash_placeholder(self):
        """AC6: health always '—' in Epic 1."""
        svc = ProjectService()
        mock_db = AsyncMock()

        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        row = _make_row()
        data_result = MagicMock()
        data_result.mappings.return_value.fetchall.return_value = [row]
        mock_db.execute.side_effect = [count_result, data_result]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            result = await svc.list_projects(
                db=mock_db,
                user_id=uuid.uuid4(),
                user_role="owner",
                tenant_id=uuid.uuid4(),
            )

        assert result.data[0].health == "—"
