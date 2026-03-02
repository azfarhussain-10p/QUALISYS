"""
Unit tests — PMDashboardService (Story 2-12, 2-13)
DoD: every test has a one-line comment stating the behaviour proved.

Tests pure logic functions only (no DB, no Redis required):
  - _compute_health() boundary conditions (AC-30)
  - get_overview() cache-hit path (AC-30)
  - _compute_week_over_week() delta + direction (AC-1)
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.pm_dashboard_service import PMDashboardService


# ---------------------------------------------------------------------------
# _compute_health boundary tests (AC-30)
# ---------------------------------------------------------------------------

class TestComputeHealth:

    def test_compute_health_no_data(self):
        # Proves: _compute_health(None) returns "no_data" when no coverage artifacts exist.
        assert PMDashboardService._compute_health(None) == "no_data"

    def test_compute_health_green(self):
        # Proves: _compute_health(80.0) returns "green" at the 80% boundary (inclusive).
        assert PMDashboardService._compute_health(80.0) == "green"

    def test_compute_health_yellow(self):
        # Proves: _compute_health(79.9) returns "yellow" just below the 80% green threshold.
        assert PMDashboardService._compute_health(79.9) == "yellow"

    def test_compute_health_yellow_lower(self):
        # Proves: _compute_health(50.0) returns "yellow" at the lower 50% boundary (inclusive).
        assert PMDashboardService._compute_health(50.0) == "yellow"

    def test_compute_health_red(self):
        # Proves: _compute_health(49.9) returns "red" just below the 50% yellow threshold.
        assert PMDashboardService._compute_health(49.9) == "red"


# ---------------------------------------------------------------------------
# get_overview — cache-hit path (AC-30)
# ---------------------------------------------------------------------------

class TestGetOverviewCached:

    @pytest.mark.asyncio
    async def test_get_overview_returns_cached(self):
        # Proves: get_overview() returns cached dict and does NOT query the DB when Redis has data.
        service = PMDashboardService()
        project_id = str(uuid.uuid4())
        cached_data = {
            "coverage_pct": 85.0,
            "health_status": "green",
            "requirements_covered": 17,
            "total_requirements": 20,
            "artifact_count": 3,
            "last_run_at": "2026-03-01T10:00:00+00:00",
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(cached_data).encode())

        mock_db = AsyncMock()

        with patch("src.services.pm_dashboard_service.get_redis_client", return_value=mock_redis):
            result = await service.get_overview(mock_db, "tenant_test", project_id)

        # Cache hit — DB should NOT be queried
        mock_db.execute.assert_not_called()
        assert result["coverage_pct"] == 85.0
        assert result["health_status"] == "green"
        assert result["requirements_covered"] == 17


# ---------------------------------------------------------------------------
# _compute_week_over_week boundary tests (AC-1)
# ---------------------------------------------------------------------------

class TestComputeWeekOverWeek:

    def test_compute_week_over_week_up(self):
        # Proves: _compute_week_over_week(80.0, 75.0) returns (5.0, "up") for a positive delta.
        pct, direction = PMDashboardService._compute_week_over_week(80.0, 75.0)
        assert pct == 5.0
        assert direction == "up"

    def test_compute_week_over_week_down(self):
        # Proves: _compute_week_over_week(70.0, 75.0) returns (-5.0, "down") for a negative delta.
        pct, direction = PMDashboardService._compute_week_over_week(70.0, 75.0)
        assert pct == -5.0
        assert direction == "down"

    def test_compute_week_over_week_flat(self):
        # Proves: _compute_week_over_week(75.0, 75.0) returns (0.0, "flat") when equal.
        pct, direction = PMDashboardService._compute_week_over_week(75.0, 75.0)
        assert pct == 0.0
        assert direction == "flat"

    def test_compute_week_over_week_no_data(self):
        # Proves: _compute_week_over_week(None, 75.0) returns (None, "no_data") when current is None.
        pct, direction = PMDashboardService._compute_week_over_week(None, 75.0)
        assert pct is None
        assert direction == "no_data"
