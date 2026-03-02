"""
QUALISYS — PM Dashboard Service
Story: 2-12-pm-csm-dashboard-project-health-overview
       2-13-pm-dashboard-test-coverage-metrics
AC-30: project health overview (coverage %, health status, recent activity)
AC-31: coverage trend (30-day daily LineChart data, requirements totals)
AC-1:  week-over-week trend indicator
AC-2:  coverage matrix drill-down
AC-3:  multi-project health grid
FR67: project health dashboard
FR68: test coverage metrics

Coverage data sourced from artifacts.metadata JSONB (BAConsultant output, Story 2-8):
  {"requirements_covered": N, "total_requirements": M, "tokens_used": ...}
Redis cache key: dashboard:{project_id}, TTL 60s (tech-spec §6.1).
              dashboard:projects:{tenant_id}, TTL 60s (Story 2-13 AC-3).
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.cache import get_redis_client
from src.logger import logger

_CACHE_TTL = 60  # seconds


class PMDashboardService:
    """
    Provides project health metrics and coverage trend data for the PM/CSM dashboard.

    All data is sourced from artifacts.metadata JSONB where artifact_type='coverage_matrix'.
    Overview results are Redis-cached for 60 seconds to avoid repeated aggregation queries.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_overview(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
    ) -> dict[str, Any]:
        """
        AC-30: Return project health overview.

        Attempts Redis cache first (TTL 60s). On miss, computes from DB and caches.

        Returns:
            {
              "coverage_pct": float | None,
              "health_status": "green" | "yellow" | "red" | "no_data",
              "requirements_covered": int,
              "total_requirements": int,
              "artifact_count": int,
              "last_run_at": str | None,   # ISO8601 of most recent agent_run.created_at
            }
        """
        cache_key = f"dashboard:{project_id}"
        redis = get_redis_client()

        # 1. Try Redis cache
        try:
            cached_raw = await redis.get(cache_key)
            if cached_raw:
                return json.loads(cached_raw)
        except Exception as exc:
            logger.warning("PM dashboard cache read failed", exc=str(exc))

        # 2. Query DB
        result = await self._compute_overview(db, schema_name, project_id)

        # 3. Cache result
        try:
            await redis.set(cache_key, json.dumps(result, default=str), ex=_CACHE_TTL)
        except Exception as exc:
            logger.warning("PM dashboard cache write failed", exc=str(exc))

        return result

    async def get_coverage_trend(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
    ) -> dict[str, Any]:
        """
        AC-31: Return 30-day daily coverage trend + lifetime totals.
        AC-1:  Includes week-over-week delta and direction fields.

        Returns:
            {
              "requirements_covered": int,
              "total_requirements": int,
              "coverage_pct": float | None,
              "trend": [{"date": "YYYY-MM-DD", "coverage_pct": float | None}, ...]  # 30 items
              "week_over_week_pct": float | None,        # AC-1
              "week_over_week_direction": str,           # AC-1 "up"|"down"|"flat"|"no_data"
            }
        """
        # Daily grouped aggregation for last 30 days
        rows = await db.execute(
            text(
                f"""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC')                         AS day,
                    SUM((metadata->>'requirements_covered')::int)               AS covered,
                    SUM((metadata->>'total_requirements')::int)                 AS total
                FROM "{schema_name}".artifacts
                WHERE project_id = :pid
                  AND artifact_type = 'coverage_matrix'
                  AND created_at >= NOW() - INTERVAL '30 days'
                  AND metadata ? 'requirements_covered'
                  AND metadata ? 'total_requirements'
                GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                ORDER BY day ASC
                """
            ),
            {"pid": project_id},
        )
        db_rows = rows.fetchall()

        # Build zero-filled 30-day trend
        end_day = date.today()
        start_day = end_day - timedelta(days=29)  # 30 days inclusive
        day_map: dict[date, float | None] = {
            start_day + timedelta(i): None for i in range(30)
        }

        for row in db_rows:
            covered = row.covered or 0
            total = row.total or 0
            day_map[row.day] = round(covered / total * 100, 1) if total > 0 else None

        trend = [
            {"date": d.isoformat(), "coverage_pct": v}
            for d, v in sorted(day_map.items())
        ]

        # Lifetime totals (all time, not just last 30 days)
        totals_result = await db.execute(
            text(
                f"""
                SELECT
                    COALESCE(SUM((metadata->>'requirements_covered')::int), 0) AS reqs_covered,
                    COALESCE(SUM((metadata->>'total_requirements')::int), 0)   AS reqs_total
                FROM "{schema_name}".artifacts
                WHERE project_id = :pid
                  AND artifact_type = 'coverage_matrix'
                  AND metadata ? 'requirements_covered'
                  AND metadata ? 'total_requirements'
                """
            ),
            {"pid": project_id},
        )
        totals_row = totals_result.fetchone()
        reqs_covered = totals_row.reqs_covered if totals_row else 0
        reqs_total = totals_row.reqs_total if totals_row else 0
        coverage_pct = (
            round(reqs_covered / reqs_total * 100, 1) if reqs_total > 0 else None
        )

        # AC-1: Week-over-week — same filter but created_at < NOW() - INTERVAL '7 days'
        last_week_result = await db.execute(
            text(
                f"""
                SELECT
                    COALESCE(SUM((metadata->>'requirements_covered')::int), 0) AS covered,
                    COALESCE(SUM((metadata->>'total_requirements')::int), 0)   AS total
                FROM "{schema_name}".artifacts
                WHERE project_id = :pid
                  AND artifact_type = 'coverage_matrix'
                  AND created_at < NOW() - INTERVAL '7 days'
                  AND metadata ? 'requirements_covered'
                  AND metadata ? 'total_requirements'
                """
            ),
            {"pid": project_id},
        )
        lw_row = last_week_result.fetchone()
        last_week_pct = (
            round(lw_row.covered / lw_row.total * 100, 1)
            if lw_row and lw_row.total > 0
            else None
        )
        wow_pct, wow_dir = self._compute_week_over_week(coverage_pct, last_week_pct)

        return {
            "requirements_covered": reqs_covered,
            "total_requirements": reqs_total,
            "coverage_pct": coverage_pct,
            "trend": trend,
            "week_over_week_pct": wow_pct,
            "week_over_week_direction": wow_dir,
        }

    async def get_coverage_matrix(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
    ) -> dict[str, Any]:
        """
        AC-2: Find latest coverage_matrix artifact and parse requirements list.

        Returns:
            {
              "artifact_id": str | None,
              "artifact_title": str | None,
              "requirements": [{"name": str, "covered": bool, "test_count": int}],
              "generated_at": str | None,
              "fallback_url": str | None,
            }
        """
        result = await db.execute(
            text(
                f"""
                SELECT a.id, a.title, a.created_at, av.content
                FROM "{schema_name}".artifacts a
                JOIN "{schema_name}".artifact_versions av
                  ON av.artifact_id = a.id AND av.version = a.current_version
                WHERE a.project_id = :pid
                  AND a.artifact_type = 'coverage_matrix'
                ORDER BY a.created_at DESC
                LIMIT 1
                """
            ),
            {"pid": project_id},
        )
        row = result.fetchone()

        if not row:
            return {
                "artifact_id": None,
                "artifact_title": None,
                "requirements": [],
                "generated_at": None,
                "fallback_url": f"/projects/{project_id}/artifacts?type=coverage_matrix",
            }

        requirements: list[dict] = []
        try:
            content_data = json.loads(row.content)
            raw_reqs = content_data.get("requirements", [])
            for req in raw_reqs:
                requirements.append(
                    {
                        "name": req["name"],
                        "covered": bool(req.get("covered", False)),
                        "test_count": int(req.get("test_count", 0)),
                    }
                )
        except (json.JSONDecodeError, KeyError, TypeError):
            requirements = []

        return {
            "artifact_id": str(row.id),
            "artifact_title": row.title,
            "requirements": requirements,
            "generated_at": row.created_at.isoformat() if row.created_at else None,
            "fallback_url": (
                None
                if requirements
                else f"/projects/{project_id}/artifacts?type=coverage_matrix"
            ),
        }

    async def get_all_projects_health(
        self,
        db: AsyncSession,
        schema_name: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """
        AC-3: Return health cards for all projects in the tenant.

        Redis cache key: dashboard:projects:{tenant_id}, TTL 60s.

        Uses 3 batch queries instead of 2N per-project queries:
          1. All projects (list)
          2. Artifact coverage aggregation GROUP BY project_id
          3. Last agent run DISTINCT ON project_id

        Returns:
            {"projects": [{project_id, project_name, health_status,
                           coverage_pct, artifact_count, last_run_at}]}
        """
        cache_key = f"dashboard:projects:{tenant_id}"
        redis = get_redis_client()

        try:
            cached_raw = await redis.get(cache_key)
            if cached_raw:
                return json.loads(cached_raw)
        except Exception as exc:
            logger.warning("PM dashboard projects cache read failed", exc=str(exc))

        # 1. Fetch all projects
        projects_result = await db.execute(
            text(
                f"""
                SELECT id, name
                FROM "{schema_name}".projects
                ORDER BY name ASC
                """
            )
        )
        project_rows = projects_result.fetchall()

        # 2. Batch coverage aggregation across all projects in one query
        agg_result = await db.execute(
            text(
                f"""
                SELECT
                    project_id,
                    COUNT(*)                                                            AS artifact_count,
                    COALESCE(SUM((metadata->>'requirements_covered')::int), 0)         AS reqs_covered,
                    COALESCE(SUM((metadata->>'total_requirements')::int), 0)           AS reqs_total
                FROM "{schema_name}".artifacts
                WHERE artifact_type = 'coverage_matrix'
                  AND metadata IS NOT NULL
                  AND metadata ? 'requirements_covered'
                  AND metadata ? 'total_requirements'
                GROUP BY project_id
                """
            )
        )
        agg_by_project: dict[str, Any] = {
            str(row.project_id): row for row in agg_result.fetchall()
        }

        # 3. Batch last agent run timestamp per project (DISTINCT ON avoids subquery)
        run_result = await db.execute(
            text(
                f"""
                SELECT DISTINCT ON (project_id) project_id, created_at
                FROM "{schema_name}".agent_runs
                ORDER BY project_id, created_at DESC
                """
            )
        )
        run_by_project: dict[str, Any] = {
            str(row.project_id): row.created_at for row in run_result.fetchall()
        }

        projects: list[dict] = []
        for p in project_rows:
            pid = str(p.id)
            agg = agg_by_project.get(pid)
            artifact_count = int(agg.artifact_count) if agg else 0
            reqs_covered = int(agg.reqs_covered) if agg else 0
            reqs_total = int(agg.reqs_total) if agg else 0
            coverage_pct = (
                round(reqs_covered / reqs_total * 100, 1) if reqs_total > 0 else None
            )
            last_run_at_dt = run_by_project.get(pid)
            last_run_at = last_run_at_dt.isoformat() if last_run_at_dt else None
            projects.append(
                {
                    "project_id": pid,
                    "project_name": p.name,
                    "health_status": self._compute_health(coverage_pct),
                    "coverage_pct": coverage_pct,
                    "artifact_count": artifact_count,
                    "last_run_at": last_run_at,
                }
            )

        result_dict = {"projects": projects}

        try:
            await redis.set(cache_key, json.dumps(result_dict, default=str), ex=_CACHE_TTL)
        except Exception as exc:
            logger.warning("PM dashboard projects cache write failed", exc=str(exc))

        return result_dict

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _compute_overview(
        self,
        db: AsyncSession,
        schema_name: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Query DB and build the overview dict (no caching here)."""
        # Aggregate coverage_matrix artifacts
        agg_result = await db.execute(
            text(
                f"""
                SELECT
                    COUNT(*)                                                            AS artifact_count,
                    COALESCE(SUM((metadata->>'requirements_covered')::int), 0)         AS reqs_covered,
                    COALESCE(SUM((metadata->>'total_requirements')::int), 0)           AS reqs_total,
                    MAX(created_at)                                                     AS last_artifact_at
                FROM "{schema_name}".artifacts
                WHERE project_id = :pid
                  AND artifact_type = 'coverage_matrix'
                  AND metadata IS NOT NULL
                  AND metadata ? 'requirements_covered'
                  AND metadata ? 'total_requirements'
                """
            ),
            {"pid": project_id},
        )
        agg_row = agg_result.fetchone()

        artifact_count = agg_row.artifact_count if agg_row else 0
        reqs_covered = agg_row.reqs_covered if agg_row else 0
        reqs_total = agg_row.reqs_total if agg_row else 0
        coverage_pct = (
            round(reqs_covered / reqs_total * 100, 1) if reqs_total > 0 else None
        )
        health_status = self._compute_health(coverage_pct)

        # Most recent agent run timestamp
        run_result = await db.execute(
            text(
                f"""
                SELECT created_at
                FROM "{schema_name}".agent_runs
                WHERE project_id = :pid
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"pid": project_id},
        )
        run_row = run_result.fetchone()
        last_run_at = run_row.created_at.isoformat() if run_row and run_row.created_at else None

        return {
            "coverage_pct": coverage_pct,
            "health_status": health_status,
            "requirements_covered": reqs_covered,
            "total_requirements": reqs_total,
            "artifact_count": artifact_count,
            "last_run_at": last_run_at,
        }

    @staticmethod
    def _compute_health(coverage_pct: float | None) -> str:
        """
        AC-30: Map coverage percentage to health status string.

        None   → "no_data"
        >= 80  → "green"
        >= 50  → "yellow"
        < 50   → "red"
        """
        if coverage_pct is None:
            return "no_data"
        if coverage_pct >= 80:
            return "green"
        if coverage_pct >= 50:
            return "yellow"
        return "red"

    @staticmethod
    def _compute_week_over_week(
        current_pct: float | None,
        last_week_pct: float | None,
    ) -> tuple[float | None, str]:
        """
        AC-1: Compute signed week-over-week coverage delta.

        Returns (delta_rounded_1dp, direction) where:
          direction: "up" | "down" | "flat" | "no_data"
        Returns (None, "no_data") if either argument is None.
        """
        if current_pct is None or last_week_pct is None:
            return (None, "no_data")
        delta = round(current_pct - last_week_pct, 1)
        if delta > 0:
            return (delta, "up")
        if delta < 0:
            return (delta, "down")
        return (0.0, "flat")


# Module-level singleton
pm_dashboard_service = PMDashboardService()
