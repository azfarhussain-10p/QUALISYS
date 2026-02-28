# Engineering Backlog

This backlog collects cross-cutting or future action items that emerge from reviews and planning.

Routing guidance:

- Use this file for non-urgent optimizations, refactors, or follow-ups that span multiple stories/epics.
- Must-fix items to ship a story belong in that story's `Tasks / Subtasks`.
- Same-epic improvements may also be captured under the epic Tech Spec `Post-Review Follow-ups` section.

| Date | Story | Epic | Type | Severity | Owner | Status | Notes |
| 2026-02-28 | 2.3 | 2 | Bug | Med | DEV Agent | Resolved | [M1] cleanup_expired_repos() filtered only status='cloned', missed 'analyzed' connections — fixed to IN ('cloned','analyzed') [github_connector_service.py:287] |
| 2026-02-28 | 2.3 | 2 | TechDebt | Low | DEV Agent | Resolved | [L2] DELETE /github endpoint missing "qa-automation" — fixed require_project_role("owner","admin","qa-automation") [router.py:111] |
| 2026-02-28 | 2.3 | 2 | TechDebt | Low | DEV Agent | Resolved | [L3] asyncio.get_event_loop().run_in_executor() replaced with asyncio.to_thread() [github_connector_service.py:353]; test mocks updated |
| 2026-02-28 | 2.7 | 2 | Bug | Med | DEV Agent | Resolved | [M1] BudgetExceededError leaves step in `running` — fixed _run_agent_step:200–209 to mark step `failed` before re-raising [orchestrator.py] |
| 2026-02-28 | 2.7 | 2 | Test | Med | DEV Agent | Resolved | [M1] Added test_execute_pipeline_budget_exceeded_marks_step_failed to test_orchestrator.py |
| 2026-02-28 | 2.7 | 2 | TechDebt | Low | DEV Agent | Resolved | [L3] Error message fixed to "3 retries" [orchestrator.py:231] |
| 2026-02-28 | 2.9 | 2 | Bug | Med | DEV | Resolved | [M-1] execute_pipeline() failure paths now emit complete+all_done+error=True — client EventSource terminates cleanly [orchestrator.py:516,535] |
| 2026-02-28 | 2.9 | 2 | Bug | Med | DEV | Resolved | [M-1] Frontend all_done+error handler shows error banner, does not navigate to artifacts [AgentsTab.tsx] |
| 2026-02-28 | 2.9 | 2 | Test | Med | DEV | Resolved | [M-1] test_sse_pipeline_failure_terminates_stream added — 26/26 passing [test_sse_events.py] |
| 2026-02-28 | 2.9 | 2 | TechDebt | Low | DEV | Resolved | [L-1] JSON.parse wrapped in try/catch in es.onmessage [AgentsTab.tsx] |
| 2026-02-28 | 2.9 | 2 | Bug | Low | DEV | Resolved | [L-2] setActiveAgents([]) added to es.onerror handler [AgentsTab.tsx] |
| 2026-02-28 | 2.9 | 2 | TechDebt | Low | DEV | Resolved | [L-3] asyncio.Queue(maxsize=1000) in SSEManager.get_or_create_queue() [sse_manager.py] |
| 2026-02-28 | 2.9 | 2 | Docs | Low | DEV | Resolved | [L-4] tech-spec-epic-2.md §4.1 corrected: events/agent-runs/{run_id} |
| ---- | ----- | ---- | ---- | -------- | ----- | ------ | ----- |
| 2026-02-02 | 0.1 | 0 | Security | Med | DEV Agent | Resolved | Scope state bucket policy to actual account ID instead of wildcard `*` [bootstrap/main.tf:124-126] |
| 2026-02-02 | 0.1 | 0 | Bug | Med | DEV Agent | Resolved | Add `replicationgroup` resource type to ElastiCache policy for DescribeReplicationGroups/ModifyReplicationGroup [iam/policies.tf:198] |
| 2026-02-02 | 0.1 | 0 | Security | Med | DEV Agent | Resolved | Scope CI/CD ECR push/pull to `qualisys-*` repositories [iam/policies.tf:82-98] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Consolidate duplicate `data.aws_caller_identity` into shared file [iam/roles.tf:6, cloudtrail.tf:5] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Use `var.project_name` interpolation for hardcoded bucket names [cloudtrail.tf:9] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Add explicit `filter {}` block to lifecycle rule [cloudtrail.tf:43] |
