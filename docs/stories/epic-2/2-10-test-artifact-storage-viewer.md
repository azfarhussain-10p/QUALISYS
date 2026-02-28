# Story 2.10: Test Artifact Storage & Viewer

Status: done

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

- Task 1: artifact_type constants updated in all 3 agent files (AC-22, AC-23, AC-24)
- Task 2: QAConsultant `run_bdd()` + `BDD_SYSTEM_PROMPT` added; orchestrator calls it after primary artifact (AC-25)
- Task 3: ArtifactService with `list_artifacts`, `get_artifact`, `list_versions`, `get_version` — follows document_service.py SQL pattern
- Task 4: artifacts API router with 4 GET endpoints, Pydantic schemas, registered in main.py
- Task 5: `artifactApi` namespace + TypeScript interfaces added to api.ts
- Task 6: ArtifactsTab (4-tab viewer with expand/collapse, coverage matrix table, empty states) + ArtifactsPage wrapper at `/projects/:projectId/artifacts` route
- Task 7: 13 tests (7 unit artifact_service + 2 orchestrator + 4 integration) — all passing
- Pre-existing orchestrator tests updated for new constants and BDD token accounting — 17/17 passing

### File List

**Modified:**
- `backend/src/services/agents/ba_consultant.py` — ARTIFACT_TYPE → `"coverage_matrix"`, CONTENT_TYPE → `"application/json"`
- `backend/src/services/agents/qa_consultant.py` — ARTIFACT_TYPE → `"manual_checklist"`, CONTENT_TYPE → `"text/markdown"`, added BDD constants + `run_bdd()` + `BDD_SYSTEM_PROMPT`
- `backend/src/services/agents/automation_consultant.py` — ARTIFACT_TYPE → `"playwright_script"`, CONTENT_TYPE → `"text/typescript"`
- `backend/src/services/agents/orchestrator.py` — Added BDD secondary artifact creation in `_run_agent_step()` for `qa_consultant`; combined token accounting
- `backend/src/main.py` — Registered `artifacts_router`
- `web/src/lib/api.ts` — Added `ArtifactSummary`, `ArtifactDetail`, `ArtifactVersionSummary` interfaces + `artifactApi` namespace
- `web/src/App.tsx` — Added `/projects/:projectId/artifacts` route
- `backend/tests/unit/services/test_orchestrator.py` — Updated 2 pre-existing tests for new constants + token accounting; added 2 new tests
- `docs/sprint-status.yaml` — `2-10` → `review`

**Created:**
- `backend/src/services/artifact_service.py` — ArtifactService (list, get, versions)
- `backend/src/api/v1/artifacts/__init__.py` — Package init
- `backend/src/api/v1/artifacts/schemas.py` — Pydantic response models
- `backend/src/api/v1/artifacts/router.py` — 4 GET endpoints with RBAC
- `web/src/pages/projects/artifacts/ArtifactsTab.tsx` — 4-tab artifact viewer (AC-26b/c/d)
- `web/src/pages/projects/artifacts/ArtifactsPage.tsx` — Standalone page wrapper for route
- `backend/tests/unit/services/test_artifact_service.py` — 7 unit tests
- `backend/tests/integration/test_artifacts.py` — 4 integration tests

## Senior Developer Review (AI)

### Reviewer
AI Senior Developer (Code Review Workflow)

### Date
2026-03-01

### Outcome
**CHANGES REQUESTED** — 1 MEDIUM finding requires a code change before approval. All acceptance criteria are structurally implemented and verified with evidence; the MEDIUM finding addresses a production data gap that the test mocks currently mask.

### Summary

Story 2-10 delivers a well-structured implementation of the Test Artifact Storage & Viewer. All 7 acceptance criteria are addressed across 17 modified/created files with 13 new tests and 2 updated tests. The backend follows established SQL/RBAC patterns, the frontend provides a clean tabbed UI with proper empty states and content rendering, and the BDD secondary artifact pattern is cleanly integrated into the orchestrator. One MEDIUM finding was identified: the `artifacts.metadata` JSONB column is never populated by the orchestrator's `_create_artifact()`, meaning `metadata.tokens_used` would always be `NULL` in production despite AC-26 requiring it in responses and the UI referencing it.

### Key Findings

#### HIGH Severity
None.

#### MEDIUM Severity

**M-1: `artifacts.metadata` column never populated — tokens_used NULL in production**
The orchestrator's `_create_artifact()` INSERT (`orchestrator.py:337-355`) does not include the `metadata` column despite the migration 015 defining it as `JSONB` (`015_create_agent_runs_and_artifacts.py:135`). The `artifact_service.py` SELECT includes `metadata` (line 29), the Pydantic `ArtifactSummary` exposes it (line 20), and the frontend `ArtifactCard` reads `artifact.metadata?.tokens_used` (line 193). In production, this field would always be `NULL`. The integration tests mask this because they mock rows with `"metadata": {"tokens_used": 100}`. Fix: add `metadata` to the `_create_artifact()` INSERT with `json.dumps({"tokens_used": result.tokens_used, "cost_usd": result.cost_usd})`.

#### LOW Severity

**L-1: Stale docstring in `ba_consultant.py`**
Line 6 still references `Artifact: requirements_matrix (JSON content_type)` but the constant was changed to `"coverage_matrix"`. Cosmetic but misleading for future developers.

**L-2: Stale docstring in `automation_consultant.py`**
Line 6 still references `Artifact: playwright_scripts (TypeScript content_type)` (plural) but the constant is now `"playwright_script"` (singular).

**L-3: No tests for version endpoints**
`test_artifacts.py` covers list, list-with-filter, detail, and 404 — but no tests for `GET /artifacts/{id}/versions` or `GET /artifacts/{id}/versions/{ver}`. These endpoints are implemented and have unit-level coverage in `test_artifact_service.py` but lack integration-level HTTP tests.

**L-4: BDD `run_bdd()` not covered by retry loop**
The primary `agent.run()` call benefits from the 3x retry with 5s/10s/20s backoff (`orchestrator.py:209-240`), but the `run_bdd()` call (`orchestrator.py:281`) is outside the retry block. If the BDD LLM call fails transiently, the entire step fails without retry. Acceptable for MVP (documented in dev notes as "two LLM calls, two artifact rows per QA step") but should be addressed for production resilience.

**L-5: ArtifactCard uses manual fetch state instead of React Query**
`ArtifactCard` manages detail loading via `useState` + manual `artifactApi.get()` (`ArtifactsTab.tsx:166-191`) instead of `useQuery`, missing React Query's caching, deduplication, and automatic refetch benefits. Functional but inconsistent with the pattern used for the artifact list.

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC-22 | BA Consultant stores `coverage_matrix` artifact | IMPLEMENTED | `ba_consultant.py:16-17` — `ARTIFACT_TYPE = "coverage_matrix"`, `CONTENT_TYPE = "application/json"` |
| AC-23 | QA Consultant stores `manual_checklist` artifact | IMPLEMENTED | `qa_consultant.py:17-18` — `ARTIFACT_TYPE = "manual_checklist"`, `CONTENT_TYPE = "text/markdown"` |
| AC-24 | Automation Consultant stores `playwright_script` artifact | IMPLEMENTED | `automation_consultant.py:16-17` — `ARTIFACT_TYPE = "playwright_script"`, `CONTENT_TYPE = "text/typescript"` |
| AC-25 | QA Consultant generates BDD scenario; orchestrator creates 2 artifacts | IMPLEMENTED | `qa_consultant.py:21-23,48-70,104-121` — BDD constants + prompt + `run_bdd()`; `orchestrator.py:280-294` — dual artifact creation with token accumulation |
| AC-26 | GET endpoints with RBAC + ArtifactService | IMPLEMENTED | `router.py:26-107` — 4 endpoints with `require_project_role`; `artifact_service.py:18-178` — 4 service methods; `main.py:153-154` — router registered |
| AC-26b | 4-tab viewer page | IMPLEMENTED | `ArtifactsTab.tsx:26-55` — tab definitions; `ArtifactsTab.tsx:280-299` — tab UI; `ArtifactsTab.tsx:196-249` — ArtifactCard; `App.tsx:67` — route `/projects/:projectId/artifacts` |
| AC-26c | Empty states per tab | IMPLEMENTED | `ArtifactsTab.tsx:31-53` — unique `emptyMessage` per tab; `ArtifactsTab.tsx:318-329` — empty state UI with icon |
| AC-26d | Content format: JSON→table, others→pre | IMPLEMENTED | `ArtifactsTab.tsx:71-126` — `CoverageMatrixTable` (JSON parse + HTML table with status badges); `ArtifactsTab.tsx:241-244` — `<pre className="font-mono">` for others |

**Summary: 8 of 8 acceptance criteria fully implemented** (M-1 is a data-population gap, not a missing AC implementation)

### Task Completion Validation

| Task | Marked As | Verified As | Evidence |
|------|-----------|-------------|---------|
| 1.1 BA constant change | Unmarked | VERIFIED COMPLETE | `ba_consultant.py:16-17` |
| 1.2 QA constant change | Unmarked | VERIFIED COMPLETE | `qa_consultant.py:17-18` |
| 1.3 Automation constant change | Unmarked | VERIFIED COMPLETE | `automation_consultant.py:16-17` |
| 2.1 BDD constants | Unmarked | VERIFIED COMPLETE | `qa_consultant.py:21-23` |
| 2.2 BDD prompt + run_bdd() | Unmarked | VERIFIED COMPLETE | `qa_consultant.py:48-70,104-121` |
| 2.3 Orchestrator BDD integration | Unmarked | VERIFIED COMPLETE | `orchestrator.py:280-294` |
| 2.4 BDD artifact constants used | Unmarked | VERIFIED COMPLETE | `orchestrator.py:286-289` — uses `_qa.BDD_ARTIFACT_TYPE`, `_qa.BDD_CONTENT_TYPE`, `_qa.BDD_TITLE` |
| 3.1 ArtifactService | Unmarked | VERIFIED COMPLETE | `artifact_service.py:18-178` — 4 methods, singleton instantiated |
| 4.1 artifacts __init__.py | Unmarked | VERIFIED COMPLETE | `backend/src/api/v1/artifacts/__init__.py` exists |
| 4.2 Pydantic schemas | Unmarked | VERIFIED COMPLETE | `schemas.py:12-39` — 3 models |
| 4.3 Router endpoints | Unmarked | VERIFIED COMPLETE | `router.py:26-107` — 4 GET endpoints |
| 4.4 main.py registration | Unmarked | VERIFIED COMPLETE | `main.py:153-154` |
| 5.1 TypeScript interfaces | Unmarked | VERIFIED COMPLETE | `api.ts:998-1020` |
| 5.2 artifactApi namespace | Unmarked | VERIFIED COMPLETE | `api.ts:1022-1047` |
| 6.1 ArtifactsTab component | Unmarked | VERIFIED COMPLETE | `ArtifactsTab.tsx:1-346` |
| 6.2 Route registration | Unmarked | VERIFIED COMPLETE | `ArtifactsPage.tsx` + `App.tsx:67` |
| 7.1 Unit tests for ArtifactService | Unmarked | VERIFIED COMPLETE | `test_artifact_service.py` — 7 tests |
| 7.2 Orchestrator BDD test | Unmarked | VERIFIED COMPLETE | `test_orchestrator.py:640-694` |
| 7.3 Constants test | Unmarked | VERIFIED COMPLETE | `test_orchestrator.py:620-636` |
| 7.4 Integration tests | Unmarked | VERIFIED COMPLETE | `test_artifacts.py` — 4 tests |
| 7.5 Sprint status update | Unmarked | VERIFIED COMPLETE | `sprint-status.yaml:152` — set to `review` (note: task text incorrectly says `drafted`; `review` is correct post-implementation) |

**Summary: 21 of 21 tasks verified complete, 0 questionable, 0 falsely marked**

### Test Coverage and Gaps

**Tests present:**
- 7 unit tests for ArtifactService (list, filter, detail, 404, versions, version 404)
- 2 orchestrator tests (constants validation, BDD dual-artifact pattern)
- 4 integration tests (empty list, filtered list, detail with content, 404)
- 2 pre-existing orchestrator tests updated (constant values, token totals)
- Total: 13 new + 2 updated = 15 test touch points

**Gaps:**
- No integration tests for version endpoints (L-3)
- Integration tests only exercise `owner` role — no coverage of `admin` or `qa-automation` roles
- Integration test for `metadata.tokens_used` uses mocked data, masking the production NULL (M-1)

### Architectural Alignment

- SQL pattern: Follows `document_service.py` exactly (`text()` + `:params`, f-string for schema name only) ✅
- RBAC pattern: Follows `agent_runs/router.py` (`require_project_role`) ✅
- Multi-tenancy: Uses `current_tenant_slug` ContextVar + `slug_to_schema_name` ✅
- Frontend pattern: Uses React Query, Axios client, tab UI consistent with existing pages ✅
- BDD secondary artifact: Follows the dev notes pattern — clean integration without modifying orchestrator signature ✅

### Security Notes

- **RBAC**: All 4 endpoints enforce `require_project_role("owner", "admin", "qa-automation")` ✅
- **SQL injection**: All queries use `text()` with named `:params`. Schema name only in f-string (validated upstream). ✅
- **IDOR protection**: `list_artifacts` filters by `project_id`. `get_artifact` checks both `aid` AND `pid`. `list_versions` does ownership check before returning versions. `get_version` joins with project_id filter. ✅
- **No secrets exposed**: No tokens, keys, or credentials in code or responses. ✅

### Best-Practices and References

- [FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/) — `artifact_type` filter uses `Query(None)` correctly
- [React Query](https://tanstack.com/query/latest/docs/react/overview) — list fetch uses `useQuery` with proper `queryKey` array for cache invalidation on tab switch
- [Pydantic V2 model inheritance](https://docs.pydantic.dev/latest/concepts/models/#model-inheritance) — `ArtifactDetail(ArtifactSummary)` extends cleanly

### Action Items

**Code Changes Required:**
- [x] [Med] Populate `artifacts.metadata` JSONB column in `_create_artifact()` with `{"tokens_used": result.tokens_used, "cost_usd": result.cost_usd}` so `metadata.tokens_used` is available in production responses [file: `backend/src/services/agents/orchestrator.py:337-359`] — **FIXED**: added `metadata` to INSERT with `json.dumps()`

**Advisory Notes (all resolved):**
- [x] L-1: Updated stale docstring in `ba_consultant.py:6` — `requirements_matrix` → `coverage_matrix`
- [x] L-2: Updated stale docstring in `automation_consultant.py:6` — `playwright_scripts` → `playwright_script`
- [x] L-3: Added 3 integration tests for version endpoints (`test_list_versions_returns_ordered`, `test_get_specific_version_returns_content`, `test_get_version_404_unknown`) — 7/7 integration tests passing
- [x] L-4: Wrapped BDD `run_bdd()` in same 3x retry loop with 5s/10s/20s backoff in `orchestrator.py` — `BudgetExceededError` still non-retryable
- [x] L-5: Migrated `ArtifactCard` detail fetch from manual `useState` to `useQuery` with `enabled: expanded` and 5-min `staleTime` for caching
- Note: Add integration test coverage for `admin` and `qa-automation` roles (deferred — not a code defect)

## Senior Developer Review — Pass 2 (AI)

### Reviewer
AI Senior Developer (Code Review Workflow)

### Date
2026-03-01

### Outcome
**APPROVE** — All 6 Pass 1 findings verified resolved. No new issues introduced. 31/31 tests passing.

### Pass 1 Finding Verification

| Finding | Status | Verification Evidence |
|---------|--------|-----------------------|
| M-1: `artifacts.metadata` never populated | **RESOLVED** | `orchestrator.py:364-367` — `json.dumps({"tokens_used": result.tokens_used, "cost_usd": result.cost_usd})` added. INSERT now includes `metadata` column (line 373) and `:metadata` param (line 384). Production artifacts will have `metadata.tokens_used` and `metadata.cost_usd`. |
| L-1: Stale docstring in `ba_consultant.py` | **RESOLVED** | `ba_consultant.py:6` — now reads `Artifact: coverage_matrix (application/json content_type).` |
| L-2: Stale docstring in `automation_consultant.py` | **RESOLVED** | `automation_consultant.py:6` — now reads `Artifact: playwright_script (text/typescript content_type).` |
| L-3: No integration tests for version endpoints | **RESOLVED** | `test_artifacts.py:280-379` — 3 new tests added: `test_list_versions_returns_ordered` (asserts version ordering), `test_get_specific_version_returns_content` (asserts content + content_type), `test_get_version_404_unknown` (asserts VERSION_NOT_FOUND). Integration test count: 4 → 7. |
| L-4: BDD `run_bdd()` not in retry loop | **RESOLVED** | `orchestrator.py:281-307` — Full 3x retry loop with 5s/10s/20s backoff wrapping `agent.run_bdd()`. `BudgetExceededError` immediately re-raised (non-retryable). On exhaustion, raises `RuntimeError` with descriptive message. Matches primary `agent.run()` retry pattern exactly. |
| L-5: ArtifactCard manual fetch state | **RESOLVED** | `ArtifactsTab.tsx:168-177` — Replaced `useState`/manual fetch with `useQuery({ queryKey: ['artifact-detail', projectId, artifact.id], enabled: expanded, staleTime: 5 * 60 * 1000 })`. Toggle handler simplified to `setExpanded((prev) => !prev)`. Consistent with list-level `useQuery` pattern. |

### New Code Quality Check

No new issues introduced by the fixes:
- M-1 fix: `json.dumps` serialization is correct for JSONB column insertion via SQLAlchemy `text()` with `:params`. The metadata dict structure matches what the frontend reads (`artifact.metadata?.tokens_used`).
- L-4 fix: BDD retry loop correctly scopes `bdd_last_error` and `bdd_result_llm` variables within the `if agent_type == "qa_consultant"` block. No variable shadowing with the outer retry loop.
- L-5 fix: `useQuery` with `enabled: expanded` correctly defers the fetch until the card is expanded. The `staleTime` prevents re-fetches within 5 minutes for already-loaded cards. The `isError` boolean from `useQuery` replaces the previous `loadError` string state cleanly.

### Test Results

- **17/17** orchestrator unit tests passing (includes `test_qa_consultant_creates_two_artifacts` verifying BDD path with retry)
- **7/7** artifact service unit tests passing
- **7/7** artifact integration tests passing (includes 3 new version endpoint tests)
- **Total: 31/31 tests passing**

## Change Log

| Date | Change | By |
|------|--------|----|
| 2026-03-01 | Story created | SM Agent |
| 2026-03-01 | Implementation complete — all 7 tasks, 13 new tests | DEV Agent |
| 2026-03-01 | Senior Developer Review Pass 1 — CHANGES REQUESTED (1 MEDIUM, 5 LOW) | AI Code Review |
| 2026-03-01 | All review findings resolved (M-1 + L-1 through L-5). 31/31 tests passing (17 orchestrator + 7 artifact unit + 7 integration). Re-submitted for review. | DEV Agent |
| 2026-03-01 | Senior Developer Review Pass 2 — APPROVED. All 6 findings verified resolved, 0 new issues. | AI Code Review |
