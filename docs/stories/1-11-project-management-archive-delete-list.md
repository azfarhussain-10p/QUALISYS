# Story 1.11: Project Management (Archive, Delete, List)

Status: ready-for-dev

## Story

As an Admin,
I want to archive or delete projects and view project list,
so that I can manage projects over time.

## Requirements Context

This is the **eleventh story** in Epic 1 (Foundation & Administration). It completes the project lifecycle by adding archive (soft-delete), hard-delete, and a comprehensive project list view. Projects were created in Story 1.9 and team-assigned in Story 1.10. This story provides the management operations to maintain projects over time — archiving inactive ones, permanently deleting unwanted ones, and listing all projects with status filtering.

**FRs Covered:**
- FR14 — Users can archive or delete projects
- FR15 — Users can view list of all projects with status and health indicators

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model [Source: docs/architecture/architecture.md#ADR-001]
- Multi-tenancy: All project operations scoped to tenant via ContextVar middleware (Story 1.2) [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- RBAC: Only Owner/Admin can archive or delete projects; all authenticated roles can view project list (filtered by membership per Story 1.10) [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix]
- RLS: Row-level security policies enforce tenant isolation on projects table [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Existing `is_active` column: Projects table already has `is_active BOOLEAN DEFAULT true` — used for archive (soft-delete) [Source: scripts/init-local-db.sql]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`
- Story 1.2 (Organization Creation & Setup) — tenant context middleware, RBAC decorators
- Story 1.5 (Login & Session Management) — JWT auth middleware
- Story 1.9 (Project Creation & Configuration) — projects table with slug, status, settings
- Story 1.10 (Project Team Assignment) — project_members table, `check_project_access` dependency, membership-filtered project list

## Acceptance Criteria

1. **AC1: Project List Page** — Projects list page (`/projects`) displays all projects the user has access to (filtered by project membership per Story 1.10 — all for Owner/Admin, assigned only for other roles). Table columns: project name (link to project dashboard), status badge (Active — green, Archived — gray), description (truncated), team size (member count from project_members), created date, actions dropdown. Searchable by project name (client-side filter or server-side search). Sortable by name, created date, status. Pagination: 20 projects per page with load-more or page navigation. Empty state: "No projects yet. Create your first project to get started." (with New Project button for Owner/Admin).

2. **AC2: Show Archived Toggle** — Project list defaults to showing only active projects (`is_active = true`). "Show Archived" toggle (checkbox or switch) reveals archived projects alongside active ones. Archived projects visually distinct (gray text/row, "Archived" badge). Alternatively, status filter dropdown: "Active" (default), "Archived", "All". Filter persisted in URL query parameter (`?status=active|archived|all`) for shareable links.

3. **AC3: Archive Project (Soft-Delete)** — Owner/Admin can archive a project via actions dropdown → "Archive Project". Confirmation dialog: "Archive {project_name}? The project will be hidden from the active list but all data will be retained. You can restore it later." On confirm: `POST /api/v1/projects/{project_id}/archive` sets `is_active = false` and `status = 'archived'`. Archived project hidden from default list, visible via "Show Archived" toggle. All project data retained (test cases, executions, members). Returns HTTP 200 with updated project.

4. **AC4: Restore Archived Project** — Owner/Admin can restore an archived project via actions dropdown → "Restore Project" (visible only on archived projects). `POST /api/v1/projects/{project_id}/restore` sets `is_active = true` and `status = 'active'`. Restored project reappears in active list. All data intact. Returns HTTP 200 with updated project.

5. **AC5: Delete Project (Hard-Delete)** — Owner/Admin can permanently delete a project via actions dropdown → "Delete Project". High-friction confirmation dialog: "Permanently delete {project_name}? This action cannot be undone. All project data including test cases, test executions, and team assignments will be permanently removed." User must type the exact project name to confirm (case-sensitive input match). On confirm: `DELETE /api/v1/projects/{project_id}` cascades to: project_members, test_cases, test_executions (all in tenant schema). Returns HTTP 204. Deleted project removed from all lists.

6. **AC6: Project Health Indicator (Placeholder)** — Each project in the list shows a health indicator column. For Epic 1, this is a placeholder: always shows "—" or a neutral gray dot. In Epic 2-4, this will be populated with test coverage percentage, pass rate, and last test run status. The column structure and component are created now for forward compatibility.

7. **AC7: Validation & Error Handling** — Cannot archive an already archived project (400: "Project is already archived"). Cannot restore an active project (400: "Project is not archived"). Cannot delete a non-existent project (404). Delete confirmation: project name must match exactly (client-side validation before API call). All API responses follow consistent error format from Story 1.1. RBAC: non-Admin attempting archive/restore/delete gets 403.

8. **AC8: Rate Limiting & Audit** — Archive/restore/delete operations rate-limited to 10 per organization per hour (Redis-backed). All operations logged to audit trail: project archived (project_id, project_name, archived_by), project restored (project_id, restored_by), project deleted (project_id, project_name, deleted_by — logged BEFORE deletion). Audit entries include user_id, IP, user_agent, timestamp.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema Updates** (AC: #3, #4, #5)
  - [ ] 1.1 Verify `is_active` column exists on `{tenant_schema}.projects` (already in init-local-db.sql)
  - [ ] 1.2 Verify `status` column added by Story 1.9 Alembic migration (varchar 20, default 'active')
  - [ ] 1.3 Create index on `(is_active, tenant_id)` for efficient active/archived filtering (if not exists)
  - [ ] 1.4 Verify CASCADE behavior: deleting project cascades to project_members (Story 1.10 FK), test_cases, test_executions
  - [ ] 1.5 Add ON DELETE CASCADE to project_members FK if not already set

- [ ] **Task 2: Project Service Extensions** (AC: #1, #2, #3, #4, #5)
  - [ ] 2.1 Extend `ProjectService` with: `list_projects()`, `archive_project()`, `restore_project()`, `delete_project()`
  - [ ] 2.2 Implement `list_projects()`: filtered by is_active (default true), searchable by name (ILIKE), sortable, paginated, includes member count (JOIN project_members GROUP BY), respects membership filter (Story 1.10 check_project_access)
  - [ ] 2.3 Implement `archive_project()`: set is_active=false, status='archived', updated_at=NOW()
  - [ ] 2.4 Implement `restore_project()`: set is_active=true, status='active', updated_at=NOW()
  - [ ] 2.5 Implement `delete_project()`: hard-delete with CASCADE (project_members, test_cases, test_executions). Log audit BEFORE deletion

- [ ] **Task 3: FastAPI Endpoints** (AC: #1, #2, #3, #4, #5, #7, #8)
  - [ ] 3.1 Update `GET /api/v1/projects` — list projects with query params: `status` (active|archived|all, default active), `search` (name filter), `sort` (name|created_at|status), `page`/`per_page` (pagination). Applies membership filter from Story 1.10
  - [ ] 3.2 Create `POST /api/v1/projects/{project_id}/archive` — archive project (Owner/Admin only), returns 200
  - [ ] 3.3 Create `POST /api/v1/projects/{project_id}/restore` — restore project (Owner/Admin only), returns 200
  - [ ] 3.4 Create `DELETE /api/v1/projects/{project_id}` — hard-delete project (Owner/Admin only), returns 204
  - [ ] 3.5 RBAC enforcement: `@require_role(['owner', 'admin'])` on archive/restore/delete
  - [ ] 3.6 Rate limiting: 10 archive/restore/delete operations per org per hour
  - [ ] 3.7 Audit log all operations (log delete BEFORE executing)

- [ ] **Task 4: React UI — Project List Page** (AC: #1, #2, #6)
  - [ ] 4.1 Create project list page (`/projects`) with table layout
  - [ ] 4.2 Table columns: name (link), status badge, health indicator (placeholder), description (truncated), team size, created date, actions dropdown
  - [ ] 4.3 Search input: filter by project name
  - [ ] 4.4 Status filter: Active (default) / Archived / All — persisted in URL query param
  - [ ] 4.5 Sort controls: name, created date, status
  - [ ] 4.6 Pagination: 20 per page with page navigation
  - [ ] 4.7 Empty state with New Project CTA (Owner/Admin only)
  - [ ] 4.8 Health indicator placeholder column (gray dot or "—")

- [ ] **Task 5: React UI — Archive, Restore, Delete** (AC: #3, #4, #5, #7)
  - [ ] 5.1 Actions dropdown per project row: View, Settings, Archive/Restore, Delete (Owner/Admin only)
  - [ ] 5.2 Archive confirmation dialog with project name and reassurance about data retention
  - [ ] 5.3 Restore action (visible on archived projects only) — no heavy confirmation needed
  - [ ] 5.4 Delete confirmation dialog: high-friction (red warning, type project name to confirm)
  - [ ] 5.5 Delete button disabled until typed name matches exactly
  - [ ] 5.6 Success/error toast notifications for all operations
  - [ ] 5.7 List auto-refreshes after archive/restore/delete

- [ ] **Task 6: Testing** (AC: all)
  - [ ] 6.1 Unit tests: list filtering (active/archived/all), search, sort, pagination logic
  - [ ] 6.2 Integration tests: `GET /api/v1/projects` — list with filters, membership filtering (non-Admin sees only assigned), pagination
  - [ ] 6.3 Integration tests: `POST /projects/{id}/archive` — valid archive, already archived (400), RBAC (non-admin 403)
  - [ ] 6.4 Integration tests: `POST /projects/{id}/restore` — valid restore, not archived (400), RBAC
  - [ ] 6.5 Integration tests: `DELETE /projects/{id}` — valid delete (cascade verified), non-existent (404), RBAC
  - [ ] 6.6 Integration tests: cascade on delete — project_members, test_cases, test_executions removed
  - [ ] 6.7 Integration tests: tenant isolation — project list, archive, delete scoped to tenant
  - [ ] 6.8 Integration tests: rate limiting — 11th operation returns 429
  - [ ] 6.9 Security tests: SQL injection prevention, RBAC bypass, cross-tenant access
  - [ ] 6.10 Frontend tests: project list table, search, filter, sort, pagination, archive/restore/delete dialogs, name confirmation input

- [ ] **Task 7: Security Review** (AC: #5, #7, #8)
  - [ ] 7.1 Verify all queries use parameterized statements
  - [ ] 7.2 Verify tenant isolation on all list/archive/delete operations
  - [ ] 7.3 Verify RBAC: only Owner/Admin can archive/restore/delete
  - [ ] 7.4 Verify delete confirmation cannot be bypassed (server validates, not just client)
  - [ ] 7.5 Verify audit logged BEFORE hard-delete (data available for audit entry)
  - [ ] 7.6 Verify rate limiting prevents mass deletion abuse

## Dev Notes

### Architecture Patterns

- **Soft-delete (Archive):** Uses existing `is_active` boolean column. Sets `is_active = false` and `status = 'archived'`. Data fully retained — test cases, executions, members all preserved. Restorable at any time. This is the preferred project lifecycle operation.
- **Hard-delete:** Permanent removal via SQL DELETE with CASCADE. High-friction confirmation (type project name). Cascades to: project_members (Story 1.10), test_cases, test_executions. Audit entry logged BEFORE deletion to preserve project_id and name.
- **Project list with membership filter:** Story 1.10 establishes `check_project_access` and membership-filtered project list. This story extends `GET /api/v1/projects` with search, sort, pagination, and status filter. Membership filtering remains: non-Admin sees only assigned projects.
- **Health indicator placeholder:** Column created in Epic 1 with placeholder value. Epic 2-4 stories will populate with real metrics (test coverage, pass rate, last run status). Component structure defined now for forward compatibility.
- **Cascade behavior:** `project_members` has FK to projects.id — needs ON DELETE CASCADE. `test_cases` and `test_executions` have `project_id` column but may not have FK constraint in current DDL — add FK with CASCADE or handle deletion explicitly in service.

### Project Structure Notes

- Project service extensions: `src/services/project_service.py` (add list, archive, restore, delete methods)
- API routes: `src/api/v1/projects/` (extend existing router with archive, restore, delete endpoints)
- Frontend: `src/pages/projects/ProjectList.tsx` (new page)
- Components: `src/components/projects/ProjectTable.tsx`, `src/components/projects/ArchiveDialog.tsx`, `src/components/projects/DeleteDialog.tsx`
- Reuse: `check_project_access` from Story 1.10, RBAC decorators from Story 1.2, project settings from Story 1.9

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Cascade tests critical: verify all related data removed on hard-delete
- Tenant isolation critical: verify list/archive/delete scoped to tenant
- Use existing `test_tenant` and `tenant_connection` fixtures from conftest.py

### Learnings from Previous Story

**From Story 1-10-project-team-assignment (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.10's specification establishes:

- **check_project_access dependency** — Reusable FastAPI dependency for project-scoped endpoints. This story uses it for archive/restore/delete endpoints.
- **Membership-filtered project list** — Story 1.10 modifies GET /projects to filter by membership. This story extends that endpoint with search, sort, pagination, and status filter.
- **project_members table** — FK to projects.id. Needs ON DELETE CASCADE for hard-delete.
- **Rate limiting pattern** — Story 1.10 rate-limits per project. This story rate-limits per org (archive/delete are org-level operations).

[Source: docs/stories/1-10-project-team-assignment.md]

### References

- [Source: docs/planning/prd.md#Project-Management] — FR14 (archive/delete projects), FR15 (project list with status/health)
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.11: Project Management, FR14/FR15
- [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix] — Delete/Archive: Owner/Admin only, View list: all roles (filtered)
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Schema-per-tenant isolation
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Audit trails, rate limiting, immutable audit records
- [Source: docs/epics/epics.md#Story-1.11] — AC source: project list, archive, delete, health indicator
- [Source: docs/stories/1-9-project-creation-configuration.md] — Projects table with is_active, status columns
- [Source: docs/stories/1-10-project-team-assignment.md] — check_project_access, project_members table, membership filtering
- [Source: scripts/init-local-db.sql] — Existing projects table with is_active column, CASCADE behavior

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-18 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-11-project-management-archive-delete-list.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
