# Story 2.13: PM Dashboard — Test Coverage Metrics

Status: done

## Story

As a PM/CSM,
I want to see test coverage metrics with a week-over-week trend indicator, a drill-down into which requirements lack tests, and a multi-project health grid,
so that I can measure testing completeness, identify coverage gaps, and monitor all projects at a glance.

## Requirements Context

Story 2-12 delivered the single-project `DashboardPage` at `/projects/:projectId/dashboard` with:
- Health indicator dot, coverage % summary, recent activity (AC-30)
- Recharts 30-day `LineChart` + configurable target line (AC-31)
- SSE auto-refresh via `dashboard_refresh` event every 30 s (AC-32)
- Placeholder widgets for Epic 3–4 (AC-33)

Three capabilities remain deferred from 2-12 that this story delivers:

1. **Week-over-week trend indicator (AC-1):** A signed delta badge ("↑ +5.0% from last week" / "↓ -3.2%")
   appended to the coverage widget — new field on existing `GET /dashboard/coverage` response.
2. **Coverage matrix drill-down (AC-2):** Click "View Details →" link → `CoverageMatrixPanel` component shows
   a per-requirement covered/uncovered table sourced from `GET /dashboard/coverage/matrix`. If AI-generated
   content cannot be parsed, falls back to a link to the ArtifactsTab.
3. **Multi-project health grid (AC-3):** New page at `/pm-dashboard` with `GET /api/v1/dashboard/projects`
   (tenant-level, no project_id prefix) — lists all projects the tenant has with their health cards.

**FRs Covered:** FR68 (test coverage metrics), FR67 (continued — multi-project health grid deferred from 2-12)

**Out of Scope:**
- JIRA traceability (Stories 2-15 to 2-17)
- Token budget monitoring (Story 2-18)
- Story 2-14 placeholder widgets (already delivered in 2-12 as AC-33)

**Architecture Constraints:**
- All SQL: `text(f'... "{schema_name}".table ...')` with bound `:params`; schema from `current_tenant_slug` ContextVar
- Per-project dashboard endpoints: RBAC `require_project_role("owner", "admin", "qa-automation", "pm-csm")`
- Tenant-level `GET /api/v1/dashboard/projects`: use `require_role("owner", "admin", "pm-csm")` with `org_id`
  path param (same pattern as `GET /api/v1/admin/analytics` in Story 1-12)
- Do NOT use `"pm"` role string — confirmed role is `"pm-csm"` (RBAC middleware comment line 22)
- Redis cache: extend existing `dashboard:{project_id}` key for trend; new key
  `dashboard:projects:{tenant_id}` (TTL 60 s) for multi-project grid
- `recharts` already installed (`web/package.json` — confirmed in 2-12 completion notes)
- No new DB migration required — all data sourced from existing `artifacts`, `artifact_versions`,
  `agent_runs`, `projects` tables (Migration 015)
- Do NOT copy the L-1 dead variable pattern from `pm_dashboard_service.py:129-137` — clean implementation only

## Acceptance Criteria

| # | Criterion |
|---|---|
| AC-1 | **Week-over-week trend indicator.** `GET /api/v1/projects/{project_id}/dashboard/coverage` response adds two new fields: `week_over_week_pct: float \| null` (signed, e.g. `+5.0` or `-3.2`, rounded to 1 decimal) and `week_over_week_direction: "up" \| "down" \| "flat" \| "no_data"`. Logic: compute coverage % from `artifacts` with `created_at < NOW() - INTERVAL '7 days'` (same `coverage_matrix` + metadata filter as `get_overview`); delta = current_coverage_pct − last_week_pct; direction = `"up"` if delta > 0, `"down"` if delta < 0, `"flat"` if delta == 0, `"no_data"` if either value is `null`. Frontend: `DashboardPage.tsx` renders a badge below the summary string — green "↑ +5.0% from last week" / red "↓ -3.2% from last week" / gray "→ No change" / gray "No trend data yet". `DashboardCoverage` TypeScript interface extended with `week_over_week_pct: number \| null` and `week_over_week_direction: string`. Unit test: `PMDashboardService._compute_week_over_week(current_pct, last_week_pct)` returns `(+5.0, "up")` for `(80.0, 75.0)`, `(-5.0, "down")` for `(70.0, 75.0)`, `(0.0, "flat")` for `(75.0, 75.0)`, `(null, "no_data")` for `(None, 75.0)`. |
| AC-2 | **Coverage matrix drill-down.** New endpoint `GET /api/v1/projects/{project_id}/dashboard/coverage/matrix` returns `{artifact_id: uuid \| null, artifact_title: str \| null, requirements: list[{name: str, covered: bool, test_count: int}], generated_at: str \| null, fallback_url: str \| null}`. Logic: find latest `coverage_matrix` artifact (`ORDER BY created_at DESC LIMIT 1`); join latest `artifact_versions.content`; parse content as JSON; look for a `requirements` key (list of objects with `name`/`id` and `covered`/`test_count` fields); if parseable → populate `requirements` list; if not parseable or no artifact → `requirements = []` and `fallback_url = "/projects/{project_id}/artifacts?type=coverage_matrix"`. Frontend: `DashboardPage.tsx` shows "View Details →" link next to coverage summary. Clicking opens `CoverageMatrixPanel` component (same page, expandable section below coverage chart): table columns `Requirement`, `Status` (green "Covered" / red "Missing"), `Tests`. If `requirements` list is empty: show "No coverage data yet — run AI agents to generate a coverage matrix" with link to AgentsTab. RBAC: same as other dashboard endpoints. Integration test: GET coverage/matrix → 200; response has `artifact_id`, `requirements` (list, may be empty), `fallback_url`. GET coverage/matrix with no auth → 401. |
| AC-3 | **Multi-project health grid.** New tenant-level endpoint `GET /api/v1/dashboard/projects` (registered on a separate router, no `project_id` prefix). Returns `{projects: list[{project_id: str, project_name: str, health_status: str, coverage_pct: float \| null, artifact_count: int, last_run_at: str \| null}]}`. Logic: query all `projects` in `"{schema_name}".projects`; for each project call the same aggregation logic as `get_overview()` (or batch-query across projects); Redis cache key `dashboard:projects:{tenant_id}` TTL 60 s. RBAC: `require_role("owner", "admin", "pm-csm")` with `org_id` path param (endpoint: `GET /api/v1/orgs/{org_id}/dashboard/projects`). Frontend: new `ProjectsGridPage.tsx` at `web/src/pages/dashboard/ProjectsGridPage.tsx`; route `/orgs/:orgId/pm-dashboard`; renders responsive grid of project health cards (reuses `HealthDot` component from `DashboardPage.tsx`); each card links to `/projects/:projectId/dashboard`; empty state: "No projects found". Add import + route in `App.tsx`. Integration test: GET orgs/{org_id}/dashboard/projects → 200; response has `projects` key (list). GET with no auth → 401. |

## Tasks / Subtasks

### Task 1 — Backend: Extend `PMDashboardService` (AC-1, AC-2, AC-3)

- [x] 1.1 Add `_compute_week_over_week(current_pct: float | None, last_week_pct: float | None) -> tuple[float | None, str]` as `@staticmethod` in `PMDashboardService`:
  - Returns `(None, "no_data")` if either arg is `None`
  - Returns `(round(current - last_week, 1), direction)` where direction = `"up"` / `"down"` / `"flat"`

- [x] 1.2 Extend `get_coverage_trend(self, db, schema_name, project_id) -> dict` to also compute week-over-week:
  - Query: same `coverage_matrix` + metadata filter but with `AND created_at < NOW() - INTERVAL '7 days'` for `last_week_pct`
  - Add `week_over_week_pct` and `week_over_week_direction` keys to returned dict
  - Do NOT use dead variable pattern (L-1 from 2-12 review): only retain variables that are actually returned

- [x] 1.3 Add `async def get_coverage_matrix(self, db, schema_name, project_id) -> dict`:
  - Query:
    ```sql
    SELECT a.id, a.title, a.created_at, av.content
    FROM "{schema_name}".artifacts a
    JOIN "{schema_name}".artifact_versions av
      ON av.artifact_id = a.id AND av.version = a.current_version
    WHERE a.project_id = :pid
      AND a.artifact_type = 'coverage_matrix'
    ORDER BY a.created_at DESC
    LIMIT 1
    ```
    params: `pid=project_id`
  - Parse `content` as JSON; extract `requirements` list if present
  - Return `{"artifact_id": str|None, "artifact_title": str|None, "requirements": list, "generated_at": str|None, "fallback_url": f"/projects/{project_id}/artifacts?type=coverage_matrix" if no parseable requirements else None}`
  - Wrap JSON parse in `try/except json.JSONDecodeError` → set `requirements = []`

- [x] 1.4 Add `async def get_all_projects_health(self, db, schema_name, tenant_id) -> dict`:
  - Query all projects:
    ```sql
    SELECT id, name FROM "{schema_name}".projects ORDER BY name ASC
    ```
  - For each project: run the same aggregation as `get_overview()` (reuse private logic or call inline)
  - Attempt Redis cache read first: key `dashboard:projects:{tenant_id}`, TTL 60 s
  - On cache miss: build list, serialize to JSON, write to Redis
  - Return `{"projects": [{"project_id": str, "project_name": str, "health_status": str, "coverage_pct": float|None, "artifact_count": int, "last_run_at": str|None}]}`

### Task 2 — Backend: Extend dashboard schemas (AC-1, AC-2, AC-3)

- [x] 2.1 Extend `DashboardCoverageResponse` in `backend/src/api/v1/dashboard/schemas.py`:
  ```python
  class DashboardCoverageResponse(BaseModel):
      requirements_covered: int
      total_requirements: int
      coverage_pct: Optional[float]
      trend: list[TrendPoint]
      week_over_week_pct: Optional[float]      # NEW — AC-1
      week_over_week_direction: str             # NEW — "up"|"down"|"flat"|"no_data"
  ```

- [x] 2.2 Add new schemas for AC-2 and AC-3:
  ```python
  class RequirementCoverageItem(BaseModel):
      name: str
      covered: bool
      test_count: int

  class CoverageMatrixResponse(BaseModel):
      artifact_id: Optional[str]
      artifact_title: Optional[str]
      requirements: list[RequirementCoverageItem]
      generated_at: Optional[str]
      fallback_url: Optional[str]

  class ProjectHealthItem(BaseModel):
      project_id: str
      project_name: str
      health_status: str
      coverage_pct: Optional[float]
      artifact_count: int
      last_run_at: Optional[str]

  class ProjectsHealthResponse(BaseModel):
      projects: list[ProjectHealthItem]
  ```

### Task 3 — Backend: Extend dashboard router + new org-level router (AC-1, AC-2, AC-3)

- [x] 3.1 Extend `GET /dashboard/coverage` in `backend/src/api/v1/dashboard/router.py`:
  - `DashboardCoverageResponse` now includes the two new AC-1 fields — service already computes them in Task 1.2; no router logic change needed beyond using updated schema

- [x] 3.2 Add `GET /dashboard/coverage/matrix` to `backend/src/api/v1/dashboard/router.py`:
  ```python
  @router.get(
      "/dashboard/coverage/matrix",
      response_model=CoverageMatrixResponse,
  )
  async def get_coverage_matrix(
      project_id: uuid.UUID,
      auth: tuple = Depends(require_project_role("owner", "admin", "qa-automation", "pm-csm")),
      db: AsyncSession = Depends(get_db),
  ) -> CoverageMatrixResponse:
  ```
  - Extract `schema_name` from ContextVar; call `pm_dashboard_service.get_coverage_matrix(db, schema_name, project_id)`

- [x] 3.3 Create `backend/src/api/v1/dashboard/org_router.py` for the tenant-level projects grid:
  ```python
  """
  QUALISYS — PM Dashboard Org-Level API
  Story: 2-13-pm-dashboard-test-coverage-metrics
  AC-3: GET /api/v1/orgs/{org_id}/dashboard/projects
  """
  from fastapi import APIRouter, Depends
  from sqlalchemy.ext.asyncio import AsyncSession
  from src.middleware.rbac import require_role
  from src.api.v1.deps import get_db
  from src.middleware.tenant_context import current_tenant_slug
  from src.services.pm_dashboard_service import pm_dashboard_service
  from .schemas import ProjectsHealthResponse
  import uuid

  org_router = APIRouter(
      prefix="/api/v1/orgs/{org_id}",
      tags=["PM Dashboard"],
  )

  @org_router.get("/dashboard/projects", response_model=ProjectsHealthResponse)
  async def get_projects_health(
      org_id: uuid.UUID,
      auth: tuple = Depends(require_role("owner", "admin", "pm-csm")),
      db: AsyncSession = Depends(get_db),
  ) -> ProjectsHealthResponse:
      schema_name = slug_to_schema_name(current_tenant_slug.get())
      tenant_id = auth[1].tenant_id  # TenantUser.tenant_id from require_role tuple
      return await pm_dashboard_service.get_all_projects_health(db, schema_name, str(tenant_id))
  ```

### Task 4 — Backend: Register new org router in main.py (AC-3)

- [x] 4.1 Add to `backend/src/main.py` after the existing `dashboard_router` block:
  ```python
  # Story 2.13 — PM Dashboard org-level (multi-project grid)
  from src.api.v1.dashboard.org_router import org_router as pm_org_dashboard_router  # noqa: E402
  app.include_router(pm_org_dashboard_router)
  ```

### Task 5 — Frontend: Extend `api.ts` (AC-1, AC-2, AC-3)

- [x] 5.1 Extend `DashboardCoverage` interface in `web/src/lib/api.ts`:
  ```typescript
  export interface DashboardCoverage {
    requirements_covered: number
    total_requirements: number
    coverage_pct: number | null
    trend: TrendPoint[]
    week_over_week_pct: number | null      // AC-1
    week_over_week_direction: string        // "up" | "down" | "flat" | "no_data"
  }
  ```

- [x] 5.2 Add new types and API functions:
  ```typescript
  export interface RequirementCoverageItem {
    name: string
    covered: boolean
    test_count: number
  }

  export interface CoverageMatrixData {
    artifact_id: string | null
    artifact_title: string | null
    requirements: RequirementCoverageItem[]
    generated_at: string | null
    fallback_url: string | null
  }

  export interface ProjectHealthItem {
    project_id: string
    project_name: string
    health_status: 'green' | 'yellow' | 'red' | 'no_data'
    coverage_pct: number | null
    artifact_count: number
    last_run_at: string | null
  }

  export interface ProjectsHealthData {
    projects: ProjectHealthItem[]
  }

  export const dashboardApi = {
    // existing:
    getOverview: (projectId: string): Promise<DashboardOverview> =>
      api.get(`/projects/${projectId}/dashboard/overview`).then((r) => r.data),
    getCoverage: (projectId: string): Promise<DashboardCoverage> =>
      api.get(`/projects/${projectId}/dashboard/coverage`).then((r) => r.data),
    // new:
    getCoverageMatrix: (projectId: string): Promise<CoverageMatrixData> =>
      api.get(`/projects/${projectId}/dashboard/coverage/matrix`).then((r) => r.data),
    getProjectsHealth: (orgId: string): Promise<ProjectsHealthData> =>
      api.get(`/orgs/${orgId}/dashboard/projects`).then((r) => r.data),
  }
  ```

### Task 6 — Frontend: Extend `DashboardPage.tsx` (AC-1, AC-2)

- [x] 6.1 Add `TrendBadge` helper component in `DashboardPage.tsx`:
  ```typescript
  function TrendBadge({ direction, pct }: {
    direction: string
    pct: number | null
  }) {
    if (direction === 'no_data') return <span className="text-xs text-gray-400">No trend data yet</span>
    if (direction === 'flat') return <span className="text-xs text-gray-500">→ No change from last week</span>
    const isUp = direction === 'up'
    const arrow = isUp ? '↑' : '↓'
    const colour = isUp ? 'text-green-600' : 'text-red-600'
    return (
      <span className={`text-xs font-medium ${colour}`}>
        {arrow} {Math.abs(pct ?? 0).toFixed(1)}% from last week
      </span>
    )
  }
  ```

- [x] 6.2 Render `TrendBadge` below coverage summary string in the coverage trend section:
  ```tsx
  <TrendBadge direction={coverage?.week_over_week_direction ?? 'no_data'} pct={coverage?.week_over_week_pct ?? null} />
  ```

- [x] 6.3 Add `showMatrix` state and `CoverageMatrixPanel` integration:
  ```typescript
  const [showMatrix, setShowMatrix] = useState(false)
  const { data: matrixData } = useQuery({
    queryKey: ['coverage-matrix', projectId],
    queryFn: () => dashboardApi.getCoverageMatrix(projectId!),
    enabled: showMatrix,
  })
  ```
  - Add "View Details →" button/link below coverage summary line:
    `<button onClick={() => setShowMatrix(true)} className="text-xs text-indigo-600 underline ml-2">View Details →</button>`
  - Render `<CoverageMatrixPanel data={matrixData} projectId={projectId!} />` below coverage chart when `showMatrix && matrixData`

### Task 7 — Frontend: New `CoverageMatrixPanel.tsx` component (AC-2)

- [x] 7.1 Create `web/src/pages/projects/dashboard/CoverageMatrixPanel.tsx`:
  ```typescript
  import { CoverageMatrixData } from '@/lib/api'

  interface Props {
    data: CoverageMatrixData | undefined
    projectId: string
  }

  export function CoverageMatrixPanel({ data, projectId }: Props) {
    if (!data) return null

    if (data.requirements.length === 0) {
      return (
        <div className="mt-4 rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
          No coverage data yet — run AI agents to generate a coverage matrix.{' '}
          {data.fallback_url && (
            <a href={data.fallback_url} className="text-indigo-600 underline">View Artifacts →</a>
          )}
        </div>
      )
    }

    return (
      <div className="mt-4 rounded border border-gray-200 overflow-hidden">
        <div className="bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700">
          Coverage Matrix — {data.artifact_title ?? 'Latest'}
          {data.generated_at && (
            <span className="ml-2 text-xs text-gray-400">
              Generated {new Date(data.generated_at).toLocaleDateString()}
            </span>
          )}
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-100 text-left text-xs text-gray-500">
              <th className="px-4 py-2">Requirement</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Tests</th>
            </tr>
          </thead>
          <tbody>
            {data.requirements.map((req, i) => (
              <tr key={i} className="border-t border-gray-100">
                <td className="px-4 py-2 text-gray-800">{req.name}</td>
                <td className="px-4 py-2">
                  {req.covered
                    ? <span className="text-green-600 font-medium">✅ Covered</span>
                    : <span className="text-red-600 font-medium">❌ Missing</span>}
                </td>
                <td className="px-4 py-2 text-gray-500">{req.test_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }
  ```

### Task 8 — Frontend: New `ProjectsGridPage.tsx` (AC-3)

- [x] 8.1 Create `web/src/pages/dashboard/ProjectsGridPage.tsx`:
  - Import: `useQuery` from `@tanstack/react-query`; `useParams`, `Link` from `react-router-dom`; `dashboardApi, ProjectHealthItem` from `@/lib/api`
  - Reuse `HealthDot` component — import from `../projects/dashboard/DashboardPage` OR extract `HealthDot` to a shared file (e.g. `web/src/components/dashboard/HealthDot.tsx`) and update both pages to import from there
  - `const { orgId } = useParams<{ orgId: string }>()`
  - `const { data, isLoading } = useQuery({ queryKey: ['projects-health', orgId], queryFn: () => dashboardApi.getProjectsHealth(orgId!), staleTime: 60_000 })`
  - Empty state: "No projects found"
  - Loading state: 3 skeleton cards
  - Grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`
  - Each card: white rounded border card with `HealthDot`, project name, coverage % or "No data", last run relative time, `Link` to `/projects/{project_id}/dashboard`

### Task 9 — Frontend: Register new route in `App.tsx` (AC-3)

- [x] 9.1 Add import:
  ```typescript
  import ProjectsGridPage from '@/pages/dashboard/ProjectsGridPage'
  ```

- [x] 9.2 Add route (after the `/projects/:projectId/dashboard` route):
  ```tsx
  {/* Story 2.13 — PM/CSM multi-project health grid */}
  <Route path="/orgs/:orgId/pm-dashboard" element={<ProjectsGridPage />} />
  ```

### Task 10 — Tests (AC-1, AC-2, AC-3)

- [x] 10.1 `backend/tests/unit/services/test_pm_dashboard_service.py` — add 4 unit tests:
  - `test_compute_week_over_week_up` — `_compute_week_over_week(80.0, 75.0)` → `(5.0, "up")`
  - `test_compute_week_over_week_down` — `_compute_week_over_week(70.0, 75.0)` → `(-5.0, "down")`
  - `test_compute_week_over_week_flat` — `_compute_week_over_week(75.0, 75.0)` → `(0.0, "flat")`
  - `test_compute_week_over_week_no_data` — `_compute_week_over_week(None, 75.0)` → `(None, "no_data")`

- [x] 10.2 `backend/tests/integration/test_dashboard.py` — add 7 integration tests (extend existing file):
  - `test_get_coverage_trend_includes_week_over_week_200` — Seed artifacts with some older than 7 days; GET coverage → 200; assert response has `week_over_week_pct` key and `week_over_week_direction` key.
  - `test_get_coverage_trend_no_data_direction` — No artifacts older than 7 days; GET coverage → 200; assert `week_over_week_direction == "no_data"`.
  - `test_get_coverage_matrix_200` — Seed one `coverage_matrix` artifact with parseable content `{"requirements": [{"name": "REQ-001", "covered": true, "test_count": 3}]}`; GET coverage/matrix → 200; assert `requirements[0]["name"] == "REQ-001"`.
  - `test_get_coverage_matrix_no_artifact_200` — No artifacts; GET coverage/matrix → 200; assert `requirements == []` and `fallback_url` is not null.
  - `test_get_coverage_matrix_rbac_401` — No auth; GET coverage/matrix → 401.
  - `test_get_projects_health_200` — GET `/api/v1/orgs/{org_id}/dashboard/projects` with valid auth; assert 200; response has `projects` key (list).
  - `test_get_projects_health_rbac_401` — No auth; GET projects health → 401.

## Dev Notes

### Week-Over-Week Calculation Pattern

Extend `get_coverage_trend()` — compute `last_week_pct` via a secondary query in the same method:
```python
last_week_result = await db.execute(text("""
    SELECT
        COALESCE(SUM((metadata->>'requirements_covered')::int), 0) AS covered,
        COALESCE(SUM((metadata->>'total_requirements')::int), 0)   AS total
    FROM "{schema_name}".artifacts
    WHERE project_id = :pid
      AND artifact_type = 'coverage_matrix'
      AND created_at < NOW() - INTERVAL '7 days'
      AND metadata ? 'requirements_covered'
"""), {"pid": project_id})
row = last_week_result.fetchone()
last_week_pct = round(row.covered / row.total * 100, 1) if row.total > 0 else None
wow_pct, wow_dir = PMDashboardService._compute_week_over_week(coverage_pct, last_week_pct)
```
Do NOT dead-accumulate variables. Only assign what is returned.

### Coverage Matrix Content Parsing

BAConsultant stores artifact content as JSON text in `artifact_versions.content`. Expected schema:
```json
{
  "requirements": [
    {"name": "REQ-001: User can log in", "covered": true, "test_count": 3},
    {"name": "REQ-002: Password reset flow", "covered": false, "test_count": 0}
  ]
}
```
Parse defensively — wrap in `try/except (json.JSONDecodeError, KeyError, TypeError)`. If parsing fails or
`requirements` key is missing, set `requirements = []` and return `fallback_url`.

### `require_role` for Org-Level Endpoint

The `require_role()` dependency in `backend/src/middleware/rbac.py` accepts `org_id` as a path parameter
(used by `/api/v1/orgs/{org_id}/...` pattern). Use:
```python
auth: tuple = Depends(require_role("owner", "admin", "pm-csm"))
```
Returns `(User, TenantUser)`. Extract `tenant_id` from `auth[1].tenant_id`. Schema name:
`slug_to_schema_name(current_tenant_slug.get())` (same ContextVar set by `TenantContextMiddleware`).

### HealthDot Component Extraction (Optional)

If `HealthDot` is extracted to a shared component (`web/src/components/dashboard/HealthDot.tsx`),
update both `DashboardPage.tsx` and `ProjectsGridPage.tsx` imports. If extraction adds scope, keep
`HealthDot` in `DashboardPage.tsx` and import it directly in `ProjectsGridPage.tsx` — this is acceptable
for MVP.

### Redis Cache for Multi-Project Grid

```python
cache_key = f"dashboard:projects:{tenant_id}"
redis = get_redis_client()
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)
# ... compute list ...
await redis.set(cache_key, json.dumps(result), ex=60)
```
Matches existing `dashboard:{project_id}` pattern from `PMDashboardService.get_overview()`.

### Project Structure Notes

**New files:**
- `backend/src/api/v1/dashboard/org_router.py`
- `web/src/pages/projects/dashboard/CoverageMatrixPanel.tsx`
- `web/src/pages/dashboard/ProjectsGridPage.tsx`
- *(Optional)* `web/src/components/dashboard/HealthDot.tsx`

**Modified:**
- `backend/src/services/pm_dashboard_service.py` — Add `_compute_week_over_week()`, `get_coverage_matrix()`, `get_all_projects_health()`, extend `get_coverage_trend()`
- `backend/src/api/v1/dashboard/router.py` — Add `GET /dashboard/coverage/matrix`
- `backend/src/api/v1/dashboard/schemas.py` — Extend `DashboardCoverageResponse`; add `RequirementCoverageItem`, `CoverageMatrixResponse`, `ProjectHealthItem`, `ProjectsHealthResponse`
- `backend/src/main.py` — Register `pm_org_dashboard_router`
- `web/src/lib/api.ts` — Extend `DashboardCoverage`; add new types + `getCoverageMatrix`, `getProjectsHealth`
- `web/src/pages/projects/dashboard/DashboardPage.tsx` — Add `TrendBadge`, `showMatrix` state, `CoverageMatrixPanel` import + render
- `web/src/App.tsx` — Add `/orgs/:orgId/pm-dashboard` route
- `backend/tests/unit/services/test_pm_dashboard_service.py` — Add 4 unit tests
- `backend/tests/integration/test_dashboard.py` — Add 7 integration tests
- `docs/sprint-status.yaml` — Update `2-13` status to `drafted`

### Learnings from Previous Story (2-12)

**From Story 2-12 (Status: done)**

- **`PMDashboardService` base is complete** — `get_overview()`, `get_coverage_trend()`, `_compute_health()` all implemented at `backend/src/services/pm_dashboard_service.py`. Extend, don't recreate. [Source: `backend/src/services/pm_dashboard_service.py`]
- **L-1 advisory: dead variable anti-pattern** — `pm_dashboard_service.py:129-137` accumulates `total_covered`/`total_reqs` from trend rows but overrides them. Do NOT replicate this pattern. Only assign variables that are returned. [Source: `docs/stories/epic-2/2-12-pm-csm-dashboard-project-health-overview.md#L-1`]
- **`recharts` confirmed installed** — No `npm install` needed. `LineChart`, `BarChart`, `ResponsiveContainer` available. [Source: 2-12 Completion Notes]
- **`dashboardApi` namespace in `api.ts`** — Extend by adding `getCoverageMatrix` and `getProjectsHealth` to the existing `dashboardApi` object (don't create a new namespace). [Source: `web/src/lib/api.ts`]
- **React Query patterns established** — `useQuery` with `queryKey` arrays, `staleTime: 30_000`–`60_000` pattern. For lazy-loaded matrix panel, set `enabled: showMatrix` so the query only fires on user action. [Source: `web/src/pages/projects/dashboard/DashboardPage.tsx`]
- **`require_role` for tenant endpoints** — `require_role("owner", "admin", ...)` with `org_id` path param. Returns `(User, TenantUser)`. Used in Analytics router (`backend/src/api/v1/admin/router.py`). [Source: Story 1-12]
- **Pre-existing test failures** in `test_backup_code_service.py` / `test_profile_service.py` are unrelated — ignore. [Source: 2-12 Completion Notes]

[Source: docs/stories/epic-2/2-12-pm-csm-dashboard-project-health-overview.md#Dev-Agent-Record]

### References

- Epic 2 tech-spec: `docs/stories/epic-2/tech-spec-epic-2.md#6-1-performance` (cache TTLs)
- Tech-spec API definitions: `docs/stories/epic-2/tech-spec-epic-2.md#4-services-data-models--apis`
- Tech-spec PM Dashboard scope: `docs/stories/epic-2/tech-spec-epic-2.md#2-objectives--scope`
- Story 2-12 (predecessor): `docs/stories/epic-2/2-12-pm-csm-dashboard-project-health-overview.md`
- `PMDashboardService`: `backend/src/services/pm_dashboard_service.py`
- Dashboard router: `backend/src/api/v1/dashboard/router.py`
- Dashboard schemas: `backend/src/api/v1/dashboard/schemas.py`
- Analytics router (require_role pattern): `backend/src/api/v1/admin/router.py`
- `DashboardPage.tsx`: `web/src/pages/projects/dashboard/DashboardPage.tsx`
- `api.ts`: `web/src/lib/api.ts`
- `App.tsx` (route registration): `web/src/App.tsx`
- Migration 015 (artifacts + artifact_versions): `backend/alembic/versions/015_create_agent_runs_and_artifacts.py`
- Epics: `docs/epics/epics.md` — Story 2.13 definition at line 662

## Dev Agent Record

### Context Reference

- docs/stories/epic-2/2-13-pm-dashboard-test-coverage-metrics.context.xml

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **All 22 tests passing**: 10 unit (including 4 new _compute_week_over_week tests) + 12 integration (including 7 new AC-1/2/3 tests)
- **`_setup_db_session` extended** with `last_week_row`, `matrix_row`, `project_rows` params to route new SQL patterns
- **Fix applied**: `require_role()` already returns a `Depends` object — used directly as default param, NOT wrapped in `Depends()` (same pattern as all other existing org-level routers)
- **Dead variable pattern avoided** (C4): removed `total_covered`/`total_reqs` accumulation loop from `get_coverage_trend()` — only variables actually returned are assigned
- **`HealthDot` + `formatRelative`** duplicated in `ProjectsGridPage.tsx` to avoid cross-page imports (MVP approach per story notes)
- **Redis cache**: `dashboard:projects:{tenant_id}` key with TTL 60s wraps full project list computation

### File List

**Modified:**
- `backend/src/services/pm_dashboard_service.py` — added `_compute_week_over_week()`, `get_coverage_matrix()`, `get_all_projects_health()`; extended `get_coverage_trend()` with week-over-week query
- `backend/src/api/v1/dashboard/schemas.py` — extended `DashboardCoverageResponse`; added `RequirementCoverageItem`, `CoverageMatrixResponse`, `ProjectHealthItem`, `ProjectsHealthResponse`
- `backend/src/api/v1/dashboard/router.py` — added `GET /dashboard/coverage/matrix` endpoint
- `backend/src/main.py` — registered `pm_org_dashboard_router`
- `web/src/lib/api.ts` — extended `DashboardCoverage`; added new types + `getCoverageMatrix`, `getProjectsHealth`
- `web/src/pages/projects/dashboard/DashboardPage.tsx` — added `TrendBadge`, `showMatrix` state, `CoverageMatrixPanel` render
- `web/src/App.tsx` — added `/orgs/:orgId/pm-dashboard` route
- `backend/tests/unit/services/test_pm_dashboard_service.py` — added 4 unit tests
- `backend/tests/integration/test_dashboard.py` — added 7 integration tests

**New files:**
- `backend/src/api/v1/dashboard/org_router.py`
- `web/src/pages/projects/dashboard/CoverageMatrixPanel.tsx`
- `web/src/pages/dashboard/ProjectsGridPage.tsx`

## Senior Developer Review (AI)

**Reviewer:** DEV Agent (Amelia) — code-review workflow
**Date:** 2026-03-02
**Outcome:** ✅ APPROVED

### Acceptance Criteria Results

| AC | Result | Evidence |
|----|--------|----------|
| AC-1: week-over-week trend indicator | ✅ PASS | `pm_dashboard_service.py:420-439` (static method), `pm_dashboard_service.py:172-204` (secondary query), `schemas.py:36-37`, `DashboardPage.tsx:64-79,242-247` |
| AC-2: coverage matrix drill-down endpoint + panel | ✅ PASS | `router.py:65-77`, `pm_dashboard_service.py:206-275`, `CoverageMatrixPanel.tsx:14-66`, `DashboardPage.tsx:115-120,272-274` |
| AC-3: multi-project health grid | ✅ PASS | `org_router.py:25-38`, `pm_dashboard_service.py:277-335`, `ProjectsGridPage.tsx:87-118`, `App.tsx:75` |

### Test Results

- **Unit tests:** 10/10 passing (including 4 new `_compute_week_over_week` boundary tests)
- **Integration tests:** 12/12 passing (including 7 new AC-1/2/3 tests)
- **Total:** 22/22 ✅

### Findings

| # | Severity | Finding |
|---|----------|---------|
| M1 | MINOR | `pm_dashboard_service.py:331` — `get_all_projects_health()` uses `ex=60` literal instead of `_CACHE_TTL` constant. Functionally identical but inconsistent with `get_overview()` (L84). |
| M2 | MINOR | `test_dashboard.py:347` — `test_get_coverage_trend_includes_week_over_week_200` checks field presence only, not computed value (expected 20.0 / "up"). Unit tests cover the math correctly. |
| O1 | OBS | N+1 query in `get_all_projects_health()` — 2 DB queries per project. Acceptable for MVP, track for Epic 3 batch optimization. |
| O2 | OBS | `HealthDot` + `formatRelative` duplicated in `ProjectsGridPage.tsx` — intentional (MVP approach, per Dev Notes). |

### Security Sign-off

- SQL injection: all queries parameterized ✅
- Tenant isolation: `schema_name` from trusted ContextVar ✅
- `fallback_url` XSS: constructed from UUID only ✅
- RBAC: org-level (`require_role`) vs project-level (`require_project_role`) correctly differentiated ✅
- `require_role()` double-Depends bug caught and fixed during implementation ✅

### Summary

All 3 acceptance criteria fully implemented. No architectural violations. No security issues. Two minor non-blocking observations noted above for future improvement. Story is approved for done status.

## Change Log

| Date | Change | By |
|------|--------|----|
| 2026-03-02 | Story created | SM Agent (Bob) |
| 2026-03-02 | Story implemented — all tasks complete, 22 tests passing, status → review | DEV Agent (Amelia) |
| 2026-03-02 | Code review complete — APPROVED, status → done | DEV Agent (Amelia) |
| 2026-03-02 | All review findings fixed: M1 (_CACHE_TTL), M2 (test value assertions), O1 (batch queries 2N→3), O2 (shared HealthDot/formatRelative) — 22/22 tests passing | DEV Agent (Amelia) |
