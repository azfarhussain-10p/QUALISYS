# Sprint Change Proposal — Multi-Cloud Course Correction

**Date**: 2026-02-09
**Author**: PM Agent (John)
**Workflow**: correct-course (Incremental mode)
**Requested by**: Azfar (Product Owner)

---

## 1. Trigger & Context

### What Changed
Azure infrastructure was integrated at the Terraform and Kubernetes level (Two Roots architecture), but planning artifacts — stories, epics, and the infrastructure README — still referenced AWS exclusively.

### Discovery
- 12 ready-for-dev stories examined
- **147 AWS-specific references** found across 8 stories
- 4 stories already cloud-agnostic (0-15, 0-16, 0-17, 0-18, 0-21)
- CI/CD workflows already multi-cloud (`vars.CLOUD_PROVIDER`)
- Infrastructure code already multi-cloud (Terraform + K8s manifests for both)

### Gap
Documentation/planning artifacts only — **no code changes needed**.

---

## 2. Impact Assessment

### Stories Affected (8 of 12 ready-for-dev)

| Story | Title | AWS Refs | Impact |
|-------|-------|----------|--------|
| 0-11 | Staging Auto-Deployment | 14 | HIGH |
| 0-12 | Production Deployment with Approval Gate | 13 | HIGH |
| 0-13 | Load Balancer & Ingress | 15 | HIGH |
| 0-14 | Test Database Provisioning | 3 | LOW |
| 0-19 | Monitoring (Prometheus + Grafana) | 4 | LOW |
| 0-20 | Log Aggregation (CloudWatch/Loki) | 39 | CRITICAL |
| 0-22 | Third-Party API Keys | 42 | CRITICAL |

### Done Stories Annotated (9 of 10)

| Story | Title | Annotation |
|-------|-------|------------|
| 0-1 | Cloud Account & IAM Setup | Multi-cloud note added (96 AWS refs) |
| 0-2 | VPC & Network Configuration | Multi-cloud note added (18 AWS refs) |
| 0-3 | Kubernetes Cluster Provisioning | Multi-cloud note added (28 AWS refs) |
| 0-4 | PostgreSQL Multi-Tenant Database | Multi-cloud note added (35 AWS refs) |
| 0-5 | Redis Caching Layer | Multi-cloud note added (20 AWS refs) |
| 0-6 | Container Registry | Multi-cloud note added (19 AWS refs) |
| 0-7 | Secret Management | Multi-cloud note added (52 AWS refs) |
| 0-8 | GitHub Actions Workflow Setup | Multi-cloud note added (10 AWS refs) |
| 0-9 | Docker Build Automation | Multi-cloud note added (4 AWS refs) |

*Story 0-10 (Automated Test Execution on PR) was already cloud-agnostic — no annotation needed.*

### Stories NOT Affected (5 of 12 ready-for-dev)

| Story | Title | Reason |
|-------|-------|--------|
| 0-15 | Test Data Factories | Already cloud-agnostic |
| 0-16 | CI/CD Test Pipeline | Already cloud-agnostic |
| 0-17 | Test Reporting Dashboard | Already cloud-agnostic |
| 0-18 | Multi-Tenant Test Isolation | Already cloud-agnostic |
| 0-21 | Secrets Rotation | Already cloud-agnostic |

### Other Artifacts Affected

| Artifact | Impact |
|----------|--------|
| `docs/sprint-status.yaml` | Cloud Provider comment updated |
| `docs/epics/epic-0-infrastructure.md` | Cloud Platform field updated |
| `infrastructure/README.md` | Major update — multi-cloud overview, section annotations |

---

## 3. Changes Applied

### Approach: Annotation + Generalization

Rather than rewriting entire stories or removing AWS-specific examples (which are valuable reference documentation), we applied:

1. **Cloud-agnostic task descriptions** — Tasks referencing specific AWS services now include Azure equivalents in parentheses
2. **Multi-cloud annotations** — Blockquotes before AWS-specific code examples noting the Azure alternative
3. **Dependency updates** — Dependencies referencing EKS/ECR/etc. now use cloud-agnostic names with provider variants
4. **Variable name normalization** — `ECR_REGISTRY` → `CONTAINER_REGISTRY` in deployment manifests

### File-by-File Summary

| # | File | Changes | Type |
|---|------|---------|------|
| 1 | `docs/sprint-status.yaml` | 1 | Comment update |
| 2 | `docs/epics/epic-0-infrastructure.md` | 1 | Cloud Platform field |
| 3 | `docs/stories/0-11-staging-auto-deployment.md` | 6 | Tasks, AC, annotation, deps |
| 4 | `docs/stories/0-12-production-deployment-with-approval-gate.md` | 5 | Tasks, annotation, secrets, deps |
| 5 | `docs/stories/0-13-load-balancer-ingress-configuration.md` | 10 | ACs, tasks, decision table, annotation, deps |
| 6 | `docs/stories/0-14-test-database-provisioning.md` | 4 | Tasks, connection strings, deps |
| 7 | `docs/stories/0-19-monitoring-infrastructure-prometheus-grafana.md` | 2 | Secrets, storage class |
| 8 | `docs/stories/0-20-log-aggregation-elk-or-cloudwatch.md` | 12 | ACs, tasks, constraints, annotation, security, deps |
| 9 | `docs/stories/0-22-third-party-service-accounts-api-keys.md` | 10 | ACs, tasks, constraints, annotations, security, deps |
| 10 | `infrastructure/README.md` | 7 structural | Header, multi-cloud overview, prerequisites, quick start, directory tree, 8 section annotations, Azure CI/CD secrets |
| 11 | `docs/stories/0-1-cloud-account-iam-setup.md` | 1 | Multi-cloud annotation (done story) |
| 12 | `docs/stories/0-2-vpc-network-configuration.md` | 1 | Multi-cloud annotation (done story) |
| 13 | `docs/stories/0-3-kubernetes-cluster-provisioning.md` | 1 | Multi-cloud annotation (done story) |
| 14 | `docs/stories/0-4-postgresql-multi-tenant-database.md` | 1 | Multi-cloud annotation (done story) |
| 15 | `docs/stories/0-5-redis-caching-layer.md` | 1 | Multi-cloud annotation (done story) |
| 16 | `docs/stories/0-6-container-registry.md` | 1 | Multi-cloud annotation (done story) |
| 17 | `docs/stories/0-7-secret-management.md` | 1 | Multi-cloud annotation (done story) |
| 18 | `docs/stories/0-8-github-actions-workflow-setup.md` | 1 | Multi-cloud annotation (done story) |
| 19 | `docs/stories/0-9-docker-build-automation.md` | 1 | Multi-cloud annotation (done story) |

**Total**: ~67 individual edits across 19 files.

---

## 4. What Did NOT Change

- **No code changes** — All Terraform, Kubernetes manifests, and CI/CD workflows are already multi-cloud
- **No story status changes** — All stories remain `ready-for-dev`
- **No scope changes** — No stories added, removed, or re-prioritized
- **No sprint timeline impact** — Documentation-only changes
- **AWS-specific code examples preserved** — Annotated rather than removed (valuable for implementation reference)

---

## 5. Validation

### Consistency Checks
- CI/CD workflows (`deploy-staging.yml`, `deploy-production.yml`, `reusable-build.yml`, `reusable-deploy.yml`) already use `vars.CLOUD_PROVIDER` — stories now aligned
- `infrastructure/terraform/README.md` already documents Two Roots architecture — `infrastructure/README.md` now references it
- Azure Kubernetes manifests (`kubernetes/azure/`) already exist — stories now reference both providers

### Cross-Reference Verification
- `sprint-status.yaml` cloud provider comment matches `epic-0-infrastructure.md` Cloud Platform field
- All 8 modified stories reference `infrastructure/terraform/README.md` for Two Roots architecture
- Infrastructure README links to all cloud-specific READMEs

---

## 6. Routing

This change proposal is **self-contained** — all edits have been applied directly as part of this workflow execution. No further implementation routing is needed.

### For SM Agent (Bob)
- Story context XMLs for modified ready-for-dev stories have been regenerated (7 files)
- No sprint-status changes required (stories remain ready-for-dev)
- Done stories (0-1 through 0-9) have multi-cloud annotations — no context XML update needed

### For DEV Agent
- When implementing any modified story, refer to both AWS and Azure variants
- CI/CD workflows are the source of truth for multi-cloud deployment patterns
- `infrastructure/terraform/README.md` is the source of truth for the Two Roots architecture

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-02-09 | PM Agent (John) | Sprint Change Proposal created — Multi-cloud course correction |
| 2026-02-09 | PM Agent (John) | Added done story annotations (0-1 through 0-9) and context XML regeneration notes |
