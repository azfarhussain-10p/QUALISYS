# Story 2.10: Test Artifact Storage & Viewer

Status: ready-for-dev

## Story

As a QA-Automation user,
I want to view generated test artifacts organized by type,
so that I can review all AI-generated test outputs (coverage matrix, checklists, scripts, BDD scenarios) from a single tabbed interface after a pipeline run completes.

## Requirements Context

Stories 2-6 through 2-9 delivered:
- Agent pipeline creation, orchestration, and execution (BAConsultant → QAConsultant → AutomationConsultant)
- `_create_artifact()` in orchestrator INSERTs to `artifacts` + `artifact_versions` tables (AC-17g, returning artifact_id)
- SSE real-time progress; AC-21 navigates to Artifacts page on `all_done=true`
- Migration 015: `artifacts` and `artifact_versions` tables exist in all `tenant_%` schemas

**Two problems to solve in this story:**

1. **Artifact type alignment (AC-22–25):** Current agent `ARTIFACT_TYPE` constants do not match the tech spec values used in the viewer tabs. The mapping is:

   | Agent | Current constant | Required (tech-spec) |
   |---|---|---|
   | BAConsultantAgent | `"requirements_matrix"` | `"coverage_matrix"` |
   | QAConsultantAgent | `"test_checklists"` | `"manual_checklist"` |
   | AutomationConsultantAgent | `"playwright_scripts"` | `"playwright_script"` |
   | QAConsultantAgent (BDD) | *(not implemented)* | `"bdd_scenario"` (AC-25) |

2. **Artifact viewer (AC-26):** No API (`ArtifactService`) or frontend page (`ArtifactsTab`) exists yet.

**FRs Covered:** FR31 (store outputs), FR32–FR35 (each agent stores its type), FR38 (view artifacts by type)

**Out of Scope:**
- Monaco editor / save-edit (Story 2-11: AC-27–29)
- Version history diff view (Story 2-11)
- JIRA traceability links (Story 2-17)

**Architecture Constraints:**
- All SQL: `text(f'... "{schema_name}".table ...')` with bound `:params`; schema_name from validated `current_tenant_slug` ContextVar
- RBAC: `require_project_role("owner", "admin", "qa-automation")` on all artifact endpoints
- BDD artifact: QAConsultant runs a secondary LLM call (separate system prompt); orchestrator calls `run_bdd()` after `run()` and creates a second artifact row — **two LLM calls, two artifact rows per QA step**
- Content-type mapping: `coverage_matrix` → `"application/json"`, `manual_checklist` → `"text/markdown"`, `playwright_script` → `"text/typescript"`, `bdd_scenario` → `"text/plain"`

## Acceptance Criteria

| # | Criterion |
|---|---|
| AC-22 | BAConsultant agent stores artifact with `artifact_type = 'coverage_matrix'` (JSON array of `{requirement_id, description, source, coverage_status, notes}` objects). Unit test: mock LLM, assert `artifact_type == 'coverage_matrix'` and content is parseable JSON array. |
| AC-23 | QAConsultant agent stores artifact with `artifact_type = 'manual_checklist'` (Markdown). Unit test: mock LLM, assert `artifact_type == 'manual_checklist'` and content contains `# Manual Test Checklists` header. |
| AC-24 | AutomationConsultant agent stores artifact with `artifact_type = 'playwright_script'` (TypeScript). Unit test: mock LLM, assert `artifact_type == 'playwright_script'` and content contains `import { test, expect }`. |
| AC-25 | QAConsultant also generates a BDD scenario artifact (`artifact_type = 'bdd_scenario'`, plain text Gherkin). Orchestrator calls `qa_consultant.run_bdd()` after `run()`; creates a second artifact row in same DB transaction. Unit test: mock LLM twice, assert two artifacts created — one `manual_checklist`, one `bdd_scenario` with `Scenario:` in content. |
| AC-26 | `GET /api/v1/projects/{project_id}/artifacts` returns list of artifacts with metadata. `GET /api/v1/projects/{project_id}/artifacts/{id}` returns artifact detail + current version content. Both endpoints require `require_project_role("owner","admin","qa-automation")`. Integration test: seed DB, assert list response contains `artifact_type`, `agent_type`, `title`, `current_version`, `metadata.tokens_used`, `created_at`. |
| AC-26b | Artifact viewer page (`/projects/:projectId/artifacts`) shows 4 tabs: Coverage Matrix, Manual Checklists, Playwright Scripts, BDD Scenarios. Each tab lists artifacts filtered by `artifact_type`. Each artifact card shows: agent name, created_at (human-readable), tokens_used (from metadata), version badge. |
| AC-26c | Each tab shows an appropriate empty state when no artifacts of that type exist (e.g., "No coverage matrix generated yet. Run the BA Consultant agent."). |
| AC-26d | Artifact content is displayed in the appropriate format: Coverage Matrix → `<table>` rendered from JSON; Manual Checklists + BDD → `<pre>` block; Playwright Scripts → `<pre>` block with `font-mono` styling. |

## Tasks / Subtasks

### Task 1 — Fix artifact_type constants in agent files (AC-22, AC-23, AC-24)

- [ ] 1.1 `backend/src/services/agents/ba_consultant.py`: Change `ARTIFACT_TYPE = "requirements_matrix"` → `"coverage_matrix"`. Change `CONTENT_TYPE = "json"` → `"application/json"`. [AC-22]
- [ ] 1.2 `backend/src/services/agents/qa_consultant.py`: Change `ARTIFACT_TYPE = "test_checklists"` → `"manual_checklist"`. Change `CONTENT_TYPE = "markdown"` → `"text/markdown"`. [AC-23]
- [ ] 1.3 `backend/src/services/agents/automation_consultant.py`: Change `ARTIFACT_TYPE = "playwright_scripts"` → `"playwright_script"`. Change `CONTENT_TYPE = "typescript"` → `"text/typescript"`. [AC-24]

### Task 2 — Add BDD scenario generation to QAConsultant (AC-25)

- [ ] 2.1 `backend/src/services/agents/qa_consultant.py`: Add constants `BDD_ARTIFACT_TYPE = "bdd_scenario"`, `BDD_CONTENT_TYPE = "text/plain"`, `BDD_TITLE = "BDD/Gherkin Test Scenarios"`.
- [ ] 2.2 `backend/src/services/agents/qa_consultant.py`: Add `BDD_SYSTEM_PROMPT` (Gherkin format: `Feature:` / `Scenario:` / `Given` / `When` / `Then`). Add `run_bdd(context, tenant_id, context_hash)` → `LLMResult` — same pattern as `run()` but using `BDD_SYSTEM_PROMPT` and `agent_type="qa_consultant_bdd"` for cache key separation.
- [ ] 2.3 `backend/src/services/agents/orchestrator.py`: In `_run_agent_step()`, after storing primary artifact for `qa_consultant`, detect if agent is `qa_consultant` and call `agent.run_bdd(context, tenant_id, context_hash=context_hash)`. Build a secondary `AgentResult` using BDD constants. Call `_create_artifact()` again for the BDD result. Accumulate `tokens_used` from both calls into step totals. [AC-25]
- [ ] 2.4 `backend/src/services/agents/orchestrator.py`: Ensure BDD `_create_artifact()` call uses `artifact_type="bdd_scenario"`, `content_type="text/plain"`, `title="BDD/Gherkin Test Scenarios"`, same `run_id` and `project_id`.

### Task 3 — Implement ArtifactService (AC-26)

- [ ] 3.1 Create `backend/src/services/artifact_service.py` with class `ArtifactService`:
  - `list_artifacts(db, schema_name, project_id, artifact_type=None)` → `list[dict]`
    - `SELECT id, agent_type, artifact_type, title, current_version, metadata, created_by, created_at, updated_at FROM "{schema_name}".artifacts WHERE project_id = :pid [AND artifact_type = :at] ORDER BY created_at DESC`
  - `get_artifact(db, schema_name, project_id, artifact_id)` → `dict` (includes current version content)
    - JOIN `artifacts` + `artifact_versions` on `version = current_version`
    - Raise `HTTPException(404, {"error": "ARTIFACT_NOT_FOUND"})` if not found or wrong project_id
  - `list_versions(db, schema_name, project_id, artifact_id)` → `list[dict]`
    - Verify artifact belongs to project; SELECT all versions ordered by version DESC
  - `get_version(db, schema_name, project_id, artifact_id, version)` → `dict`
    - Raise `HTTPException(404, {"error": "VERSION_NOT_FOUND"})` if version missing
  - Instantiate singleton: `artifact_service = ArtifactService()`

### Task 4 — Create artifacts API router (AC-26)

- [ ] 4.1 Create `backend/src/api/v1/artifacts/__init__.py` (empty).
- [ ] 4.2 Create `backend/src/api/v1/artifacts/schemas.py` with Pydantic models:
  - `ArtifactVersionSummary`: `id, version, content_type, edited_by, created_at`
  - `ArtifactSummary`: `id, agent_type, artifact_type, title, current_version, metadata, created_at, updated_at`
  - `ArtifactDetail(ArtifactSummary)`: adds `content: str, content_type: str`
- [ ] 4.3 Create `backend/src/api/v1/artifacts/router.py` with:
  - `GET /api/v1/projects/{project_id}/artifacts` — query param `artifact_type: Optional[str] = None`; returns `list[ArtifactSummary]`
  - `GET /api/v1/projects/{project_id}/artifacts/{artifact_id}` — returns `ArtifactDetail`
  - `GET /api/v1/projects/{project_id}/artifacts/{artifact_id}/versions` — returns `list[ArtifactVersionSummary]`
  - `GET /api/v1/projects/{project_id}/artifacts/{artifact_id}/versions/{version}` — returns `ArtifactDetail`
  - All endpoints: `require_project_role("owner", "admin", "qa-automation")` dependency
  - All endpoints: resolve `schema_name` via `slug_to_schema_name(current_tenant_slug.get())`
- [ ] 4.4 `backend/src/main.py`: Import and register `artifacts_router` under prefix `/api/v1`.

### Task 5 — Frontend: artifact API client (AC-26b)

- [ ] 5.1 `web/src/lib/api.ts`: Add types `ArtifactSummary`, `ArtifactDetail`, `ArtifactVersionSummary`.
- [ ] 5.2 `web/src/lib/api.ts`: Add `artifactApi` namespace:
  - `list(projectId, artifactType?)` → `GET /projects/{id}/artifacts?artifact_type={type}`
  - `get(projectId, artifactId)` → `GET /projects/{id}/artifacts/{aid}`
  - `listVersions(projectId, artifactId)` → `GET /projects/{id}/artifacts/{aid}/versions`
  - `getVersion(projectId, artifactId, version)` → `GET /projects/{id}/artifacts/{aid}/versions/{v}`

### Task 6 — Frontend: ArtifactsTab page (AC-26, AC-26b, AC-26c, AC-26d)

- [ ] 6.1 Create `web/src/pages/projects/artifacts/ArtifactsTab.tsx`:
  - Tab state: `activeTab: 'coverage_matrix' | 'manual_checklist' | 'playwright_script' | 'bdd_scenario'`
  - Four tab buttons; active tab highlighted
  - Per-tab: `useQuery` calling `artifactApi.list(projectId, activeTab)` — re-fetches on tab switch
  - Loading state: spinner while query pending
  - Empty state: contextual message per tab (e.g., "No Playwright scripts yet. Run the Automation Consultant agent.")
  - Artifact card: title, agent name badge, `created_at` (formatted), `metadata.tokens_used` if present, version badge
  - On card click: expand to show content inline — JSON → `<table>` for `coverage_matrix`; `<pre className="font-mono text-sm">` for all others
- [ ] 6.2 Register ArtifactsTab in project page routing/navigation so the Agents tab's AC-21 navigation (`/projects/:id/artifacts`) resolves correctly.

### Task 7 — Unit & Integration Tests (AC-22 through AC-26)

- [ ] 7.1 `backend/tests/unit/services/test_artifact_service.py` (≥4 tests):
  - `test_list_artifacts_returns_rows` — Proves: `list_artifacts()` executes SELECT and maps rows to dicts.
  - `test_get_artifact_returns_detail_with_content` — Proves: JOIN returns content from `artifact_versions` at `current_version`.
  - `test_get_artifact_raises_404_wrong_project` — Proves: artifact owned by different project → `HTTPException(404)`.
  - `test_list_versions_ordered_desc` — Proves: versions returned latest-first.
- [ ] 7.2 `backend/tests/unit/services/test_orchestrator.py`: Add `test_qa_consultant_creates_two_artifacts` — mock `qa_consultant.run()` + `run_bdd()` + `_create_artifact()` twice; assert two artifact INSERTs with types `manual_checklist` and `bdd_scenario`. [AC-25]
- [ ] 7.3 `backend/tests/unit/services/test_orchestrator.py`: Add `test_artifact_type_constants_match_spec` — import all three agent modules; assert `ba_consultant.ARTIFACT_TYPE == "coverage_matrix"`, `qa_consultant.ARTIFACT_TYPE == "manual_checklist"`, `automation_consultant.ARTIFACT_TYPE == "playwright_script"`. [AC-22, AC-23, AC-24]
- [ ] 7.4 `backend/tests/integration/test_documents.py` (reuse pattern) — create `backend/tests/integration/test_artifacts.py` (≥4 tests):
  - `test_list_artifacts_empty` — Proves: GET /artifacts with no seeded data → 200, empty list.
  - `test_list_artifacts_with_type_filter` — Proves: seed 2 artifacts (coverage_matrix + manual_checklist); filter by coverage_matrix → only 1 returned.
  - `test_get_artifact_detail_includes_content` — Proves: GET /artifacts/{id} returns `content` field from artifact_versions.
  - `test_get_artifact_404_unknown_id` — Proves: unknown artifact_id → 404 ARTIFACT_NOT_FOUND.
- [ ] 7.5 Update `docs/sprint-status.yaml`: set `2-10-test-artifact-storage-viewer` → `drafted`.

## Dev Notes

### Architecture: BDD Secondary Artifact Pattern

The orchestrator's `_run_agent_step()` currently calls `_create_artifact()` once per agent step. For `qa_consultant`, this story adds a second artifact. The safest approach (no orchestrator signature change):

```python
# In _run_agent_step(), after primary artifact created:
if agent_type == "qa_consultant":
    bdd_result_llm = await agent.run_bdd(context, tenant_id, context_hash=context_hash)
    bdd_result = AgentResult(
        content=bdd_result_llm.content,
        tokens_used=bdd_result_llm.tokens_used,
        cost_usd=bdd_result_llm.cost_usd,
        artifact_type=_qa.BDD_ARTIFACT_TYPE,   # "bdd_scenario"
        content_type=_qa.BDD_CONTENT_TYPE,     # "text/plain"
        title=_qa.BDD_TITLE,
    )
    await self._create_artifact(db, schema_name, project_id, run_id, agent_type, bdd_result, user_id)
    # Accumulate BDD tokens into step/run totals:
    step_tokens_total += bdd_result_llm.tokens_used
```

Import the `_qa` module alias at top of orchestrator (same pattern as `_ba`, `_automation`). The `complete` SSE event already carries `artifact_id` for the primary artifact — BDD artifact_id is not included in SSE (acceptable for MVP).

### ArtifactService SQL Pattern

Follow the exact pattern from `document_service.py`:

```python
schema_name = slug_to_schema_name(current_tenant_slug.get())  # in router

# list_artifacts():
rows = await db.execute(
    text(
        f'SELECT id, agent_type, artifact_type, title, current_version, metadata, '
        f'created_by, created_at, updated_at '
        f'FROM "{schema_name}".artifacts '
        f'WHERE project_id = :pid '
        + ('AND artifact_type = :at ' if artifact_type else '')
        + 'ORDER BY created_at DESC'
    ),
    {"pid": project_id} | ({"at": artifact_type} if artifact_type else {}),
)
```

### Coverage Matrix Content Rendering

BAConsultant output is a JSON array. Parse it in the frontend:

```tsx
// In ArtifactsTab, coverage_matrix tab:
const matrix = JSON.parse(artifact.content) as CoverageMatrixRow[]
// Render as <table> with columns: requirement_id, description, source, coverage_status, notes
```

Handle JSON parse errors with a fallback `<pre>` display.

### artifact_type Filter Query Param

Use FastAPI `Optional[str] = Query(None, alias="artifact_type")` to accept the filter. Pass directly to `artifact_service.list_artifacts()`.

### Project Structure Notes

- `ArtifactService` → `backend/src/services/artifact_service.py` (new, follows `document_service.py` pattern)
- `ArtifactsTab` → `web/src/pages/projects/artifacts/ArtifactsTab.tsx` (new directory `artifacts/`)
- Artifacts router → `backend/src/api/v1/artifacts/router.py` (new, same structure as `documents/router.py`)
- Agent module files: single-line constant changes only (Task 1)

### Learnings from Previous Story (2-9)

**From Story 2-9 (Status: done)**

- **`_create_artifact()` returns `str` (artifact_id):** Updated in Story 2-9 (Task 2.2). When adding BDD secondary artifact call, capture the return value if needed, or ignore it if SSE event for BDD artifact is not required. [Source: `backend/src/services/agents/orchestrator.py`]
- **Patch target rule (CRITICAL for tests):** Services with module-level `from src.cache import get_redis_client` must be patched at `src.services.{service_name}.get_redis_client`. This applies to `artifact_service.py` ONLY if it imports from `src.cache` (it does not for read-only CRUD — no Redis needed).
- **No toast library:** Use inline `useState` banner for success/error feedback in `ArtifactsTab`. Do not add `sonner` or `react-hot-toast`.
- **SSE `all_done` → navigate to Artifacts:** `AgentsTab.tsx` (AC-21) navigates to `/projects/{id}/artifacts` on pipeline completion. `ArtifactsTab` must be registered at this route.

[Source: docs/stories/epic-2/2-9-real-time-agent-progress-tracking.md#Dev-Agent-Record]

### References

- Tech spec AC-22–26: `docs/stories/epic-2/tech-spec-epic-2.md#8-acceptance-criteria`
- Agent files: `backend/src/services/agents/{ba,qa,automation}_consultant.py`
- Orchestrator: `backend/src/services/agents/orchestrator.py` (see `_run_agent_step`, `_create_artifact`)
- Migration 015 (artifacts schema): `backend/alembic/versions/015_create_agent_runs_and_artifacts.py`
- Pattern reference: `backend/src/services/document_service.py` (SQL + schema pattern)
- Agent runs router (RBAC pattern): `backend/src/api/v1/agent_runs/router.py`
- Frontend pattern: `web/src/pages/projects/agents/AgentsTab.tsx` (tab UI, useQuery, inline banners)

## Dev Agent Record

### Context Reference

- docs/stories/epic-2/2-10-test-artifact-storage-viewer.context.xml

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List
