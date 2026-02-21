# Story 1.12: Usage Analytics & Audit Logs (Basic)

Status: ready-for-dev

## Story

As an Admin,
I want to view usage analytics and audit logs,
so that I can monitor platform usage.

## Requirements Context

This is the **twelfth story** in Epic 1 (Foundation & Administration). It establishes the audit infrastructure that all previous stories (1.2-1.11) have been writing audit entries to, plus a basic analytics dashboard for platform usage metrics. The audit_logs table is created here — previous stories define WHAT to log but the actual logging infrastructure lands in this story. The analytics dashboard shows simple counts (users, projects, tests) with placeholders for richer metrics from Epics 2-5.

**FRs Covered:**
- FR104 — Admins can view usage analytics (tests run, storage consumed, agent executions)
- FR108 — System provides audit logs of all administrative actions

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model [Source: docs/architecture/architecture.md#ADR-001]
- Multi-tenancy: Audit logs in `{tenant_schema}.audit_logs` — tenant-scoped via ContextVar + RLS [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- Audit records MUST be immutable — no UPDATE or DELETE allowed on audit_logs table [Source: docs/architecture/architecture.md#Security-Threat-Model]
- RBAC: Only Owner/Admin can view audit logs and analytics dashboard [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix]
- Security: Parameterized queries ONLY; TLS 1.3 in transit [Source: docs/architecture/architecture.md#Security-Threat-Model]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts, audit pattern defined
- Story 1.2 (Organization Creation & Setup) — tenant context, RBAC decorators, audit trail AC
- Story 1.3 (Team Member Invitation) — audit: invitation lifecycle events
- Story 1.4 (User Management) — audit: role changes, user removal
- Story 1.5 (Login & Session Management) — JWT auth, audit: login events
- Story 1.9 (Project Creation & Configuration) — audit: project CRUD
- Story 1.10 (Project Team Assignment) — audit: member add/remove
- Story 1.11 (Project Management) — audit: archive/restore/delete

## Acceptance Criteria

1. **AC1: Admin Dashboard — Basic Metrics** — Admin dashboard page (`/admin/dashboard` or `/dashboard`) shows basic usage metrics via MetricCard widgets (shadcn/ui Card): total active users in organization (count from tenants_users), total projects (active count from projects), total test runs (placeholder: "—" or 0 — populated by Epic 2-4), storage consumed (placeholder: "—" — populated by Epic 2). Each metric card shows: title, value (large number), trend indicator (placeholder: neutral). Owner/Admin only (RBAC enforced). API: `GET /api/v1/admin/analytics`.

2. **AC2: Audit Log Table** — Database table `{tenant_schema}.audit_logs` created via Alembic migration: `id` (UUID PK), `tenant_id` (UUID NOT NULL), `actor_user_id` (UUID FK→public.users, NOT NULL), `action` (VARCHAR 100, NOT NULL — e.g., 'user.invited', 'project.created', 'role.changed'), `resource_type` (VARCHAR 50, NOT NULL — e.g., 'user', 'project', 'organization', 'invitation'), `resource_id` (UUID, nullable), `details` (JSONB — old/new values, additional context), `ip_address` (VARCHAR 45 — supports IPv6), `user_agent` (TEXT), `created_at` (TIMESTAMPTZ DEFAULT NOW()). RLS policy for tenant isolation. Indexes on: `(tenant_id, created_at DESC)`, `(tenant_id, action)`, `(tenant_id, actor_user_id)`. Table is INSERT-ONLY: no UPDATE or DELETE policies (immutable audit trail).

3. **AC3: Audit Service** — `AuditService` class with `log_action()` method: accepts actor_user_id, action, resource_type, resource_id, details (JSONB), ip_address, user_agent. Inserts into `{tenant_schema}.audit_logs` within current tenant context. Non-blocking: uses background task or fire-and-forget pattern (audit logging MUST NOT slow down the main request). Convenience methods: `log_user_action()`, `log_project_action()`, `log_org_action()` with pre-filled resource_type. Action naming convention: `{resource_type}.{verb}` — e.g., 'user.invited', 'user.role_changed', 'project.created', 'project.archived', 'project.deleted', 'member.added', 'member.removed', 'org.settings_updated'.

4. **AC4: Audit Log Viewer Page** — Audit log page (`/admin/audit-logs`) displays all audit entries for the organization in reverse chronological order. Table columns: timestamp (formatted in user's timezone per Story 1.8), actor (user name + avatar), action (human-readable label), resource (type + name/ID), details (expandable — shows old/new values), IP address. Paginated: 50 entries per page. Owner/Admin only.

5. **AC5: Audit Log Filtering** — Audit log page supports filters: date range picker (preset: Last 7 days, Last 30 days, Last 90 days, Custom range), action type dropdown (All, User Actions, Project Actions, Organization Actions, or granular: user.invited, project.created, etc.), actor dropdown (searchable list of org members). Filters applied server-side via query parameters. Active filters shown as removable chips. Filters persisted in URL for shareable links.

6. **AC6: Audit Log Export** — "Export CSV" button exports all audit entries matching current filters. CSV columns: timestamp, actor_email, actor_name, action, resource_type, resource_id, details (JSON string), ip_address, user_agent. `POST /api/v1/admin/audit-logs/export` returns CSV file download. For large datasets: server generates CSV and returns file (streaming response). Rate-limited: 5 exports per hour per user.

7. **AC7: Retroactive Audit Integration** — Provide `AuditService` as an importable module for all existing story endpoints to use. Document the audit action catalog (all action types from Stories 1.2-1.11). Stories implemented before this one will integrate AuditService calls when they are developed (since all Epic 1 stories are still ready-for-dev). Provide audit middleware/decorator pattern: `@audit_action('project.created')` that can be applied to endpoints to auto-log.

8. **AC8: Validation & Error Handling** — Invalid date range: returns 400. Invalid action type filter: returns 400. Export with no matching entries: returns empty CSV with headers. All endpoints require JWT + Owner/Admin role. All responses follow consistent error format from Story 1.1.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema — Audit Logs Table** (AC: #2)
  - [ ] 1.1 Create Alembic migration for `{tenant_schema}.audit_logs` table with all columns
  - [ ] 1.2 Create indexes: `(tenant_id, created_at DESC)`, `(tenant_id, action)`, `(tenant_id, actor_user_id)`
  - [ ] 1.3 Create RLS policy for tenant isolation
  - [ ] 1.4 Create INSERT-ONLY policy: GRANT INSERT on audit_logs, REVOKE UPDATE and DELETE (immutable)
  - [ ] 1.5 Add audit_logs table to TENANT_TABLES_DDL in conftest.py for test fixtures
  - [ ] 1.6 Write migration rollback script

- [ ] **Task 2: Audit Service** (AC: #3, #7)
  - [ ] 2.1 Create `AuditService` class: `log_action()`, `log_user_action()`, `log_project_action()`, `log_org_action()`
  - [ ] 2.2 Implement `log_action()`: async insert into tenant-scoped audit_logs, non-blocking (FastAPI BackgroundTasks or asyncio.create_task)
  - [ ] 2.3 Define action naming convention and action catalog document
  - [ ] 2.4 Create `@audit_action` decorator for auto-logging on endpoints
  - [ ] 2.5 Extract IP address and user_agent from FastAPI Request object
  - [ ] 2.6 Handle audit logging failures gracefully (log error, don't fail the request)

- [ ] **Task 3: Analytics Service** (AC: #1)
  - [ ] 3.1 Create `AnalyticsService` class: `get_dashboard_metrics()`
  - [ ] 3.2 Implement metrics: active users count (tenants_users), active projects count (projects WHERE is_active), test runs count (placeholder 0), storage consumed (placeholder "—")
  - [ ] 3.3 Cache metrics in Redis (5-minute TTL) to avoid repeated COUNT queries

- [ ] **Task 4: FastAPI Endpoints** (AC: #1, #4, #5, #6, #8)
  - [ ] 4.1 Create `GET /api/v1/admin/analytics` — returns dashboard metrics (Owner/Admin only)
  - [ ] 4.2 Create `GET /api/v1/admin/audit-logs` — list audit logs with query params: date_from, date_to, action, actor_user_id, page, per_page (default 50). Returns paginated results with total count
  - [ ] 4.3 Create `POST /api/v1/admin/audit-logs/export` — export filtered audit logs as CSV (streaming response)
  - [ ] 4.4 RBAC enforcement: `@require_role(['owner', 'admin'])` on all admin endpoints
  - [ ] 4.5 Rate limiting: 5 exports per user per hour
  - [ ] 4.6 Register AuditService in FastAPI dependency injection for use across all routers

- [ ] **Task 5: React UI — Admin Dashboard** (AC: #1)
  - [ ] 5.1 Create admin dashboard page (`/admin/dashboard`) with MetricCard widgets
  - [ ] 5.2 MetricCard component: title, value (large), trend indicator (placeholder neutral)
  - [ ] 5.3 4 metric cards: Active Users, Active Projects, Test Runs (placeholder), Storage (placeholder)
  - [ ] 5.4 Owner/Admin access only (redirect non-Admin to projects page)
  - [ ] 5.5 Add Admin Dashboard link to sidebar/nav for Owner/Admin users

- [ ] **Task 6: React UI — Audit Log Viewer** (AC: #4, #5, #6)
  - [ ] 6.1 Create audit log page (`/admin/audit-logs`) with table layout
  - [ ] 6.2 Table columns: timestamp (user timezone), actor (avatar + name), action (human label), resource, details (expandable row), IP
  - [ ] 6.3 Filter bar: date range picker (presets + custom), action type dropdown, actor dropdown (searchable)
  - [ ] 6.4 Active filter chips with remove option
  - [ ] 6.5 Pagination: 50 per page
  - [ ] 6.6 "Export CSV" button with loading state
  - [ ] 6.7 Filters persisted in URL query params
  - [ ] 6.8 Empty state: "No audit entries match your filters."

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: AuditService.log_action() inserts correct record, action naming validation
  - [ ] 7.2 Unit tests: AnalyticsService.get_dashboard_metrics() returns correct counts
  - [ ] 7.3 Integration tests: `GET /admin/analytics` — returns metrics, RBAC (non-admin 403)
  - [ ] 7.4 Integration tests: `GET /admin/audit-logs` — list with filters (date range, action, actor), pagination
  - [ ] 7.5 Integration tests: `POST /admin/audit-logs/export` — CSV download, empty result, rate limiting
  - [ ] 7.6 Integration tests: audit log immutability — UPDATE and DELETE on audit_logs rejected
  - [ ] 7.7 Integration tests: tenant isolation — audit logs from tenant A not visible in tenant B
  - [ ] 7.8 Integration tests: @audit_action decorator auto-logs endpoint calls
  - [ ] 7.9 Integration tests: non-blocking audit (request completes even if audit insert delayed)
  - [ ] 7.10 Security tests: RBAC bypass attempts, SQL injection in filters, cross-tenant access
  - [ ] 7.11 Frontend tests: dashboard metrics, audit log table, filters, export button, pagination

- [ ] **Task 8: Security Review** (AC: #2, #8)
  - [ ] 8.1 Verify audit_logs table is INSERT-ONLY (no UPDATE/DELETE)
  - [ ] 8.2 Verify tenant isolation via ContextVar + RLS on audit_logs
  - [ ] 8.3 Verify RBAC: only Owner/Admin can view audit logs and analytics
  - [ ] 8.4 Verify audit logging is non-blocking (doesn't slow requests)
  - [ ] 8.5 Verify no sensitive data in audit details (no password hashes, no tokens)
  - [ ] 8.6 Verify CSV export doesn't leak cross-tenant data
  - [ ] 8.7 Verify rate limiting on export endpoint

## Dev Notes

### Architecture Patterns

- **Audit infrastructure as foundation:** This story creates the audit_logs table and AuditService that all previous stories (1.2-1.11) have referenced in their AC8/AC9 sections. Since all Epic 1 stories are still in ready-for-dev status, the DEV agent implementing each story will import AuditService from this story's module. Implementation order recommendation: implement Story 1.12's audit infrastructure early so other stories can use it.
- **Immutable audit trail:** audit_logs table has INSERT-ONLY policy. No UPDATE or DELETE permissions granted. This ensures compliance with audit requirements from architecture. If records need correction, add a new "correction" entry pointing to the original.
- **Non-blocking logging:** AuditService.log_action() uses FastAPI BackgroundTasks or asyncio.create_task for fire-and-forget insertion. Audit logging failure MUST NOT cause the main request to fail. Log errors to application error log for monitoring.
- **Action naming convention:** `{resource_type}.{verb}` format standardizes audit entries across all stories. Examples: 'user.created', 'user.invited', 'user.role_changed', 'user.removed', 'project.created', 'project.updated', 'project.archived', 'project.deleted', 'member.added', 'member.removed', 'org.settings_updated', 'org.created'.
- **Analytics with placeholders:** Dashboard metrics show real counts for users and projects (simple COUNT queries). Test runs and storage are placeholders for Epics 2-5. Redis cache (5-min TTL) prevents repeated COUNT queries on every dashboard load.
- **CSV export:** Streaming response for large datasets. Server generates CSV rows from query results, streams to client. Avoids loading entire result set into memory.

### Project Structure Notes

- Audit service: `src/services/audit_service.py`
- Analytics service: `src/services/analytics_service.py`
- Audit model: `src/models/audit_log.py`
- API routes: `src/api/v1/admin/` (analytics, audit-logs, export)
- Audit decorator: `src/decorators/audit.py` or in audit_service.py
- Frontend dashboard: `src/pages/admin/Dashboard.tsx`
- Frontend audit log: `src/pages/admin/AuditLogs.tsx`
- Components: `src/components/admin/MetricCard.tsx`, `src/components/admin/AuditLogTable.tsx`, `src/components/admin/AuditFilters.tsx`
- Reuse: RBAC decorators from Story 1.2, tenant context from Story 1.2, JWT auth from Story 1.5

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Immutability tests critical: verify UPDATE/DELETE blocked on audit_logs
- Tenant isolation critical: verify audit logs scoped to tenant
- Non-blocking tests: verify request completes without waiting for audit insert
- Use existing `test_tenant` and `tenant_connection` fixtures from conftest.py — add audit_logs to TENANT_TABLES_DDL

### Learnings from Previous Story

**From Story 1-11-project-management-archive-delete-list (Status: drafted)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.11's specification establishes:

- **Audit before delete** — Story 1.11 requires audit entry logged BEFORE hard-delete (data available for audit). AuditService must support synchronous pre-action logging when needed (not just background).
- **Project lifecycle events** — Story 1.11 adds archive/restore/delete actions to the audit catalog. These are logged via AuditService from this story.
- **is_active pattern** — Soft-delete uses is_active column. Analytics service counts only is_active=true projects.

[Source: docs/stories/1-11-project-management-archive-delete-list.md]

### Audit Action Catalog

| Action | Resource Type | Details | Source Story |
|--------|--------------|---------|-------------|
| org.created | organization | name, slug, plan | 1.2 |
| org.settings_updated | organization | changed fields (old/new) | 1.2 |
| user.created | user | email, auth_provider | 1.1 |
| user.invited | invitation | email, role, invited_by | 1.3 |
| user.invitation_accepted | invitation | email, user_id | 1.3 |
| user.invitation_revoked | invitation | email, revoked_by | 1.3 |
| user.role_changed | user | old_role, new_role | 1.4 |
| user.removed | user | email, removed_by | 1.4 |
| user.login | session | auth_method, device_info | 1.5 |
| user.password_reset | user | (no values logged) | 1.6 |
| user.mfa_enabled | user | method: 'totp' | 1.7 |
| user.mfa_disabled | user | method: 'totp' | 1.7 |
| user.profile_updated | user | changed fields (old/new) | 1.8 |
| user.password_changed | user | (no values logged) | 1.8 |
| project.created | project | name, slug, created_by | 1.9 |
| project.updated | project | changed fields (old/new) | 1.9 |
| project.archived | project | name, archived_by | 1.11 |
| project.restored | project | name, restored_by | 1.11 |
| project.deleted | project | name, deleted_by | 1.11 |
| member.added | project_member | user_id, project_id, added_by | 1.10 |
| member.removed | project_member | user_id, project_id, removed_by | 1.10 |

### References

- [Source: docs/planning/prd.md#Administration-&-Configuration] — FR104 (usage analytics), FR108 (audit logs)
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.12: Usage Analytics & Audit Logs (Basic)
- [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix] — Admin-only access to analytics and audit
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Tenant-scoped audit_logs table
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Immutable audit trails, daily audit scanning
- [Source: docs/epics/epics.md#Story-1.12] — AC source: metrics dashboard, audit log page, filtering, export
- [Source: docs/planning/ux-design-specification.md#MetricCard] — MetricCard component pattern for dashboard
- [Source: docs/stories/1-2-organization-creation-setup.md] — AC8: audit trail pattern, tenant context
- [Source: docs/stories/1-9-project-creation-configuration.md] — AC8: audit logging pattern (project CRUD)
- [Source: docs/stories/1-10-project-team-assignment.md] — AC8: audit logging pattern (member ops)

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-18 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-12-usage-analytics-audit-logs-basic.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
