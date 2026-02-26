"""
QUALISYS — Analytics Service
Story: 1-12-usage-analytics-audit-logs-basic
AC: #1 — AnalyticsService.get_dashboard_metrics() for admin dashboard

Returns simple usage counts for the admin dashboard:
  - active_users:      COUNT from public.tenants_users WHERE tenant_id AND is_active
  - active_projects:   COUNT from {tenant_schema}.projects WHERE is_active = true
  - test_runs:         Placeholder 0 — populated by Epic 2-4
  - storage_consumed:  Placeholder "—" — populated by Epic 2

Redis cache (5-minute TTL) prevents repeated COUNT queries on every dashboard load.
Cache key: analytics:dashboard:{tenant_id}

Security (C1, C2):
  - schema_name validated by caller before passing here.
  - tenant_id always from JWT context — never from request body.
  - Parameterized queries only (SQLAlchemy text() with named :params).
"""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache import get_redis_client
from src.logger import logger

# Redis TTL for dashboard metrics (seconds)
_METRICS_CACHE_TTL = 300  # 5 minutes


class AnalyticsService:
    """
    Provides pre-computed usage metrics for the admin dashboard.

    All metrics are cached in Redis for 5 minutes to avoid repeated DB COUNT
    queries on every dashboard load.
    """

    async def get_dashboard_metrics(
        self,
        schema_name: str,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Return dashboard metrics for the given tenant.

        Args:
            schema_name: Validated tenant schema name (e.g., 'tenant_acme').
            tenant_id:   Tenant UUID used as cache key scope.
            db:          AsyncSession for DB queries.

        Returns:
            dict with keys: active_users, active_projects, test_runs, storage_consumed.
        """
        redis = get_redis_client()
        cache_key = f"analytics:dashboard:{tenant_id}"

        # --- 1. Try Redis cache ---
        try:
            cached_raw = await redis.get(cache_key)
            if cached_raw:
                return json.loads(cached_raw)
        except Exception as exc:
            logger.warning("Analytics cache read failed", exc=str(exc))

        # --- 2. Query DB ---
        metrics = await self._compute_metrics(schema_name, tenant_id, db)

        # --- 3. Store in cache ---
        try:
            await redis.setex(cache_key, _METRICS_CACHE_TTL, json.dumps(metrics, default=str))
        except Exception as exc:
            logger.warning("Analytics cache write failed", exc=str(exc))

        return metrics

    async def _compute_metrics(
        self,
        schema_name: str,
        tenant_id: uuid.UUID,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Execute COUNT queries and build the metrics dict."""
        # Active users: members of this tenant with is_active = true
        try:
            user_result = await db.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM public.tenants_users "
                    "WHERE tenant_id = :tenant_id AND is_active = true"
                ),
                {"tenant_id": str(tenant_id)},
            )
            row = user_result.fetchone()
            active_users: int = row[0] if row else 0
        except Exception as exc:
            logger.warning("Analytics: user count query failed", exc=str(exc))
            active_users = 0

        # Active projects: projects in tenant schema with is_active = true
        try:
            project_result = await db.execute(
                text(
                    f'SELECT COUNT(*) AS cnt FROM "{schema_name}".projects '
                    "WHERE is_active = true"
                ),
            )
            row = project_result.fetchone()
            active_projects: int = row[0] if row else 0
        except Exception as exc:
            logger.warning("Analytics: project count query failed", exc=str(exc))
            active_projects = 0

        return {
            "active_users": active_users,
            "active_projects": active_projects,
            "test_runs": 0,         # Placeholder — Epic 2-4
            "storage_consumed": "—",  # Placeholder — Epic 2
        }

    async def invalidate_cache(self, tenant_id: uuid.UUID) -> None:
        """Invalidate cached metrics for a tenant (call after project create/delete)."""
        try:
            redis = get_redis_client()
            await redis.delete(f"analytics:dashboard:{tenant_id}")
        except Exception as exc:
            logger.warning("Analytics cache invalidation failed", exc=str(exc))


# Module-level singleton
analytics_service = AnalyticsService()
