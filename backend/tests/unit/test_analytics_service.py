"""
Unit tests — AnalyticsService
Story: 1-12-usage-analytics-audit-logs-basic
Task 7.2 — AnalyticsService.get_dashboard_metrics() returns correct counts
AC: #1 — active_users, active_projects, test_runs=0, storage='—'
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.analytics_service import AnalyticsService, analytics_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA = "tenant_test"
TENANT_ID = uuid.uuid4()


def _make_db_session(user_count: int = 3, project_count: int = 5):
    """Mock db session that returns canned COUNT results."""
    session = AsyncMock()

    call_count = [0]

    async def mock_execute(stmt, params=None):
        call_count[0] += 1
        result = MagicMock()
        s = str(stmt).lower()
        if "tenants_users" in s:
            result.fetchone.return_value = (user_count,)
            result.scalar.return_value = user_count
        elif "projects" in s:
            result.fetchone.return_value = (project_count,)
            result.scalar.return_value = project_count
        else:
            result.fetchone.return_value = (0,)
            result.scalar.return_value = 0
        return result

    session.execute = mock_execute
    return session


def _make_redis_no_cache():
    """Redis mock that returns no cached value."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    return mock


def _make_redis_with_cache(data: dict):
    """Redis mock that returns cached JSON."""
    mock = MagicMock()
    mock.get = AsyncMock(return_value=json.dumps(data))
    mock.setex = AsyncMock(return_value=True)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_dashboard_metrics_returns_correct_counts():
    """get_dashboard_metrics() returns active_users and active_projects counts."""
    db = _make_db_session(user_count=7, project_count=3)
    svc = AnalyticsService()

    with patch("src.services.analytics_service.get_redis_client", return_value=_make_redis_no_cache()):
        metrics = await svc.get_dashboard_metrics(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            db=db,
        )

    assert metrics["active_users"] == 7
    assert metrics["active_projects"] == 3
    assert metrics["test_runs"] == 0          # placeholder
    assert metrics["storage_consumed"] == "—" # placeholder


@pytest.mark.asyncio
async def test_get_dashboard_metrics_uses_redis_cache():
    """Second call returns cached data without hitting DB."""
    db = _make_db_session(user_count=4, project_count=2)
    svc = AnalyticsService()

    cached_data = {"active_users": 99, "active_projects": 88, "test_runs": 0, "storage_consumed": "—"}
    redis_mock = _make_redis_with_cache(cached_data)

    with patch("src.services.analytics_service.get_redis_client", return_value=redis_mock):
        metrics = await svc.get_dashboard_metrics(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            db=db,
        )

    # Should return cached values, not DB values
    assert metrics["active_users"] == 99
    assert metrics["active_projects"] == 88


@pytest.mark.asyncio
async def test_get_dashboard_metrics_caches_result():
    """After DB query, result is stored in Redis with 5-minute TTL."""
    db = _make_db_session(user_count=5, project_count=2)
    svc = AnalyticsService()
    redis_mock = _make_redis_no_cache()

    with patch("src.services.analytics_service.get_redis_client", return_value=redis_mock):
        await svc.get_dashboard_metrics(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            db=db,
        )

    # Verify setex was called with 5-minute TTL
    redis_mock.setex.assert_called_once()
    call_args = redis_mock.setex.call_args
    assert call_args.args[1] == 300  # 5 minutes = 300 seconds


@pytest.mark.asyncio
async def test_get_dashboard_metrics_graceful_on_db_error():
    """DB errors return 0 counts — never fail the request."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=Exception("DB error"))
    svc = AnalyticsService()

    with patch("src.services.analytics_service.get_redis_client", return_value=_make_redis_no_cache()):
        metrics = await svc.get_dashboard_metrics(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            db=db,
        )

    assert metrics["active_users"] == 0
    assert metrics["active_projects"] == 0


@pytest.mark.asyncio
async def test_get_dashboard_metrics_graceful_on_redis_error():
    """Redis errors fall through to DB queries."""
    db = _make_db_session(user_count=2, project_count=1)
    svc = AnalyticsService()

    broken_redis = MagicMock()
    broken_redis.get = AsyncMock(side_effect=Exception("Redis unavailable"))
    broken_redis.setex = AsyncMock(side_effect=Exception("Redis unavailable"))

    with patch("src.services.analytics_service.get_redis_client", return_value=broken_redis):
        metrics = await svc.get_dashboard_metrics(
            schema_name=SCHEMA,
            tenant_id=TENANT_ID,
            db=db,
        )

    # Should still return DB data despite Redis failure
    assert metrics["active_users"] == 2
    assert metrics["active_projects"] == 1


@pytest.mark.asyncio
async def test_invalidate_cache_deletes_redis_key():
    """invalidate_cache() deletes the cached entry for the tenant."""
    svc = AnalyticsService()
    redis_mock = MagicMock()
    redis_mock.delete = AsyncMock(return_value=1)

    with patch("src.services.analytics_service.get_redis_client", return_value=redis_mock):
        await svc.invalidate_cache(TENANT_ID)

    redis_mock.delete.assert_called_once_with(f"analytics:dashboard:{TENANT_ID}")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def test_analytics_service_singleton():
    """Module-level `analytics_service` is an AnalyticsService instance."""
    assert isinstance(analytics_service, AnalyticsService)
