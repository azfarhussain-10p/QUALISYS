# Story 2.9: Real-Time Agent Progress Tracking

Status: done

## Story

As a QA-Automation user,
I want to see live per-agent status cards update in real time as my pipeline runs,
so that I know exactly which agent is executing, how far along it is, and when results are ready
— without polling or page-refreshing.

## Requirements Context

Stories 2-6 through 2-8 delivered:
- Agent selection UI and pipeline creation (`POST /agent-runs`)
- Background `AgentOrchestrator` pipeline execution
- Token budget gate (AC-17) and LLM cache key (AC-18)

The orchestrator transitions steps through `queued → running → completed | failed` in the database,
but currently emits **no real-time signals** — the client has no way to learn of progress without
polling `GET /agent-runs/{run_id}`.

This story wires the approved SSE pattern spike (`sse_pattern.py`) into the orchestrator and
exposes a streaming endpoint, completing AC-19 through AC-21 from the Epic 2 tech spec.

**FRs Covered:**
- FR30 — Users can view agent execution progress and status in real time

**Out of Scope:**
- SSE for PM dashboard auto-refresh (Story 2-12, separate endpoint)
- Cancel run / DELETE endpoint (deferred)
- Redis pub/sub relay for horizontal scaling (MVP: single-process FastAPI)
- Multiple concurrent SSE subscribers per run (MVP: one stream per run_id)

**Architecture Constraints:**
- SSE endpoint MUST use `build_sse_response(event_generator, run_id)` from `src.patterns.sse_pattern`
- Event types MUST be drawn from `_VALID_EVENT_TYPES` = `{queued, running, complete, error, heartbeat}`
- SSE wire format: `data: {"type":"...", "run_id":"...", "payload":{...}}\n\n`
- Heartbeat (15 s) handled automatically by `build_sse_response`; no manual heartbeat code
- In-process `asyncio.Queue` per run (SSEManager singleton) for MVP event relay
  - Orchestrator calls `sse_manager.publish(run_id, event_type, payload)` at each state transition
  - SSE generator calls `sse_manager.get_or_create_queue(run_id)` and reads from it
  - Queue lifecycle: created by SSE subscriber, cleaned up in generator `finally` block
- Orchestrator publish is best-effort: no exception if no subscriber is registered (silent no-op)
- C2 (tenant isolation): SSE endpoint validates `run_id` exists in `"tenant_{slug}".agent_runs`

---

## Acceptance Criteria

**AC-19 (Backend — SSE endpoint):**

`GET /api/v1/events/agent-runs/{run_id}` returns a `StreamingResponse` with
`Content-Type: text/event-stream`.

- Uses `build_sse_response(event_generator, run_id)` from `src.patterns.sse_pattern` (C2-approved pattern).
- RBAC: `require_project_role("owner", "admin", "qa-automation")`.
- Validates `run_id` in `"tenant_{slug}".agent_runs`; returns 404 `RUN_NOT_FOUND` if absent.
- Event payloads:
  - `running` step: `{"step_id": str, "agent_type": str, "progress_pct": 0, "progress_label": str}`
  - `complete` step: `{"step_id": str, "agent_type": str, "tokens_used": int, "artifact_id": str}`
  - `complete` run: `{"run_id": str, "all_done": true}` — signals stream end to client
  - `error` step: `{"step_id": str, "agent_type": str, "error_code": "STEP_FAILED", "message": str}`
- Heartbeat emitted automatically every 15 s of generator silence.
- Generator terminates after emitting `complete` + `all_done: true` or on client disconnect.
- Headers: `X-Accel-Buffering: no`, `Cache-Control: no-cache`, `Connection: keep-alive`
  (set automatically by `build_sse_response`).

**AC-19b (Backend — Orchestrator publishes SSE events):**

`_run_agent_step()` and `execute_pipeline()` in `orchestrator.py` call
`await sse_manager.publish(run_id, event_type, payload)` at every state transition:

| Trigger | Event Type | Key Payload Fields |
|---------|------------|-------------------|
| Step transitions to `running` | `running` | `step_id`, `agent_type`, `progress_pct=0`, `progress_label` |
| Step transitions to `completed` | `complete` | `step_id`, `agent_type`, `tokens_used`, `artifact_id` |
| Step transitions to `failed` | `error` | `step_id`, `agent_type`, `error_code="STEP_FAILED"`, `message` |
| Run transitions to `completed` | `complete` | `run_id`, `all_done=True` |

`sse_manager.publish()` is a silent no-op when no subscriber queue is registered for the run.

**AC-20 (Frontend — Agent status cards):**

After `POST /agent-runs` returns 201:
- Component opens an `EventSource` to `/api/v1/events/agent-runs/{run_id}`
- Renders one status card per `agents_selected`:
  - `queued` — gray chip, "Queued" label, no progress bar
  - `running` — blue card, spinner icon, animated progress bar at `progress_pct`%,
    `progress_label` shown as subtitle
  - `complete` — green card, checkmark icon, "Complete" label
  - `error` — red card, error icon, error `message` shown as subtitle
- Cards update in real time as SSE events arrive (no page refresh needed).
- EventSource closed on component unmount or stream complete.

**AC-21 (Frontend — Run completion behavior):**

On receiving the `complete` event with `payload.all_done === true`:
- Show success toast: "Agent pipeline completed successfully!"
- Auto-navigate to the Artifacts tab after 1.5 s delay using React Router `useNavigate`.
- EventSource connection closed before navigation.

---

## Tasks

### Task 1 — SSEManager singleton

- [x] 1.1 Create `backend/src/services/sse_manager.py`:
  ```python
  """SSEManager — in-process asyncio.Queue registry for SSE event relay (Story 2-9)."""
  import asyncio, json
  from typing import Optional

  class SSEManager:
      def __init__(self) -> None:
          self._queues: dict[str, asyncio.Queue] = {}

      def get_or_create_queue(self, run_id: str) -> asyncio.Queue:
          if run_id not in self._queues:
              self._queues[run_id] = asyncio.Queue()
          return self._queues[run_id]

      def remove_queue(self, run_id: str) -> None:
          self._queues.pop(run_id, None)

      async def publish(self, run_id: str, event_type: str, payload: dict) -> None:
          """Best-effort publish — silent no-op if no subscriber registered."""
          q = self._queues.get(run_id)
          if q is not None:
              await q.put({"type": event_type, "payload": payload})

  sse_manager = SSEManager()  # module-level singleton
  ```

### Task 2 — Orchestrator: emit SSE events

- [x] 2.1 In `backend/src/services/agents/orchestrator.py`:
  - Add import: `from src.services.sse_manager import sse_manager`
  - In `_run_agent_step()`, after `self._update_step(... status="running" ...)`:
    ```python
    await sse_manager.publish(run_id, "running", {
        "step_id":      step_id,
        "agent_type":   agent_type,
        "progress_pct": 0,
        "progress_label": f"Agent {agent_type} is analyzing your project...",
    })
    ```
  - In `_run_agent_step()`, after `self._update_step(... status="completed" ...)`:
    ```python
    await sse_manager.publish(run_id, "complete", {
        "step_id":    step_id,
        "agent_type": agent_type,
        "tokens_used": result.tokens_used,
        "artifact_id": artifact_id,  # capture from _create_artifact() return value
    })
    ```
    Note: `_create_artifact()` currently returns `None` — update it to return `artifact_id: str`.
  - In `_run_agent_step()`, in the `BudgetExceededError` and `RuntimeError` failure paths:
    ```python
    await sse_manager.publish(run_id, "error", {
        "step_id":    step_id,
        "agent_type": agent_type,
        "error_code": "STEP_FAILED",
        "message":    error_msg,
    })
    ```
  - In `execute_pipeline()`, after marking run `completed`:
    ```python
    await sse_manager.publish(run_id, "complete", {
        "run_id":   run_id,
        "all_done": True,
    })
    ```

- [x] 2.2 Update `_create_artifact()` return type from `None` to `str` (returns `artifact_id`):
  ```python
  async def _create_artifact(self, ...) -> str:
      artifact_id = str(uuid.uuid4())
      ...  # existing INSERT logic unchanged
      return artifact_id
  ```

### Task 3 — SSE endpoint

- [x] 3.1 Create `backend/src/api/v1/events/__init__.py` (empty).
- [x] 3.2 Create `backend/src/api/v1/events/router.py`:
  ```python
  """QUALISYS — Agent Run SSE Endpoint (Story 2-9, AC-19)."""
  import asyncio, json, uuid
  from typing import AsyncGenerator

  from fastapi import APIRouter, Depends, HTTPException, status
  from fastapi.responses import StreamingResponse
  from sqlalchemy import text
  from sqlalchemy.ext.asyncio import AsyncSession

  from src.db import get_db
  from src.middleware.rbac import require_project_role
  from src.middleware.tenant_context import current_tenant_slug
  from src.patterns.sse_pattern import SSEEvent, build_sse_response
  from src.services.sse_manager import sse_manager
  from src.services.tenant_provisioning import slug_to_schema_name

  router = APIRouter(tags=["Events"])

  @router.get("/api/v1/events/agent-runs/{run_id}")
  async def agent_run_sse_endpoint(
      run_id:  uuid.UUID,
      auth:    tuple = require_project_role("owner", "admin", "qa-automation"),
      db:      AsyncSession = Depends(get_db),
  ) -> StreamingResponse:
      schema_name = slug_to_schema_name(current_tenant_slug.get())
      result = await db.execute(
          text(f'SELECT id FROM "{schema_name}".agent_runs WHERE id = :run_id'),
          {"run_id": str(run_id)},
      )
      if not result.scalar_one_or_none():
          raise HTTPException(
              status_code=status.HTTP_404_NOT_FOUND,
              detail={"error": "RUN_NOT_FOUND", "message": "Agent run not found."},
          )
      return build_sse_response(
          event_generator=_event_generator(str(run_id)),
          run_id=run_id,
      )

  async def _event_generator(run_id: str) -> AsyncGenerator[SSEEvent, None]:
      q = sse_manager.get_or_create_queue(run_id)
      try:
          while True:
              data = await q.get()
              if data is None:      # sentinel — stream closed
                  return
              event_type = data.get("type", "error")
              yield SSEEvent(
                  type=event_type,
                  run_id=uuid.UUID(run_id),
                  payload=data.get("payload", {}),
              )
              if event_type == "complete" and data.get("payload", {}).get("all_done"):
                  return
      finally:
          sse_manager.remove_queue(run_id)
  ```

- [x] 3.3 Register events router in `backend/src/main.py`:
  ```python
  from src.api.v1.events.router import router as events_router
  app.include_router(events_router)
  ```

### Task 4 — Frontend: EventSource + status cards

- [x] 4.1 In `web/src/pages/projects/agents/AgentsTab.tsx`:
  - After successful `POST /agent-runs`, store `runId` in local state and open `EventSource`:
    ```typescript
    const eventSource = new EventSource(`/api/v1/events/agent-runs/${runId}`, {
      withCredentials: true,
    });
    ```
  - Maintain agent status state:
    ```typescript
    type AgentStatus = "queued" | "running" | "complete" | "error";
    const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>({});
    const [agentProgress, setAgentProgress] = useState<Record<string, number>>({});
    const [agentLabels, setAgentLabels]     = useState<Record<string, string>>({});
    ```
  - Handle events:
    ```typescript
    eventSource.onmessage = (e) => {
      const { type, payload } = JSON.parse(e.data);
      if (type === "running") {
        setAgentStatuses(s => ({ ...s, [payload.agent_type]: "running" }));
        setAgentProgress(p => ({ ...p, [payload.agent_type]: payload.progress_pct }));
        setAgentLabels(l   => ({ ...l, [payload.agent_type]: payload.progress_label }));
      } else if (type === "complete" && !payload.all_done) {
        setAgentStatuses(s => ({ ...s, [payload.agent_type]: "complete" }));
      } else if (type === "complete" && payload.all_done) {
        eventSource.close();
        // AC-21: success toast + navigate to artifacts
      } else if (type === "error") {
        setAgentStatuses(s => ({ ...s, [payload.agent_type]: "error" }));
      }
    };
    ```
  - Cleanup EventSource on unmount: `return () => eventSource.close();`

- [x] 4.2 Render agent status cards (one per `agents_selected`):
  - Visual states:
    - `queued` — gray background, "Queued" text, no progress bar
    - `running` — blue background, spinner (`animate-spin`), progress bar at `agentProgress[type]`%,
      `agentLabels[type]` as subtitle
    - `complete` — green background, checkmark icon, "Complete" text
    - `error` — red background, error icon, error label from `agentLabels[type]`
  - Use Tailwind classes consistent with existing Epic 1 component palette.

- [x] 4.3 Implement AC-21 on `all_done`:
  ```typescript
  import { useNavigate } from 'react-router-dom';
  const navigate = useNavigate();
  // in handler:
  toast.success("Agent pipeline completed successfully!");
  setTimeout(() => navigate(`/projects/${projectId}/artifacts`), 1500);
  ```

### Task 5 — Unit Tests (≥4)

- [x] 5.1 Create `backend/tests/unit/services/test_sse_manager.py`:
  - `test_get_or_create_queue_creates_new_queue` — Proves: first call creates a new asyncio.Queue.
  - `test_get_or_create_queue_returns_same_queue` — Proves: same run_id returns identical queue instance.
  - `test_publish_puts_event_in_queue` — Proves: publish() enqueues event dict with type + payload.
  - `test_publish_no_op_when_no_subscriber` — Proves: publish() without a registered queue raises no exception.
  - `test_remove_queue_cleans_up` — Proves: remove_queue() deletes the queue; subsequent get returns None.

- [x] 5.2 Add `test_create_artifact_returns_artifact_id` to orchestrator unit tests (or inline in integration):
  - Proves: `_create_artifact()` now returns a non-empty UUID string.

### Task 6 — Integration Tests (≥3)

- [x] 6.1 Create `backend/tests/integration/test_sse_events.py`:
  - `test_sse_endpoint_404_unknown_run` — Proves: GET /events/agent-runs/{unknown_id} → 404 RUN_NOT_FOUND.
  - `test_sse_endpoint_200_known_run` — Proves: GET /events/agent-runs/{known_id} → 200 StreamingResponse with `Content-Type: text/event-stream`.
  - `test_sse_endpoint_events_sequence` — Proves: mock SSEManager publish sequence; SSE stream emits `running` then `complete` events in order.

### Task 7 — Sprint Status Update

- [x] 7.1 Update `docs/sprint-status.yaml`: `2-9-real-time-agent-progress-tracking` → `in-progress`
  (SM will set to `drafted` now; DEV agent moves to `in-progress` on story pickup).

### Review Follow-ups (AI)

- [x] [AI-Review][Med] Emit run-level SSE termination signal in `execute_pipeline()` BudgetExceededError path [file: `backend/src/services/agents/orchestrator.py`] (M-1)
- [x] [AI-Review][Med] Emit run-level SSE termination signal in `execute_pipeline()` generic Exception path [file: `backend/src/services/agents/orchestrator.py`] (M-1)
- [x] [AI-Review][Med] Handle `all_done+error` in frontend — show error banner, do not navigate to artifacts on failure [file: `web/src/pages/projects/agents/AgentsTab.tsx`] (M-1c)
- [x] [AI-Review][Med] Add integration test `test_sse_pipeline_failure_terminates_stream` [file: `backend/tests/integration/test_sse_events.py`] (M-1)
- [x] [AI-Review][Low] Wrap `JSON.parse(e.data)` in try/catch in `es.onmessage` [file: `web/src/pages/projects/agents/AgentsTab.tsx`] (L-1)
- [x] [AI-Review][Low] Add `setActiveAgents([])` in `es.onerror` handler [file: `web/src/pages/projects/agents/AgentsTab.tsx`] (L-2)
- [x] [AI-Review][Low] `asyncio.Queue(maxsize=1000)` in SSEManager [file: `backend/src/services/sse_manager.py`] (L-3)
- [x] [AI-Review][Low] Corrected stale SSE endpoint path in tech-spec-epic-2.md §4.1 [file: `docs/stories/epic-2/tech-spec-epic-2.md`] (L-4)

---

## Definition of Done

> **Epic 2 DoD — updated per Epic 1 Retrospective (2026-02-26, A5 + A8)**

**Standard checks (every story):**
- [x] All ACs implemented and verified
- [x] Unit tests written — each test has a one-line comment stating the behaviour proved (A6)
- [x] Integration tests written and passing
- [x] Code review completed and approved (rolling — no batch reviews, A3)

**Epic 2 additions:**
- [x] **Patterns match spike** — SSE endpoint uses `build_sse_response()` from `sse_pattern.py`;
  `SSEEvent` type values drawn from `_VALID_EVENT_TYPES`; no duplicate heartbeat logic

---

## Dev Notes

### SSE Event Flow

```
POST /agent-runs (201)
  └─ create_run() → run_id returned
       └─ BackgroundTask: execute_pipeline(run_id, ...)

GET /api/v1/events/agent-runs/{run_id}
  └─ validate run in tenant schema
       └─ build_sse_response(_event_generator(run_id), run_id)
            └─ _event_generator: q = sse_manager.get_or_create_queue(run_id)

execute_pipeline() [background]
  ├─ step → running  → sse_manager.publish(run_id, "running",  {step_id, agent_type, progress_pct=0, ...})
  ├─ step → complete → sse_manager.publish(run_id, "complete", {step_id, agent_type, tokens_used, artifact_id})
  ├─ step → failed   → sse_manager.publish(run_id, "error",   {step_id, agent_type, error_code, message})
  └─ run  → complete → sse_manager.publish(run_id, "complete", {run_id, all_done: True})
                            └─ _event_generator sees all_done → yields final complete → returns
                                 └─ build_sse_response / _heartbeat_aware_stream terminates stream
```

### SSEManager Timing

The SSE subscriber queue is created lazily when the client opens the EventSource
(`_event_generator` calls `get_or_create_queue`). This happens _after_ the 201 response is
sent. The orchestrator background task also starts after the 201 response. In practice the
client opens EventSource in the same JS event loop tick as receiving the 201, before the
background task begins its first DB write. If events are published before the subscriber
connects, they are silently dropped (no queue yet). This is acceptable for MVP because:
1. The orchestrator's first event (`running`) fires only after a DB UPDATE (100–300 ms into the task)
2. The client EventSource opens within milliseconds of the 201 response

For production hardening: pre-create the queue in `start_run_endpoint()` before dispatching
`execute_pipeline` — and use Redis pub/sub for multi-replica support.

### `_create_artifact()` Return Value Change

Task 2.2 changes the return type of `_create_artifact()` from `None` to `str`. The single
call site in `_run_agent_step()` currently ignores the return value — update it to capture
`artifact_id = await self._create_artifact(...)` so it can be included in the `complete` event.

### SSE Pattern Contract Tests (do NOT re-test)

`backend/tests/patterns/test_sse_pattern.py` already has 11 contract tests covering:
- `SSEEvent.to_wire()` format and validation
- `build_sse_response()` headers and media_type
- Heartbeat emission on generator silence

Do not duplicate these. New tests cover the SSEManager and endpoint behaviour only.

### Frontend EventSource Pattern

Use the native `EventSource` API (no additional library). The existing auth uses cookies
(set by the backend JWT session), so `withCredentials: true` is required. Error handling:
`eventSource.onerror = () => { setError("Connection lost"); eventSource.close(); }`.

### Learnings from Previous Story (2-8)

**From Story 2-8 (Status: done)**

- **Patch target rule (CRITICAL for tests):** Services with a module-level
  `from src.cache import get_redis_client` binding must be patched at
  `src.services.{service_name}.get_redis_client`, NOT at `src.cache.get_redis_client`.
  `sse_manager.py` does NOT use Redis, so this rule does not apply to its tests.
- **Token budget gate now in POST /agent-runs hot path:** Integration tests that call
  `POST /api/v1/projects/{id}/agent-runs` must patch
  `src.services.token_budget_service.get_redis_client` to avoid real Redis connection.
  This applies to any new integration tests that also exercise the POST endpoint.
- **`_create_artifact()` currently returns `None`:** Task 2.2 updates this — be careful not
  to break the existing `_run_agent_step()` call path.

[Source: docs/stories/epic-2/2-8-agent-execution-engine.md#Dev-Agent-Record]

### References

- SSE pattern spike: `backend/src/patterns/sse_pattern.py`
- SSE contract tests: `backend/tests/patterns/test_sse_pattern.py` (11 tests — do NOT duplicate)
- Orchestrator: `backend/src/services/agents/orchestrator.py`
- Agent runs router: `backend/src/api/v1/agent_runs/router.py`
- Tech spec AC-19–21: `docs/stories/epic-2/tech-spec-epic-2.md#8-acceptance-criteria`
- Frontend agent tab: `web/src/pages/projects/agents/AgentsTab.tsx`

## File List

- `backend/src/services/sse_manager.py` — NEW (SSEManager singleton + asyncio.Queue registry)
- `backend/src/api/v1/events/__init__.py` — NEW (package init, empty)
- `backend/src/api/v1/events/router.py` — NEW (GET /api/v1/events/agent-runs/{run_id})
- `backend/src/services/agents/orchestrator.py` — MODIFIED (import sse_manager, emit events, return artifact_id from _create_artifact)
- `backend/src/main.py` — MODIFIED (register events_router)
- `web/src/pages/projects/agents/AgentsTab.tsx` — MODIFIED (EventSource, status cards, AC-21 completion)
- `backend/tests/unit/services/test_sse_manager.py` — NEW (7 unit tests)
- `backend/tests/unit/services/test_orchestrator.py` — MODIFIED (appended test_create_artifact_returns_artifact_id)
- `backend/tests/integration/test_sse_events.py` — NEW (3 integration tests)
- `docs/stories/epic-2/2-9-real-time-agent-progress-tracking.context.xml` — NEW (SM-generated context)

## Dev Agent Record

### Context Reference

- docs/stories/epic-2/2-9-real-time-agent-progress-tracking.context.xml

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(none — all tests passed first run)

### Completion Notes List

1. **Task 4.3 — AC-21 toast adaptation**: Story specified `toast.success(...)` but no toast library (`sonner`, `react-hot-toast`) exists in `package.json`. Implemented AC-21 completion feedback as an inline `completionMessage` state banner that displays "Agent pipeline completed successfully! Navigating to Artifacts…" and auto-dismisses on navigation. No new dependency added — consistent with existing error/success banner pattern in AgentsTab.
2. **SSE test stream termination**: Integration tests use a pre-populated `asyncio.Queue` (complete+all_done event seeded before the HTTP request) so the SSE generator terminates naturally without requiring a real orchestrator background task.
3. **`_create_artifact()` return type change**: Updated from `None → str` (returns `artifact_id`). Single call site in `_run_agent_step()` updated to capture `artifact_id = await self._create_artifact(...)`. All 15 existing orchestrator tests still pass.
4. **test_sse_manager.py count**: 7 unit tests implemented (story spec said ≥4; added `test_get_or_create_queue_different_runs_are_independent` and `test_remove_queue_no_op_when_not_found` for completeness per DoD A6).
5. **Full regression baseline**: Pre-existing suite has ~143 failures unrelated to Story 2-9 (auth, orgs, members integration tests requiring real DB/Redis). All 25 Story-2-9-specific tests pass 25/25.
6. **Review Pass 2 fixes (2026-02-28)**: Addressed all 4 MEDIUM + 4 LOW findings from code review. Key changes: (a) `execute_pipeline()` now emits `complete+all_done+error=True` in both failure paths so client EventSource terminates cleanly; (b) frontend `all_done` handler checks `payload.error` to show error banner vs navigate; (c) `JSON.parse` guarded in `onmessage`; (d) `onerror` resets `activeAgents`; (e) Queue maxsize=1000; (f) tech spec path corrected. New test: `test_sse_pipeline_failure_terminates_stream`. Total: **26/26 tests passing**.

### File List

- `backend/src/services/sse_manager.py` — NEW (+ maxsize=1000 fix L-3)
- `backend/src/api/v1/events/__init__.py` — NEW
- `backend/src/api/v1/events/router.py` — NEW
- `backend/src/services/agents/orchestrator.py` — MODIFIED (+ run-level SSE termination on failure M-1)
- `backend/src/main.py` — MODIFIED
- `web/src/pages/projects/agents/AgentsTab.tsx` — MODIFIED (+ all_done+error handler M-1c, JSON.parse guard L-1, onerror reset L-2)
- `backend/tests/unit/services/test_sse_manager.py` — NEW
- `backend/tests/unit/services/test_orchestrator.py` — MODIFIED
- `backend/tests/integration/test_sse_events.py` — NEW (+ test_sse_pipeline_failure_terminates_stream M-1)
- `docs/stories/epic-2/tech-spec-epic-2.md` — MODIFIED (corrected SSE endpoint path L-4)
- `docs/stories/epic-2/2-9-real-time-agent-progress-tracking.context.xml` — NEW

---

## Senior Developer Review (AI)

**Reviewer:** Azfar
**Date:** 2026-02-28
**Outcome:** Changes Requested

---

### Summary

Story 2-9 implements real-time SSE agent progress tracking with clean separation between the SSEManager singleton, the events endpoint, and the orchestrator publish calls. The implementation follows the C2 pattern contract exactly. AC-19, AC-19b, AC-20, and AC-21 (success path) are fully implemented and verified with evidence. All 25 tests pass.

One **MEDIUM severity** gap found: when `execute_pipeline()` terminates abnormally (budget exceeded or retries exhausted), the client EventSource is never signalled to close — it receives step-level `error` events but no run-level termination, leaving it connected indefinitely (receiving only 15 s heartbeats). Four LOW severity advisory notes also included.

---

### Outcome: Changes Requested

**Reason:** 1 MEDIUM severity finding — SSE stream not terminated on pipeline failure paths.

---

### Key Findings

#### HIGH Severity
None.

#### MEDIUM Severity

**M-1: Pipeline failure paths do not emit run-level SSE termination signal**
[`backend/src/services/agents/orchestrator.py:507-542`]

When `execute_pipeline()` catches `BudgetExceededError` (line 507) or a generic `Exception` (line 525), it updates the run to `failed` and commits — but does **not** call `sse_manager.publish()`. The client receives the step-level `error` event (emitted inside `_run_agent_step()`) but no run-level completion signal.

Consequence: The client `EventSource` stays open indefinitely. The heartbeat mechanism (`sse_pattern.py`, 15 s interval) keeps the TCP connection alive, so `es.onerror` will **not** fire. Status cards show the failed agent as `error`, but the user sees no done state and cannot navigate away without a manual page refresh. This directly affects AC-21 completeness on the failure path.

**Fix required:** In both failure `except` blocks in `execute_pipeline()`, after the `await db.commit()` call, add:
```python
# best-effort — notify client SSE stream to close on failure
try:
    await sse_manager.publish(run_id, "complete", {
        "run_id": run_id,
        "all_done": True,
        "error": True,
    })
except Exception:  # noqa: BLE001
    pass
```
The frontend `all_done` handler should additionally check `payload.error` and show an error state rather than navigating to artifacts.

---

#### LOW Severity

**L-1: `JSON.parse(e.data)` not wrapped in try/catch** [`AgentsTab.tsx:292`]

If the server emits a malformed SSE data line, `JSON.parse` throws an uncaught exception in the `onmessage` handler. The EventSource silently stops updating. Wrap in try/catch and set `runError` on parse failure.

**L-2: `activeAgents` not reset on `onerror`** [`AgentsTab.tsx:320-323`]

When `es.onerror` fires, `activeAgents` is not cleared. Status cards remain visible and agent card selection stays disabled — user cannot start a new run without a page refresh. Add `setActiveAgents([])` in the `onerror` handler.

**L-3: `asyncio.Queue` created without `maxsize`** [`sse_manager.py:31`]

Under extreme orchestrator load, the queue can grow unbounded in memory. Acceptable for MVP single-process deployment. Advisory: `asyncio.Queue(maxsize=1000)` as a safety bound for production.

**L-4: Tech spec endpoint path discrepancy** (informational)

`tech-spec-epic-2.md:170` lists the SSE endpoint as `/api/v1/events/agents/{run_id}`, but the story AC-19 and implementation use `/api/v1/events/agent-runs/{run_id}`. Implementation matches story spec (authoritative). The tech spec table has a stale path.

---

### Acceptance Criteria Coverage

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-19 | `GET /api/v1/events/agent-runs/{run_id}` → `StreamingResponse` `text/event-stream` | **IMPLEMENTED** | `events/router.py:36-63` |
| AC-19 | Uses `build_sse_response()` from `sse_pattern` (C2) | **IMPLEMENTED** | `events/router.py:29,60` |
| AC-19 | RBAC: `require_project_role("owner","admin","qa-automation")` | **IMPLEMENTED** | `events/router.py:39` |
| AC-19 | Validates `run_id` in tenant schema; 404 `RUN_NOT_FOUND` | **IMPLEMENTED** | `events/router.py:50-58` |
| AC-19 | `running` payload: `step_id`, `agent_type`, `progress_pct=0`, `progress_label` | **IMPLEMENTED** | `orchestrator.py:188-194` |
| AC-19 | `complete` step payload: `step_id`, `agent_type`, `tokens_used`, `artifact_id` | **IMPLEMENTED** | `orchestrator.py:286-292` |
| AC-19 | `complete` run payload: `run_id`, `all_done: true` (success path) | **IMPLEMENTED** | `orchestrator.py:494-498` |
| AC-19 | `error` step payload: `step_id`, `agent_type`, `error_code`, `message` | **IMPLEMENTED** | `orchestrator.py:223-229, 251-257` |
| AC-19 | Heartbeat 15 s of silence | **IMPLEMENTED** | `sse_pattern.py:44,84-112` |
| AC-19 | Generator terminates after `complete+all_done` | **IMPLEMENTED** | `events/router.py:93-94` |
| AC-19 | Headers: `X-Accel-Buffering`, `Cache-Control`, `Connection` | **IMPLEMENTED** | `sse_pattern.py:148-154` |
| AC-19b | Publish on step→running | **IMPLEMENTED** | `orchestrator.py:188-194` |
| AC-19b | Publish on step→completed | **IMPLEMENTED** | `orchestrator.py:286-292` |
| AC-19b | Publish `error` on `BudgetExceededError` | **IMPLEMENTED** | `orchestrator.py:223-229` |
| AC-19b | Publish `error` on retry-exhausted | **IMPLEMENTED** | `orchestrator.py:251-257` |
| AC-19b | Publish `complete+all_done` on run→completed | **IMPLEMENTED** | `orchestrator.py:494-498` |
| AC-19b | Silent no-op when no subscriber | **IMPLEMENTED** | `sse_manager.py:43-45` |
| AC-19b | ⚠️ Run-level termination signal on pipeline failure | **PARTIAL** | `execute_pipeline:507-542` — step error published but no run-level termination (M-1) |
| AC-20 | EventSource opened after POST /agent-runs 201 | **IMPLEMENTED** | `AgentsTab.tsx:285-289` |
| AC-20 | One status card per `agents_selected` | **IMPLEMENTED** | `AgentsTab.tsx:397-408` |
| AC-20 | `queued` state: gray, "Queued" | **IMPLEMENTED** | `AgentStatusCard:145-157` |
| AC-20 | `running` state: blue, spinner `animate-spin`, progress bar, label | **IMPLEMENTED** | `AgentStatusCard:160-183` |
| AC-20 | `complete` state: green, checkmark | **IMPLEMENTED** | `AgentStatusCard:185-197` |
| AC-20 | `error` state: red, error icon, message subtitle | **IMPLEMENTED** | `AgentStatusCard:200-215` |
| AC-20 | EventSource closed on unmount | **IMPLEMENTED** | `AgentsTab.tsx:247-251` |
| AC-21 | Close EventSource on `all_done` | **IMPLEMENTED** | `AgentsTab.tsx:307-308` |
| AC-21 | Show success notification | **IMPLEMENTED** | `AgentsTab.tsx:309,443-453` (inline banner — no toast lib in project) |
| AC-21 | Auto-navigate to Artifacts tab after 1.5 s | **IMPLEMENTED** | `AgentsTab.tsx:310-312` |

**AC Coverage: 27 of 28 sub-criteria fully implemented, 1 partial (M-1).**

---

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| 1.1 Create `sse_manager.py` | [x] | ✅ VERIFIED | `sse_manager.py:1-49`; SSEManager + singleton |
| 2.1 Orchestrator imports + all publish calls | [x] | ✅ VERIFIED | `orchestrator.py:36`; publishes at `:188`, `:224`, `:252`, `:287`, `:495` |
| 2.2 `_create_artifact()` returns `str` | [x] | ✅ VERIFIED | `orchestrator.py:305,307,346` |
| 3.1 Create `events/__init__.py` | [x] | ✅ VERIFIED | File exists: `backend/src/api/v1/events/__init__.py` |
| 3.2 Create `events/router.py` | [x] | ✅ VERIFIED | `events/router.py:1-97`; endpoint + `_event_generator` |
| 3.3 Register events router in `main.py` | [x] | ✅ VERIFIED | `main.py:149-150` |
| 4.1 EventSource + state management | [x] | ✅ VERIFIED | `AgentsTab.tsx:230-243,285-324` |
| 4.2 Render status cards (`AgentStatusCard`) | [x] | ✅ VERIFIED | `AgentsTab.tsx:392-409`; `AgentStatusCard:136-216` |
| 4.3 AC-21 all_done handler + navigation | [x] | ✅ VERIFIED | `AgentsTab.tsx:305-312` |
| 5.1 `test_sse_manager.py` (7 tests, behavior comments) | [x] | ✅ VERIFIED | 7 tests passing, A6 comments on each |
| 5.2 `test_create_artifact_returns_artifact_id` | [x] | ✅ VERIFIED | Present in `test_orchestrator.py`, passes |
| 6.1 `test_sse_events.py` (3 integration tests) | [x] | ✅ VERIFIED | 3 tests passing (404, 200, sequence) |
| 7.1 `sprint-status.yaml` updated to `review` | [x] | ✅ VERIFIED | `sprint-status.yaml:151` |

**Task Completion Summary: 13 of 13 completed tasks verified, 0 questionable, 0 falsely marked complete.**

---

### Test Coverage and Gaps

**Covered (25 tests passing):**
- SSEManager unit tests (7): queue creation, idempotency, independence, publish enqueue, no-op publish, cleanup, no-op cleanup
- Orchestrator unit tests (15 + 1): all existing pipeline tests + `test_create_artifact_returns_artifact_id`
- SSE integration tests (3): 404 unknown run, 200 + `text/event-stream` content-type, event sequence order (running → step-complete → all_done)

**Gaps (Low — follow-up from M-1 fix):**
- No test for pipeline-failure SSE termination path — needs to be added as part of M-1 fix
- No frontend unit tests for EventSource lifecycle (acceptable — outside story scope)

---

### Architectural Alignment

- ✅ Uses `build_sse_response()` from `src.patterns.sse_pattern` — C2 contract honoured
- ✅ All event types from `_VALID_EVENT_TYPES`: `queued`, `running`, `complete`, `error`, `heartbeat` — enforced by `SSEEvent.to_wire()` at runtime
- ✅ No duplicate heartbeat code — `sse_pattern.py` owns heartbeat entirely
- ✅ Tenant isolation: `run_id` validated in `"{schema_name}".agent_runs` before stream opens; generator itself is tenant-unaware
- ✅ Schema-per-tenant: `slug_to_schema_name(current_tenant_slug.get())` — consistent with all Epic 2 patterns
- ✅ MVP constraint documented: in-process `asyncio.Queue`, single-process FastAPI; production path (Redis pub/sub) noted in `sse_manager.py:14`
- ⚠️ Tech spec table path discrepancy: `events/agents/{run_id}` vs `events/agent-runs/{run_id}` (L-4, informational only)

---

### Security Notes

- No SQL injection risk: parameterized query `{"run_id": str(run_id)}`; schema name from validated ContextVar ✓
- `uuid.UUID` FastAPI coercion prevents non-UUID `run_id` from reaching SQL ✓
- RBAC at dependency level before DB lookup ✓
- `withCredentials: true` on EventSource for cookie-based auth ✓
- SSEManager queues keyed by run_id strings from validated endpoints — no cross-tenant leakage possible ✓
- No PII or secrets in SSE payloads ✓

---

### Best-Practices and References

- [MDN — Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — `EventSource` API, `withCredentials`, `onerror` reconnect behaviour
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) — async generator pattern ✓
- [RFC 8895 §9.1 — EventSource reconnection](https://html.spec.whatwg.org/multipage/server-sent-events.html#reestablishing-the-connection) — clients auto-reconnect; `retry:` field for custom backoff (not required for MVP)
- Python `asyncio.Queue` — cooperative multitasking safety: dict operations on `_queues` are atomic between `await` points in single-threaded event loop ✓
- Nginx `X-Accel-Buffering: no` — required for SSE to pass through proxies without buffering ✓

---

### Action Items

**Code Changes Required:**

- [ ] [Med] Emit run-level SSE termination on `BudgetExceededError` path — add `await sse_manager.publish(run_id, "complete", {"run_id": run_id, "all_done": True, "error": True})` after `await db.commit()` in `except BudgetExceededError:` block [file: `backend/src/services/agents/orchestrator.py:516`] (M-1)
- [ ] [Med] Emit run-level SSE termination on generic failure path — same publish call in `except Exception:` block after `await db.commit()` [file: `backend/src/services/agents/orchestrator.py:535`] (M-1)
- [ ] [Med] Handle `all_done+error` in frontend — check `payload.error` in `all_done` handler; show error banner instead of navigating to Artifacts [file: `web/src/pages/projects/agents/AgentsTab.tsx:305-312`] (M-1)
- [ ] [Med] Add integration test verifying run-level termination event on pipeline failure [file: `backend/tests/integration/test_sse_events.py`] (M-1)

**Advisory Notes:**

- Note: Wrap `JSON.parse(e.data)` in try/catch in `es.onmessage` to prevent silent crash on malformed event (L-1) [file: `AgentsTab.tsx:292`]
- Note: Add `setActiveAgents([])` in `es.onerror` handler to re-enable agent selection after stream error (L-2) [file: `AgentsTab.tsx:320`]
- Note: Consider `asyncio.Queue(maxsize=1000)` in `SSEManager.get_or_create_queue()` for memory safety under sustained load (L-3) [file: `sse_manager.py:31`]
- Note: Correct SSE endpoint path in tech-spec-epic-2.md section 4.1 table: `events/agents/{run_id}` → `events/agent-runs/{run_id}` (L-4)

---

## Senior Developer Review (AI) — Pass 2

**Reviewer:** Azfar
**Date:** 2026-02-28
**Outcome:** Approve

---

### Summary

Pass 2 review. All 4 MEDIUM and 4 LOW findings from Pass 1 have been fully implemented and verified with evidence. The M-1 failure-path SSE termination fix is clean and correct: both `BudgetExceededError` and generic `Exception` paths in `execute_pipeline()` now emit `complete+all_done+error=True` after committing the failed run state, ensuring the client `EventSource` terminates cleanly on all code paths. The frontend correctly distinguishes error vs success paths on `all_done`. The new integration test (`test_sse_pipeline_failure_terminates_stream`) proves the full failure path end-to-end. All 26 tests pass.

No new findings. Story is complete and meets all Definition of Done criteria.

---

### Outcome: Approve

All ACs fully implemented, all completed tasks verified, zero HIGH/MEDIUM/LOW action items.

---

### Key Findings

#### HIGH Severity
None.

#### MEDIUM Severity
None (all Pass 1 MEDIUM findings resolved).

#### LOW Severity
None (all Pass 1 LOW findings resolved).

---

### Acceptance Criteria Coverage

| AC | Description | Status | Evidence |
|----|-------------|--------|----------|
| AC-19 | `GET /api/v1/events/agent-runs/{run_id}` → `StreamingResponse` `text/event-stream` | **IMPLEMENTED** | `events/router.py:36-63` |
| AC-19 | Uses `build_sse_response()` from C2 pattern | **IMPLEMENTED** | `events/router.py:60-63` |
| AC-19 | RBAC: `require_project_role("owner","admin","qa-automation")` | **IMPLEMENTED** | `events/router.py:39` |
| AC-19 | Validates `run_id` in tenant schema; 404 `RUN_NOT_FOUND` | **IMPLEMENTED** | `events/router.py:50-58` |
| AC-19 | `running` payload: `step_id`, `agent_type`, `progress_pct=0`, `progress_label` | **IMPLEMENTED** | `orchestrator.py:189-194` |
| AC-19 | `complete` step payload: `step_id`, `agent_type`, `tokens_used`, `artifact_id` | **IMPLEMENTED** | `orchestrator.py:287-292` |
| AC-19 | `complete` run payload: `run_id`, `all_done: true` | **IMPLEMENTED** | `orchestrator.py:495-498` |
| AC-19 | `error` step payload: `step_id`, `agent_type`, `error_code`, `message` | **IMPLEMENTED** | `orchestrator.py:224-229, 252-257` |
| AC-19 | Heartbeat 15 s of silence | **IMPLEMENTED** | `sse_pattern.py:44, 84-112` |
| AC-19 | Generator terminates after `complete+all_done` | **IMPLEMENTED** | `router.py:93-94` |
| AC-19 | Headers: `X-Accel-Buffering`, `Cache-Control`, `Connection` | **IMPLEMENTED** | `sse_pattern.py:148-154` |
| AC-19b | Publish step→running | **IMPLEMENTED** | `orchestrator.py:189-194` |
| AC-19b | Publish step→completed | **IMPLEMENTED** | `orchestrator.py:287-292` |
| AC-19b | Publish `error` on `BudgetExceededError` | **IMPLEMENTED** | `orchestrator.py:224-229` |
| AC-19b | Publish `error` on retry-exhausted | **IMPLEMENTED** | `orchestrator.py:252-257` |
| AC-19b | Publish `complete+all_done` on run→completed | **IMPLEMENTED** | `orchestrator.py:495-498` |
| AC-19b | Silent no-op when no subscriber | **IMPLEMENTED** | `sse_manager.py:43-45` |
| AC-19b | Run-level termination on `BudgetExceededError` failure (M-1 fix) | **IMPLEMENTED** | `orchestrator.py:517-525` |
| AC-19b | Run-level termination on generic `Exception` failure (M-1 fix) | **IMPLEMENTED** | `orchestrator.py:551-559` |
| AC-20 | EventSource opened after POST /agent-runs 201 | **IMPLEMENTED** | `AgentsTab.tsx:285-289` |
| AC-20 | One status card per `agents_selected` | **IMPLEMENTED** | `AgentsTab.tsx:410-419` |
| AC-20 | `queued` state: gray, "Queued" | **IMPLEMENTED** | `AgentStatusCard:145-158` |
| AC-20 | `running` state: blue, animate-spin, progress bar, label | **IMPLEMENTED** | `AgentStatusCard:160-183` |
| AC-20 | `complete` state: green, checkmark | **IMPLEMENTED** | `AgentStatusCard:185-198` |
| AC-20 | `error` state: red, XCircle, message subtitle | **IMPLEMENTED** | `AgentStatusCard:200-215` |
| AC-20 | EventSource closed on unmount | **IMPLEMENTED** | `AgentsTab.tsx:247-251` |
| AC-21 | Close EventSource on `all_done` | **IMPLEMENTED** | `AgentsTab.tsx:312-313` |
| AC-21 | Show success notification | **IMPLEMENTED** | `AgentsTab.tsx:320, 457-466` |
| AC-21 | Auto-navigate to Artifacts after 1.5 s | **IMPLEMENTED** | `AgentsTab.tsx:321-323` |
| AC-21 | Error path: show error banner, do NOT navigate (M-1c fix) | **IMPLEMENTED** | `AgentsTab.tsx:314-317` |

**AC Coverage: 30 of 30 sub-criteria fully implemented (28 original + 2 new from M-1 fix).**

---

### Task Completion Validation

| Task | Marked | Verified | Evidence |
|------|--------|----------|----------|
| 1.1 Create `sse_manager.py` | [x] | ✅ VERIFIED | `sse_manager.py:22-49`; `maxsize=1000` at `:31` (L-3 fix) |
| 2.1 Orchestrator: 7 publish calls | [x] | ✅ VERIFIED | `:189, :224, :252, :287, :495, :519, :553` |
| 2.2 `_create_artifact()` → `str` | [x] | ✅ VERIFIED | `orchestrator.py:305, 346` |
| 3.1 `events/__init__.py` | [x] | ✅ VERIFIED | File exists |
| 3.2 `events/router.py` | [x] | ✅ VERIFIED | `router.py:1-97` |
| 3.3 Register events router in `main.py` | [x] | ✅ VERIFIED | `main.py:149-150` |
| 4.1 EventSource + state + cleanup | [x] | ✅ VERIFIED | `AgentsTab.tsx:230-338`; L-1 guard `:292-299`; L-2 onerror `:334` |
| 4.2 `AgentStatusCard` 4 visual states | [x] | ✅ VERIFIED | `AgentsTab.tsx:136-216` |
| 4.3 AC-21 all_done handler + navigate | [x] | ✅ VERIFIED | `AgentsTab.tsx:310-324`; M-1c error path `:314-317` |
| 5.1 `test_sse_manager.py` (7 tests, A6) | [x] | ✅ VERIFIED | 7 tests, each with `# Proves:` comment |
| 5.2 `test_create_artifact_returns_artifact_id` | [x] | ✅ VERIFIED | `test_orchestrator.py:584` |
| 6.1 `test_sse_events.py` (4 tests) | [x] | ✅ VERIFIED | 404, 200, sequence, failure-terminates-stream |
| 7.1 `sprint-status.yaml` updated | [x] | ✅ VERIFIED | `sprint-status.yaml:151` |
| [AI-Review] M-1a BudgetExceededError SSE | [x] | ✅ VERIFIED | `orchestrator.py:517-525` |
| [AI-Review] M-1b Exception SSE | [x] | ✅ VERIFIED | `orchestrator.py:551-559` |
| [AI-Review] M-1c frontend error path | [x] | ✅ VERIFIED | `AgentsTab.tsx:314-317` |
| [AI-Review] M-1 integration test | [x] | ✅ VERIFIED | `test_sse_events.py:246-309` |
| [AI-Review] L-1 JSON.parse guard | [x] | ✅ VERIFIED | `AgentsTab.tsx:292-299` |
| [AI-Review] L-2 onerror reset activeAgents | [x] | ✅ VERIFIED | `AgentsTab.tsx:334` |
| [AI-Review] L-3 `asyncio.Queue(maxsize=1000)` | [x] | ✅ VERIFIED | `sse_manager.py:31` |
| [AI-Review] L-4 tech-spec path corrected | [x] | ✅ VERIFIED | `tech-spec-epic-2.md:170, 478` |

**Task Completion Summary: 21 of 21 tasks verified, 0 questionable, 0 falsely marked complete.**

---

### Test Coverage and Gaps

**Covered (26 tests passing):**
- `test_sse_manager.py` (7): queue creation, idempotency, independence, publish enqueue, no-op publish, cleanup, no-op cleanup
- `test_orchestrator.py` (15 + 1): full pipeline suite + `test_create_artifact_returns_artifact_id`
- `test_sse_events.py` (4): 404 unknown run, 200 + text/event-stream, event sequence order, pipeline failure terminates stream (M-1)

**Gaps:** None — all identified gaps from Pass 1 resolved by M-1 integration test addition.

---

### Architectural Alignment

- ✅ `build_sse_response()` from C2 contract — honoured
- ✅ All event types from `_VALID_EVENT_TYPES` enforced at runtime via `SSEEvent.to_wire()`
- ✅ No duplicate heartbeat logic — `sse_pattern.py` owns it entirely
- ✅ Tenant isolation: `run_id` validated in `"{schema_name}".agent_runs` before stream opens
- ✅ Schema-per-tenant: `slug_to_schema_name(current_tenant_slug.get())` — consistent
- ✅ In-process `asyncio.Queue(maxsize=1000)` — MVP single-process; Redis pub/sub path documented
- ✅ `_event_generator` cleanup via `finally: sse_manager.remove_queue(run_id)` — correct client disconnect handling
- ✅ Tech spec path corrected (`events/agent-runs/{run_id}`) — no discrepancy remaining

---

### Security Notes

No new security concerns. Pass 1 findings all confirmed clean:
- Parameterized SQL (`{"run_id": str(run_id)}`) ✅
- `uuid.UUID` FastAPI coercion prevents non-UUID from reaching SQL ✅
- RBAC evaluated before DB lookup ✅
- `withCredentials: true` for cookie auth on EventSource ✅
- No cross-tenant leakage via SSEManager (run_id from validated endpoint only) ✅
- No PII in SSE payloads ✅

---

### Best-Practices and References

- [MDN — Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) — implementation follows native EventSource API contract ✓
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) — async generator pattern ✓
- Python `asyncio.Queue(maxsize=1000)` — memory-bounded queue prevents unbounded growth ✓
- Nginx `X-Accel-Buffering: no` — present via `sse_pattern.py` ✓

---

### Action Items

None. All Pass 1 action items resolved. Story is approved.

---

## Change Log

| Date | Version | Description |
|------|---------|-------------|
| 2026-02-28 | 1.0 | Story implemented — all tasks complete, status → review |
| 2026-02-28 | 1.1 | Senior Developer Review appended — Changes Requested (M-1: pipeline failure SSE termination gap) |
| 2026-02-28 | 1.2 | Senior Developer Review Pass 2 — APPROVED. All Pass 1 findings resolved. 26/26 tests passing. |
