# Story 2.7: Agent Pipeline Orchestration

Status: done

## Story

As a QA-Automation user,
I want my selected AI agents to actually execute after I click "Run Selected Agents",
so that the pipeline runs automatically in the background and produces test artifacts for my project.

## Requirements Context

Story 2-7 implements the background execution engine behind the queued `agent_runs` row created
by Story 2-6. When `POST /agent-runs` creates a `queued` run, this story adds the
`FastAPI BackgroundTask` dispatch and the `AgentOrchestrator` service that drives the full
sequential pipeline: context assembly → BA Consultant → QA Consultant → Automation Consultant →
artifact creation.

**FRs Covered:**
- FR28 — Sequential agent pipeline: agents execute one-at-a-time in selection order
- FR29 — LLM token usage tracked per agent step; aggregated total on the run row
- FR31 — Pipeline error recovery: LLM failure retried 3× (5s/10s/20s backoff); step + run marked
  `failed` after max retries; remaining steps skipped

**Architecture Constraints:**
- `FastAPI BackgroundTasks` (consistent with Stories 2-1 through 2-5; arq deferred post-MVP)
- New package: `backend/src/services/agents/` with `orchestrator.py` + 3 agent modules
- LLM calls via `from src.patterns.llm_pattern import call_llm, LLMResult` (C2 pattern, validated)
- Context assembly: `text()` SQL with `:params` — schema name only in f-string (validated upstream)
- Artifacts INSERTed into `artifacts` + `artifact_versions` tables (created by Migration 015)
- `artifact_type` values: `requirements_matrix` (BA), `test_checklists` (QA),
  `playwright_scripts` (Automation)
- `content_type` values: `json` (BA), `markdown` (QA), `typescript` (Automation)
- RBAC: existing `require_project_role("owner", "admin", "qa-automation")` on POST /agent-runs
- No new Alembic migration required (all tables exist from Migration 015)
- Token budget hard-limit (HTTP 429) and explicit cache validation deferred to Story 2-8
- SSE real-time progress events deferred to Story 2-9
- Artifact viewer frontend deferred to Story 2-10

**Out of Scope:**
- Token budget hard-limit enforcement / HTTP 429 BUDGET_EXCEEDED (Story 2-8)
- Redis LLM cache TTL management and AC-18 formal validation (Story 2-8)
- SSE stream `/api/v1/events/agent-runs/{run_id}` (Story 2-9)
- Progress UI updates (Story 2-9)
- Artifact viewer and Monaco editor (Story 2-10)
- Artifact editing / versioning (Story 2-11)
- Cancel run endpoint (Story 2-7+ TBD)

## Acceptance Criteria

**AC-17a (Backend — data source validation):** `POST /api/v1/projects/{project_id}/agent-runs`
checks that the project has at least one ready data source (document with `parse_status='completed'`,
GitHub connection with `status='cloned'`, or crawl session with `status='completed'`).
Returns `400 NO_DATA_SOURCES` with message if none found. Check runs before queuing the run.

**AC-17b (Backend — pipeline kick-off):** After inserting the `agent_runs` + `agent_run_steps`
rows (unchanged from Story 2-6), the router dispatches `orchestrator.execute_pipeline` as a
`BackgroundTask`. The HTTP response `201` is returned immediately; background execution begins
asynchronously.

**AC-17c (Backend — run status lifecycle):** `execute_pipeline` transitions `agent_runs`:
- `status='running'`, `started_at=now` at pipeline start
- `status='completed'`, `completed_at=now`, `total_tokens` and `total_cost_usd` summed on success
- `status='failed'`, `error_message` set, `completed_at=now` on unrecoverable step failure

**AC-17d (Backend — step status lifecycle):** For each agent step in `agents_selected` order:
`agent_run_steps.status`: `queued → running` (step start, `started_at=now`) →
`completed` (`tokens_used=N`, `progress_pct=100`, `completed_at=now`) or `failed` (`error_message`).

**AC-17e (Backend — context assembly):** Before running agents, `_assemble_context()` loads:
- Document text: concatenated `content` from `document_chunks` for project's completed documents
  (truncated at 40,000 tokens)
- GitHub summary: `analysis_summary` from the most-recent `status='cloned'` GitHub connection
- Crawl data: `crawl_data` (JSON) from the most-recent `status='completed'` crawl session
Missing sources (no rows found) are omitted gracefully — empty string / None.

**AC-17f (Backend — LLM execution):** Each agent builds an agent-specific system prompt
embedding the assembled context and calls `call_llm(prompt, tenant_id, daily_budget=None,
agent_type=agent_type)`. Returns `LLMResult(content, tokens_used, cost_usd, cached, provider)`.

**AC-17g (Backend — artifact creation):** Each agent's LLM output stored as:
- `artifacts` row: `project_id`, `run_id`, `agent_type`, `artifact_type`, `title`,
  `current_version=1`, `created_by` (run's `created_by` user)
- `artifact_versions` row: `artifact_id`, `version=1`, `content` (LLM text output),
  `content_type` (json/markdown/typescript), `diff_from_prev=null`

**AC-17h (Backend — token tracking):** `agent_run_steps.tokens_used` = `LLMResult.tokens_used`
per step. On pipeline completion: `agent_runs.total_tokens` = SUM of all completed steps'
`tokens_used`; `agent_runs.total_cost_usd` = SUM of all steps' `LLMResult.cost_usd`.

**AC-17i (Backend — error handling):** LLM call failure raises exception → retry up to 3×
with 5s → 10s → 20s backoff (`asyncio.sleep`). After 3 failures: step marked `failed` with
`error_message`; all remaining steps stay `queued` (not executed); run marked `failed`.
Artifacts created before failure are retained. Partial runs are visible in `GET /agent-runs/{id}`.

## Tasks

### Task 1: Modify POST /agent-runs router to dispatch background task

- [x] 1.1 Add `background_tasks: BackgroundTasks` parameter to `start_run_endpoint` in
  `backend/src/api/v1/agent_runs/router.py`
- [x] 1.2 Add data source validation helper `_check_has_data_sources(db, schema_name, project_id)`
  — queries document_chunks/documents, github_connections, crawl_sessions for at least one ready
  source; raises `HTTPException(400, {"error": "NO_DATA_SOURCES", "message": ...})`
- [x] 1.3 After `agent_run_service.create_run(...)` returns, dispatch:
  `background_tasks.add_task(orchestrator.execute_pipeline, run["id"], schema_name,
  str(project_id), tenant_id, str(user.id))`
- [x] 1.4 Fix LOW findings from 2-6 review while touching router/service:
  - Move `import json` to module level in `agent_run_service.py`
  - Change `agents_selected: Any` → `agents_selected: list[str]` in `AgentRunResponse`

### Task 2: Create agent implementations

- [x] 2.1 Create `backend/src/services/agents/__init__.py` (empty)
- [x] 2.2 Create `backend/src/services/agents/ba_consultant.py`
  - `class BAConsultantAgent`
  - `SYSTEM_PROMPT` — instructs LLM to produce a requirements coverage matrix (JSON)
  - `ARTIFACT_TYPE = "requirements_matrix"`, `CONTENT_TYPE = "json"`, `TITLE = "Requirements Coverage Matrix"`
  - `async def run(context: dict, tenant_id: str) -> AgentResult`
    - Builds prompt: system_prompt + doc_text + github_summary + crawl_data sections
    - Calls `call_llm(prompt, tenant_id, daily_budget=100_000, agent_type="ba_consultant")`
    - Returns `AgentResult`
- [x] 2.3 Create `backend/src/services/agents/qa_consultant.py`
  - `class QAConsultantAgent`
  - `ARTIFACT_TYPE = "test_checklists"`, `CONTENT_TYPE = "markdown"`, `TITLE = "Manual Test Checklists"`
  - Same pattern as BA; system prompt targets manual checklists + BDD/Gherkin scenarios
- [x] 2.4 Create `backend/src/services/agents/automation_consultant.py`
  - `class AutomationConsultantAgent`
  - `ARTIFACT_TYPE = "playwright_scripts"`, `CONTENT_TYPE = "typescript"`, `TITLE = "Playwright Test Scripts"`
  - Same pattern; system prompt targets syntactically valid Playwright TypeScript scripts

### Task 3: Create AgentOrchestrator

- [x] 3.1 Create `backend/src/services/agents/orchestrator.py`
  - `AgentResult = namedtuple("AgentResult", ["content", "tokens_used", "cost_usd", "artifact_type", "content_type", "title"])`
  - `AGENT_MAP: dict[str, type]` — maps agent_type string → agent class
  - `async def execute_pipeline(run_id, schema_name, project_id, tenant_id, user_id)`
    - Acquires new `AsyncSession` (separate from request lifecycle)
    - Transitions run: `running`/`started_at`
    - Loads `agents_selected` from `agent_runs` row
    - Calls `_assemble_context(db, schema_name, project_id)`
    - Iterates `agents_selected` in order; for each: calls `_run_agent_step(...)`
    - On success: sums tokens/cost, transitions run: `completed`/`total_tokens`/`completed_at`
    - On step failure: transitions run: `failed`/`error_message`/`completed_at`; breaks loop
  - `async def _assemble_context(db, schema_name, project_id) → dict`
    - Loads document chunk text (LIMIT 500 chunks, concatenated)
    - Loads most-recent GitHub analysis_summary
    - Loads most-recent crawl_data
    - Returns `{"doc_text": str, "github_summary": str, "crawl_data": str}`
  - `async def _run_agent_step(db, schema_name, step_id, agent_type, context, tenant_id, user_id, project_id, run_id) → AgentResult`
    - Transitions step: `running`
    - Instantiates agent from `AGENT_MAP[agent_type]`
    - Calls `agent.run(context, tenant_id)` with retry (3× / 5s-10s-20s backoff)
    - On success: transitions step: `completed`/`tokens_used`/`progress_pct=100`/`completed_at`
    - Calls `_create_artifact(...)`
    - On failure (all retries exhausted): transitions step: `failed`/`error_message`; re-raises
  - `async def _create_artifact(db, schema_name, project_id, run_id, agent_type, result, user_id)`
    - INSERTs `artifacts` row; INSERTs `artifact_versions` row (version=1)
  - `async def _update_run(db, schema_name, run_id, **fields)` — UPDATE agent_runs WHERE id=:id
  - `async def _update_step(db, schema_name, step_id, **fields)` — UPDATE agent_run_steps WHERE id=:id
  - `orchestrator = AgentOrchestrator()` module-level singleton

### Task 4: Tests

- [x] 4.1 Create `backend/tests/unit/services/test_orchestrator.py` — 14 unit tests
  - `test_assemble_context_returns_doc_text` — doc chunks loaded as concatenated text
  - `test_assemble_context_handles_no_sources` — empty context when no rows
  - `test_run_agent_step_marks_running_then_completed` — step status transitions verified
  - `test_run_agent_step_creates_artifact_and_version` — artifact + artifact_version INSERTs called
  - `test_run_agent_step_marks_failed_with_timestamp` — AC-17d: step UPDATE on failure includes status, error_message, completed_at
  - `test_execute_pipeline_run_failed_includes_completed_at` — AC-17c: run UPDATE on failure includes status, error_message, completed_at
  - `test_execute_pipeline_completes_all_steps` — all agents run, run status = completed
  - `test_execute_pipeline_sums_tokens_on_completion` — total_tokens = sum of step tokens
  - `test_execute_pipeline_retries_llm_on_failure` — LLM error triggers retry calls
  - `test_execute_pipeline_marks_failed_after_max_retries` — 3 LLM failures → failed step + failed run
  - `test_execute_pipeline_skips_remaining_steps_on_failure` — unexecuted steps stay queued
  - `test_execute_pipeline_budget_exceeded_non_retryable` — BudgetExceededError → 1 call, run failed
  - `test_execute_pipeline_artifacts_retained_on_failure` — successful step artifacts committed before failure
- [x] 4.2 Create `backend/tests/integration/test_agent_pipeline.py` — 4 integration tests
  - `test_start_run_no_data_sources_400` — POST /agent-runs → 400 NO_DATA_SOURCES
  - `test_start_run_201_with_data_source` — POST /agent-runs → 201 (data source present)
  - `test_start_run_dispatches_background_task` — POST /agent-runs dispatches execute_pipeline
  - `test_start_run_empty_agents_400` — regression: 400 NO_AGENTS_SELECTED still works

## DoD

- [x] A1: All ACs (17a–17i) implemented and verified against tech-spec §5.3
- [x] A2: All tasks checked off
- [x] A3: All tests pass (unit + integration) — 18/18 passing (14 unit + 4 integration)
- [x] A4: No regressions in prior Epic 2 test suite — 121/121 story tests passing
- [x] A5: sprint-status.yaml updated to `review`
- [x] A6: Every test has a one-line comment stating the behaviour proved

## Story Source References

- Pipeline flow: [Source: docs/stories/epic-2/tech-spec-epic-2.md#5-workflows-sequencing, §5.3 Agent Pipeline]
- FR28/29/31: [Source: docs/stories/epic-2/tech-spec-epic-2.md#2-objectives-scope]
- Artifact schema: [Source: backend/alembic/versions/015_create_agent_runs_and_artifacts.py]
- LLM pattern: [Source: backend/src/patterns/llm_pattern.py]
- Context assembly SQL pattern: [Source: backend/src/services/embedding_service.py]
- Background task pattern: [Source: backend/src/services/document_service.py]
- AgentRunService (reuse): [Source: backend/src/services/agent_run_service.py]
- Router pattern (reuse/modify): [Source: backend/src/api/v1/agent_runs/router.py]
- Agent class pattern: [Source: backend/src/services/dom_crawler_service.py]
- Story 2-6 learnings: [Source: docs/stories/epic-2/2-6-ai-agent-selection-ui.md#Dev-Agent-Record]

## Dev Notes

### Architecture Notes

- `execute_pipeline` must open its OWN `AsyncSession` (not the request session, which closes after
  HTTP response). Pattern: `async with get_async_session() as db:` inside the background function.
  Follow the same approach as `parse_document_task` in `document_service.py`.
- `asyncio.sleep` for retry backoff — no blocking calls in async context.
- Truncate assembled doc_text at 40,000 tokens (use `tiktoken.get_encoding("cl100k_base")`) to
  stay within LLM context limits. Warn in logs if truncated.
- `call_llm()` from `llm_pattern.py` already performs Redis cache check + basic budget gate. Story
  2-8 adds the formal HTTP 429 response surface and monitoring. For now, `BudgetExceededError`
  from `llm_pattern.py` should be caught in `_run_agent_step` and treated as a non-retryable
  failure (mark step + run `failed` with appropriate error_message).
- All SQL uses `text()` with `:params`; schema name is f-string interpolated (validated by
  `slug_to_schema_name()` upstream). Pattern consistent with all prior Epic 2 services.
- Agent system prompts should be concise (< 500 tokens) and instruct the LLM to respond with
  valid JSON (BA), Markdown (QA), or TypeScript (Automation). No specific output schema validation
  in this story — Story 2-8 adds schema enforcement.

### Data Source Validation Pattern

```python
# In router.py: check at least one ready data source exists
async def _check_has_data_sources(db, schema_name: str, project_id: str) -> bool:
    result = await db.execute(
        text(
            f'SELECT 1 FROM "{schema_name}".documents '
            f"WHERE project_id = :pid AND parse_status = 'completed' LIMIT 1"
        ),
        {"pid": project_id},
    )
    if result.scalar_one_or_none():
        return True
    # also check github_connections (status='cloned') and crawl_sessions (status='completed')
    ...
```

### Session Handling in Background Tasks

```python
# orchestrator.py — acquire new DB session in background context
from src.db import async_session_factory  # SessionLocal or equivalent

async def execute_pipeline(run_id, schema_name, project_id, tenant_id, user_id):
    async with async_session_factory() as db:
        try:
            ...
        except Exception as e:
            await _update_run(db, schema_name, run_id, status="failed", error_message=str(e), ...)
            await db.commit()
```

### Learnings from Previous Story (2-6)

**From Story 2-6-ai-agent-selection-ui (Status: done)**

- **Reuse**: `agent_run_service.agent_run_service` singleton — `create_run()`, `get_run()`,
  `list_runs()` fully implemented. Do NOT recreate.
- **Reuse**: `AGENT_DEFINITIONS` + `VALID_AGENT_TYPES` in `agent_run_service.py` — agent catalog.
- **Modify**: `backend/src/api/v1/agent_runs/router.py` — add `BackgroundTasks` param to
  `start_run_endpoint`; add `_check_has_data_sources` guard before `create_run`.
- **Fix in passing** (LOW findings from 2-6 review):
  - `agent_run_service.py:115` — `import json` inside method body → move to module level
  - `router.py:74` — `agents_selected: Any` → `list[str]` in `AgentRunResponse`
- **Tables exist**: `agent_runs`, `agent_run_steps`, `artifacts`, `artifact_versions` — from
  Migration 015 (015_create_agent_runs_and_artifacts.py)
- **artifact_versions schema**: `(id, artifact_id, version INT, content TEXT, content_type VARCHAR,
  diff_from_prev TEXT, edited_by UUID, created_at)` — note field is `version`, not `version_number`

[Source: docs/stories/epic-2/2-6-ai-agent-selection-ui.md#Dev-Agent-Record]

### Project Structure Notes

- New package path: `backend/src/services/agents/` — consistent with tech-spec table (§4.1)
- Agent module naming: `ba_consultant.py`, `qa_consultant.py`, `automation_consultant.py`
- Orchestrator: `backend/src/services/agents/orchestrator.py` — referenced in tech-spec §3 component table
- Test paths: `backend/tests/unit/services/test_orchestrator.py`,
  `backend/tests/integration/test_agent_pipeline.py`

### Testing Notes

- All tests use mock DB + mock Redis (same pattern as prior Epic 2 integration tests)
- Mock `call_llm` from `src.patterns.llm_pattern` — do not make real LLM calls
- For background task integration tests: use `unittest.mock.patch` on `background_tasks.add_task`
  to capture and inspect dispatched function/args; or capture via `AsyncMock` side_effect
- For orchestrator unit tests: mock `async_session_factory` context manager; mock `call_llm`
  to return `LLMResult(content='{}', tokens_used=100, cost_usd=0.001, cached=False, provider='openai')`
- Retry tests: use `side_effect=[Exception("LLM error"), Exception("LLM error"), Exception("LLM error")]`
  on patched `call_llm` to trigger 3-failure path

## Dev Agent Record

### Context Reference

- `docs/stories/epic-2/2-7-agent-pipeline-orchestration.context.xml` — tech-spec §5.3, Migration 015 schema, LLM pattern interfaces, session management pattern

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Fixed `doc_rows or [default]` → `doc_rows if doc_rows is not None else [default]` in test helper (empty list falsy in Python)
- `tiktoken` moved to module-level import in orchestrator.py (deferred import not patchable in tests)
- `execute_pipeline` is a module-level coroutine (not class method) — imported directly in router; `background_tasks.add_task(execute_pipeline, ...)` pattern

### Completion Notes List

All ACs (17a–17i) implemented. 18 new tests (14 unit + 4 integration), all passing.
- AC-17a: `_check_has_data_sources()` in router.py — checks documents/github_connections/crawl_sessions; 400 NO_DATA_SOURCES on miss
- AC-17b: `background_tasks.add_task(execute_pipeline, ...)` dispatched after create_run(); 201 immediate
- AC-17c/d: run and step lifecycle transitions implemented in execute_pipeline + _run_agent_step
- AC-17e: `_assemble_context()` loads doc chunks (LIMIT 500, 40k token truncation), github analysis_summary, crawl_data
- AC-17f: Each agent calls `call_llm(daily_budget=100_000)` per constraint C10 (not None)
- AC-17g: `_create_artifact()` INSERTs artifacts + artifact_versions (version=1, not version_number)
- AC-17h: `total_tokens` + `total_cost_usd` summed on pipeline completion
- AC-17i: 3× retry (5s/10s/20s asyncio.sleep); BudgetExceededError non-retryable; artifacts retained on partial failure
- F-1/F-3 from 2-6 review: `import json` moved to module level; `agents_selected: list[str]` fixed

### File List

- `backend/src/api/v1/agent_runs/router.py` — MODIFIED (BackgroundTasks, _check_has_data_sources, execute_pipeline dispatch, agents_selected: list[str])
- `backend/src/services/agent_run_service.py` — MODIFIED (import json moved to module level)
- `backend/src/services/agents/__init__.py` — NEW
- `backend/src/services/agents/ba_consultant.py` — NEW (BAConsultantAgent, requirements_matrix/json)
- `backend/src/services/agents/qa_consultant.py` — NEW (QAConsultantAgent, test_checklists/markdown)
- `backend/src/services/agents/automation_consultant.py` — NEW (AutomationConsultantAgent, playwright_scripts/typescript)
- `backend/src/services/agents/orchestrator.py` — NEW (AgentOrchestrator, execute_pipeline, _assemble_context, _run_agent_step, _create_artifact, _update_run, _update_step)
- `backend/tests/unit/services/test_orchestrator.py` — NEW (14 unit tests)
- `backend/tests/integration/test_agent_pipeline.py` — NEW (4 integration tests)
- `docs/stories/epic-2/2-7-agent-pipeline-orchestration.md` — MODIFIED (tasks, DoD, Dev Agent Record)
- `docs/sprint-status.yaml` — MODIFIED (in-progress → review)

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-28 | Story drafted from tech-spec §5.3 pipeline flow, Migration 015 schema, and Story 2-6 learnings | Bob (SM Agent) |
| 2026-02-28 | Implementation complete: AgentOrchestrator, 3 agent modules, router modifications, 17 tests passing | Amelia (DEV Agent) |
| 2026-02-28 | Senior Developer Review notes appended — CHANGES REQUESTED (1 MEDIUM: BudgetExceededError step lifecycle) | Amelia (DEV Agent) |
| 2026-02-28 | Fixed [M1]: _run_agent_step marks step failed before re-raising BudgetExceededError; added test_execute_pipeline_budget_exceeded_marks_step_failed; fixed error message "attempts" → "retries"; re-submitted to review | Amelia (DEV Agent) |
| 2026-02-28 | Code review Pass 2 APPROVED. 9/9 ACs verified, 18/18 tests verified. 0 HIGH/MEDIUM findings, all LOW fixes confirmed. Status: review → done | Amelia (DEV Agent) |

---

## Senior Developer Review (AI)

**Reviewer:** Azfar
**Date:** 2026-02-28
**Outcome:** CHANGES REQUESTED

### Summary

Story 2-7 is a clean, well-structured implementation. The orchestration pipeline, context assembly, retry logic, artifact creation, and token tracking are all correctly implemented. The primary issue is a step lifecycle gap when `BudgetExceededError` propagates through `_run_agent_step` — the step is never transitioned from `running` to `failed`, contradicting both AC-17d and the story's own Dev Notes. The remaining findings are documentation inconsistencies (test count in File List/Changelog) and a misleading `_MAX_RETRIES` error message string.

---

### Key Findings

#### MEDIUM Severity

**[M1] BudgetExceededError leaves `agent_run_steps.status` stuck in `"running"`**

- **File:** `backend/src/services/agents/orchestrator.py:199–202`
- **Root cause:** In `_run_agent_step`, the retry loop catches `BudgetExceededError` and re-raises immediately before reaching the `if last_error is not None` block that calls `_update_step(status="failed")`. The step remains `running`.
- **Impact:** AC-17d says steps must transition to `failed` on failure. Dev Notes explicitly state: *"BudgetExceededError should be caught in `_run_agent_step` and treated as a non-retryable failure (mark step + run `failed`)"*. Only the run is marked `failed`; the step is not.
- **Also missing:** Test `test_execute_pipeline_budget_exceeded_non_retryable` does not assert the step is marked `failed` — gap not caught by tests.

#### LOW Severity

**[L1]** File List entry says `"(11 unit tests)"` — corrected to 13 inline.
**[L2]** Changelog said `"15 tests passing"` — corrected to 17 inline.
**[L3]** `_MAX_RETRIES` error message: `"failed after {_MAX_RETRIES} attempts"` prints `"...after 3 attempts"` but loop runs 4 iterations (1 initial + 3 retries with 5/10/20s delays). Should say `"after {_MAX_RETRIES} retries"` or `"after {_MAX_RETRIES + 1} attempts"`.
**[L4]** AC-17f text in story + context.xml says `daily_budget=None` but constraint C10 forbids `None`. Implementation correctly uses `100_000`. AC text is misleading; implementation is correct.

---

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|---------|
| AC-17a | Data source validation → 400 NO_DATA_SOURCES | **IMPLEMENTED** | `router.py:93–147`; `test_start_run_no_data_sources_400` |
| AC-17b | BackgroundTask dispatch; 201 immediate | **IMPLEMENTED** | `router.py:195–202`; 2 integration tests |
| AC-17c | Run: queued→running→completed/failed with timestamps | **IMPLEMENTED** | `orchestrator.py:367–492`; `test_execute_pipeline_run_failed_includes_completed_at` |
| AC-17d | Step: queued→running→completed/failed with timestamps | **PARTIAL** | Normal + exhausted-retry paths ✓; BudgetExceededError leaves step in `running` ✗ [M1] |
| AC-17e | Context assembly: doc chunks, github summary, crawl data | **IMPLEMENTED** | `orchestrator.py:74–161`; tiktoken truncation; graceful empty strings; 2 unit tests |
| AC-17f | LLM via call_llm(daily_budget=100_000) | **IMPLEMENTED** | All 3 agents use `_DAILY_BUDGET=100_000` per constraint C10 |
| AC-17g | Artifact + artifact_version INSERT (version=1) | **IMPLEMENTED** | `orchestrator.py:254–302`; `version` not `version_number` ✓; unit test ✓ |
| AC-17h | Token tracking: per-step + run totals | **IMPLEMENTED** | `orchestrator.py:244–248, 436–437`; `total_cost_usd` rounded 6dp; `test_execute_pipeline_sums_tokens_on_completion` |
| AC-17i | Retry 3× (5/10/20s); BudgetExceeded non-retryable; artifacts retained | **PARTIAL** | Retry ✓; non-retryable flag ✓; artifacts retained ✓; BudgetExceeded step lifecycle [M1] |

**8 of 9 ACs fully implemented. AC-17d and AC-17i share one root cause [M1].**

---

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|---------|
| 1.1 BackgroundTasks param | ✅ | ✅ VERIFIED | `router.py:168` |
| 1.2 `_check_has_data_sources()` | ✅ | ✅ VERIFIED | `router.py:93–147` |
| 1.3 `background_tasks.add_task(execute_pipeline,...)` | ✅ | ✅ VERIFIED | `router.py:195–202` |
| 1.4 `import json` module-level; `agents_selected: list[str]` | ✅ | ✅ VERIFIED | `agent_run_service.py:13`; `router.py:76` |
| 2.1 `agents/__init__.py` | ✅ | ✅ VERIFIED | Empty package init |
| 2.2 `BAConsultantAgent` | ✅ | ✅ VERIFIED | `ba_consultant.py` — all fields + run() + _build_prompt() |
| 2.3 `QAConsultantAgent` | ✅ | ✅ VERIFIED | `qa_consultant.py` |
| 2.4 `AutomationConsultantAgent` | ✅ | ✅ VERIFIED | `automation_consultant.py` |
| 3.1 `orchestrator.py` — all methods | ✅ | ✅ VERIFIED | 5 helpers + execute_pipeline + singleton |
| 4.1 13 unit tests | ✅ | ✅ VERIFIED | 13 tests confirmed in `test_orchestrator.py` |
| 4.2 4 integration tests | ✅ | ✅ VERIFIED | 4 tests in `test_agent_pipeline.py` |

**11 of 11 completed tasks verified. 0 questionable. 0 falsely marked complete.**

---

### Test Coverage and Gaps

- 13 unit tests + 4 integration tests — 17 total. All DoD A6 one-line comments present.
- **Gap:** No test verifies step is marked `failed` when `BudgetExceededError` occurs [M1]
- **Gap (advisory):** `test_run_agent_step_marks_running_then_completed` verifies return value but not `_update_step` call contents (tokens_used, progress_pct=100, completed_at)

---

### Architectural Alignment

All 11 constraints (C1–C11) verified:
- C1 SQL security ✓, C2 session isolation ✓, C3 asyncio.sleep ✓, C4 BudgetExceeded caught separately ✓ (run only — step is gap [M1]), C5 `version` field ✓, C6 no migration ✓, C7 RBAC ✓, C8 tiktoken 40k ✓, C9 no LangChain ✓, C10 daily_budget non-None ✓, C11 error format ✓

---

### Security Notes

- No injection vectors: project_id UUID-validated; schema_name f-string only (validated upstream)
- `BudgetExceededError` attributes logged only — not exposed in API responses
- System prompts are server-controlled strings — no prompt injection surface
- `asyncio.sleep` prevents event loop blocking during retry

---

### Action Items

**Code Changes Required:**

- [ ] [Med] Fix `_run_agent_step` — mark step `failed` before re-raising `BudgetExceededError` [file: `backend/src/services/agents/orchestrator.py:199–202`]
- [ ] [Med] Add test `test_execute_pipeline_budget_exceeded_marks_step_failed` — assert `_update_step` called with `status="failed"` when `BudgetExceededError` occurs [file: `backend/tests/unit/services/test_orchestrator.py`]
- [ ] [Low] Fix error message: `"failed after {_MAX_RETRIES} attempts"` → `"failed after {_MAX_RETRIES} retries"` [file: `backend/src/services/agents/orchestrator.py:223`]

**Advisory Notes:**

- Note: AC-17f text says `daily_budget=None` — update to `daily_budget=100_000` to match C10 and implementation (no code change needed)
- Note: `ORDER BY agent_type` comment on `orchestrator.py:400` is misleading — execution order is determined by `agents_selected` list, not the query ORDER BY
- Note: Consider asserting `_update_step` kwargs (tokens_used, progress_pct=100, completed_at) in `test_run_agent_step_marks_running_then_completed`

---

## Senior Developer Review Pass 2 (AI)

**Reviewer:** Azfar
**Date:** 2026-02-28
**Outcome:** APPROVE

### Summary

All Pass 1 findings resolved. The single MEDIUM finding [M1] (BudgetExceededError leaving step in `running` state) is fixed correctly and covered by a new test. All LOW documentation fixes applied. 9/9 ACs fully implemented, 14/14 unit tests + 4/4 integration tests verified. No new issues found.

### Pass 1 Findings — Resolution Verification

| Finding | Severity | Resolution | Verified |
|---------|----------|-----------|---------|
| [M1] BudgetExceededError leaves step in `running` | Med | `_run_agent_step:200–209` — `except BudgetExceededError` now calls `_update_step(status="failed", error_message="Token budget exceeded", completed_at=now)` before `raise` | ✅ |
| New test for [M1] | Med | `test_execute_pipeline_budget_exceeded_marks_step_failed` added; asserts `status="failed"`, `error_message`, `completed_at` all present in step update | ✅ |
| [L1] File List "11 unit tests" | Low | Updated to "14 unit tests" inline | ✅ |
| [L2] Changelog "15 tests" | Low | Updated to "17/18 tests" inline | ✅ |
| [L3] Error message "3 attempts" | Low | `orchestrator.py:231` — `"retries"` replaces `"attempts"` | ✅ |

### Acceptance Criteria — Final Coverage

**9 of 9 ACs fully implemented.** All verified with evidence.

| AC# | Status | Key Evidence |
|-----|--------|-------------|
| AC-17a | ✅ IMPLEMENTED | `router.py:93–147`; integration test ✓ |
| AC-17b | ✅ IMPLEMENTED | `router.py:195–202`; 2 integration tests ✓ |
| AC-17c | ✅ IMPLEMENTED | `orchestrator.py:367–492`; unit test ✓ |
| AC-17d | ✅ IMPLEMENTED | [M1] fixed: step marked `failed` on BudgetExceededError; new unit test ✓ |
| AC-17e | ✅ IMPLEMENTED | `orchestrator.py:74–161`; 2 unit tests ✓ |
| AC-17f | ✅ IMPLEMENTED | All 3 agents `daily_budget=100_000` ✓ |
| AC-17g | ✅ IMPLEMENTED | `orchestrator.py:254–302`; unit test ✓ |
| AC-17h | ✅ IMPLEMENTED | `orchestrator.py:244–248, 436–437`; unit test ✓ |
| AC-17i | ✅ IMPLEMENTED | Retry ✓; BudgetExceededError non-retryable ✓; step+run both failed ✓; artifacts retained ✓ |

### Task Completion — Final

14/14 unit tests + 4/4 integration tests = **18/18 total passing.** All DoD A6 one-line comments present. No regressions.

### Action Items

None. Story is approved.
