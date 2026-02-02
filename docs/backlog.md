# Engineering Backlog

This backlog collects cross-cutting or future action items that emerge from reviews and planning.

Routing guidance:

- Use this file for non-urgent optimizations, refactors, or follow-ups that span multiple stories/epics.
- Must-fix items to ship a story belong in that story's `Tasks / Subtasks`.
- Same-epic improvements may also be captured under the epic Tech Spec `Post-Review Follow-ups` section.

| Date | Story | Epic | Type | Severity | Owner | Status | Notes |
| ---- | ----- | ---- | ---- | -------- | ----- | ------ | ----- |
| 2026-02-02 | 0.1 | 0 | Security | Med | DEV Agent | Resolved | Scope state bucket policy to actual account ID instead of wildcard `*` [bootstrap/main.tf:124-126] |
| 2026-02-02 | 0.1 | 0 | Bug | Med | DEV Agent | Resolved | Add `replicationgroup` resource type to ElastiCache policy for DescribeReplicationGroups/ModifyReplicationGroup [iam/policies.tf:198] |
| 2026-02-02 | 0.1 | 0 | Security | Med | DEV Agent | Resolved | Scope CI/CD ECR push/pull to `qualisys-*` repositories [iam/policies.tf:82-98] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Consolidate duplicate `data.aws_caller_identity` into shared file [iam/roles.tf:6, cloudtrail.tf:5] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Use `var.project_name` interpolation for hardcoded bucket names [cloudtrail.tf:9] |
| 2026-02-02 | 0.1 | 0 | TechDebt | Low | DEV Agent | Resolved | Add explicit `filter {}` block to lifecycle rule [cloudtrail.tf:43] |
