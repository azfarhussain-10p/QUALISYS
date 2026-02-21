# Story 1.9: Project Creation & Configuration

Status: ready-for-dev

## Story

As an Owner/Admin,
I want to create test projects and configure their settings,
so that I can organize testing efforts within my organization.

## Requirements Context

This is the **ninth story** in Epic 1 (Foundation & Administration). It establishes the project entity — the primary container for all test artifacts, agent executions, test runs, and integrations in subsequent epics. Projects live within tenant schemas (multi-tenant isolation). This story creates and configures projects; Story 1.10 adds team assignment, and Story 1.11 handles archive/delete/list operations.

**FRs Covered:**
- FR11 — Users can create new test projects within their organization
- FR12 — Users can configure project settings (name, description, app URL, repo link)

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model [Source: docs/architecture/architecture.md#ADR-001]
- Projects table: `{tenant_schema}.projects` — already provisioned by Story 0.21 (init-local-db.sql) and Story 0.4 (schema provisioning) with base columns
- Multi-tenancy: All project operations scoped to tenant via ContextVar middleware (Story 1.2) [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- RBAC: Only Owner/Admin can create projects [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix]
- RLS: Row-level security policies enforce tenant isolation on projects table [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Security: Parameterized queries ONLY; TLS 1.3 in transit [Source: docs/architecture/architecture.md#Security-Threat-Model]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`
- Story 1.2 (Organization Creation & Setup) — tenant schema provisioning, ContextVar middleware, RBAC decorators, `public.tenants` registry
- Story 1.5 (Login & Session Management) — JWT auth middleware, tenant context in JWT

## Acceptance Criteria

1. **AC1: Create Project Form** — "Create Project" page accessible from projects list page or dashboard via "New Project" button (shadcn/ui Button). Form fields: project name (required, 3-100 characters), description (optional, max 2000 characters), application URL (optional, validated URL format — the target application being tested), GitHub repository URL (optional, validated GitHub URL format `https://github.com/{owner}/{repo}`). Only Owner/Admin role can access this form (RBAC enforced — other roles see the button disabled or hidden).

2. **AC2: Project Record Creation** — On form submission, calls `POST /api/v1/projects`. Creates record in `{tenant_schema}.projects` with: `id` (UUID v4), `name` (varchar 255), `slug` (auto-generated from name, lowercase alphanumeric + hyphens, unique within tenant), `description` (text), `app_url` (varchar 500, nullable), `github_repo_url` (varchar 500, nullable), `status` (varchar 20, default 'active'), `settings` (JSONB, default `{}`), `created_by` (UUID FK to public.users), `tenant_id` (UUID, set from context), `is_active` (boolean, default true), `created_at`, `updated_at`. Slug uniqueness enforced within tenant (unique index on `(tenant_id, slug)` or schema-level unique on `slug`). Returns created project with HTTP 201.

3. **AC3: Project Settings Page** — Project settings page (`/projects/{project_slug}/settings`) accessible to Owner/Admin. Displays and allows editing: project name (with slug update confirmation), description, application URL, GitHub repository URL. Settings saved via `PATCH /api/v1/projects/{project_id}`. Changes to name trigger slug regeneration with confirmation dialog ("Changing project name will update the project URL").

4. **AC4: Project Settings — Advanced** — Advanced settings section (expandable/collapsible) includes: default test environment (dropdown: development, staging, production, custom), default browser for automated tests (dropdown: chromium, firefox, webkit — used by Epic 4), project tags (freeform tags for filtering/grouping, max 10 tags, max 50 chars each). Settings stored in `projects.settings` JSONB column. These settings provide defaults that can be overridden per test run.

5. **AC5: Creator Assignment** — User who creates the project is recorded in `created_by` field. Creator appears in project details. Creator does NOT automatically get a separate project-level role — they use their org-level role (Owner/Admin). Project team assignment handled in Story 1.10.

6. **AC6: Duplicate Project Prevention** — System rejects project creation if slug already exists within the tenant. Error message: "A project with this name already exists. Please choose a different name." Slug auto-generation: lowercase, replace spaces/special chars with hyphens, collapse consecutive hyphens, strip leading/trailing hyphens. On collision: append incrementing suffix (`my-project`, `my-project-1`, `my-project-2`).

7. **AC7: Validation & Error Handling** — All inputs validated server-side: name (required, 3-100 chars, no leading/trailing whitespace), description (max 2000 chars), app_url (valid URL format if provided), github_repo_url (valid GitHub URL format if provided). Validation errors returned as HTTP 400 with structured JSON: `{ "error": { "code": "VALIDATION_ERROR", "message": string, "details": { field: [errors] } } }`. All API responses follow consistent error format established in Story 1.1.

8. **AC8: Rate Limiting & Audit** — Project creation rate-limited to 10 per organization per hour (Redis-backed). Project settings update rate-limited to 30 per project per hour. All project actions logged to audit trail: project created (name, slug, created_by), settings updated (changed fields with old/new values). Audit entries include user_id, IP, user_agent, timestamp.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema — Project Table Enhancement** (AC: #2, #4)
  - [ ] 1.1 Create Alembic migration to add columns to `{tenant_schema}.projects`: `slug` (varchar 100), `app_url` (varchar 500, nullable), `github_repo_url` (varchar 500, nullable), `status` (varchar 20, default 'active'), `created_by` (UUID, nullable FK to public.users)
  - [ ] 1.2 Create unique index on `slug` within tenant schema (since each tenant has its own schema, slug uniqueness is per-tenant automatically)
  - [ ] 1.3 Backfill existing dev seed projects with generated slugs
  - [ ] 1.4 Write migration rollback script

- [ ] **Task 2: Project Service** (AC: #2, #3, #5, #6)
  - [ ] 2.1 Create `ProjectService` class: `create_project()`, `get_project()`, `update_project()`, `generate_slug()`
  - [ ] 2.2 Implement `create_project()`: validate inputs, generate slug (with collision handling), create record in tenant schema, set created_by from auth context
  - [ ] 2.3 Implement `get_project()`: retrieve by ID or slug within tenant context
  - [ ] 2.4 Implement `update_project()`: validate changes, update record, regenerate slug if name changed (with uniqueness check)
  - [ ] 2.5 Implement `generate_slug()`: lowercase, replace non-alphanumeric with hyphens, collapse consecutive, strip edges, append suffix on collision

- [ ] **Task 3: FastAPI Endpoints** (AC: #1, #2, #3, #7, #8)
  - [ ] 3.1 Create `POST /api/v1/projects` — create project (Owner/Admin only), returns 201
  - [ ] 3.2 Create `GET /api/v1/projects/{project_id}` — get project details (all roles with project access)
  - [ ] 3.3 Create `PATCH /api/v1/projects/{project_id}` — update project settings (Owner/Admin only)
  - [ ] 3.4 Create `GET /api/v1/projects/{project_id}/settings` — get project settings including JSONB advanced settings
  - [ ] 3.5 RBAC enforcement: `@require_role(['owner', 'admin'])` on create/update endpoints
  - [ ] 3.6 Rate limiting: 10 creates/org/hour, 30 updates/project/hour
  - [ ] 3.7 Audit log all project operations

- [ ] **Task 4: React UI — Create Project** (AC: #1, #6, #7)
  - [ ] 4.1 Create "New Project" button on projects list/dashboard (visible only to Owner/Admin)
  - [ ] 4.2 Create project form page or modal: name input, description textarea, app URL input, GitHub repo URL input
  - [ ] 4.3 Client-side validation: name (required, 3-100 chars), URL formats, GitHub URL pattern
  - [ ] 4.4 Success: redirect to new project dashboard with success toast
  - [ ] 4.5 Error handling: duplicate name, validation errors, rate limiting

- [ ] **Task 5: React UI — Project Settings** (AC: #3, #4)
  - [ ] 5.1 Create project settings page (`/projects/{slug}/settings`) with Owner/Admin access
  - [ ] 5.2 General section: editable name, description, app URL, GitHub repo URL
  - [ ] 5.3 Advanced section (collapsible): default environment dropdown, default browser dropdown, project tags input
  - [ ] 5.4 Name change confirmation dialog ("Changing name will update project URL")
  - [ ] 5.5 "Save Changes" button with validation and success/error feedback

- [ ] **Task 6: Testing** (AC: all)
  - [ ] 6.1 Unit tests: slug generation (basic, special chars, collision handling), input validation (name, URL formats)
  - [ ] 6.2 Integration tests: `POST /api/v1/projects` — valid creation, duplicate slug, missing required fields, RBAC (non-admin rejected)
  - [ ] 6.3 Integration tests: `GET /api/v1/projects/{id}` — existing project, non-existent project, cross-tenant isolation (cannot access other tenant's project)
  - [ ] 6.4 Integration tests: `PATCH /api/v1/projects/{id}` — update name (slug regenerated), update settings JSONB, RBAC enforcement
  - [ ] 6.5 Integration tests: rate limiting — 11th creation within hour returns 429
  - [ ] 6.6 Integration tests: tenant isolation — project created in tenant A not visible in tenant B (RLS enforced)
  - [ ] 6.7 Security tests: SQL injection prevention, XSS in project name/description, RBAC bypass attempts
  - [ ] 6.8 Frontend tests: create form validation, settings page, advanced settings, name change confirmation dialog

- [ ] **Task 7: Security Review** (AC: #2, #7, #8)
  - [ ] 7.1 Verify all queries use parameterized statements (no dynamic SQL with user input)
  - [ ] 7.2 Verify tenant isolation: projects scoped to tenant schema via ContextVar + RLS
  - [ ] 7.3 Verify RBAC: only Owner/Admin can create/update projects
  - [ ] 7.4 Verify slug generation cannot be exploited (no path traversal, no SQL injection via slug)
  - [ ] 7.5 Verify URL inputs sanitized (no JavaScript URLs, no XSS payloads in stored URLs)
  - [ ] 7.6 Verify rate limiting prevents abuse

## Dev Notes

### Architecture Patterns

- **Tenant-scoped projects:** Projects live in `{tenant_schema}.projects`, not in the public schema. All CRUD operations go through tenant context middleware (Story 1.2) which sets the PostgreSQL search_path. RLS policies provide defense-in-depth.
- **Existing projects table:** The `projects` table already exists in tenant schemas (created by Story 0.21 init-local-db.sql and Story 0.4 schema provisioning). This story adds new columns (`slug`, `app_url`, `github_repo_url`, `status`, `created_by`) via Alembic migration. The base columns (`id`, `name`, `description`, `organization_id`, `tenant_id`, `settings`, `is_active`, `created_at`, `updated_at`) already exist.
- **Slug pattern:** Same pattern as organization slug (Story 1.2). Used in URLs: `/projects/{slug}`. Unique within tenant schema.
- **JSONB settings:** Project-level defaults (environment, browser, tags) stored in `settings` JSONB column. Allows flexible extension without schema changes. Pattern: `{ "default_environment": "staging", "default_browser": "chromium", "tags": ["smoke", "regression"] }`.
- **RBAC enforcement:** Only Owner/Admin can create/update projects. Use `@require_role()` decorator from Story 1.2. Other roles can view projects (read access for all authenticated org members).
- **No project-level roles:** RBAC is organization-level (6 roles). Project team assignment (Story 1.10) maps org members to projects but doesn't create project-specific roles. This simplifies the permission model.

### Project Structure Notes

- Project service: `src/services/project_service.py`
- API routes: `src/api/v1/projects/` (create, get, update, settings)
- Frontend: `src/pages/projects/` (create form, settings page)
- Reuse: slug generation from Story 1.2, RBAC decorators from Story 1.2, tenant context middleware from Story 1.2
- Existing schema: `scripts/init-local-db.sql` lines 57-69 (projects table base)
- Dev seed: `scripts/dev-seed.ts` lines 137-167 (seedProjects function)

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Tenant isolation critical: all tests must verify projects are scoped to tenant schema
- Use existing `test_tenant` and `tenant_connection` fixtures from conftest.py

### Learnings from Previous Story

**From Story 1-8-profile-notification-preferences (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.8's specification establishes:

- **Settings page framework** — Story 1.8 creates the `/settings/*` tabbed layout for user settings. This story creates a separate project settings page at `/projects/{slug}/settings` — different context (project vs user) but similar edit-form patterns.
- **Audit logging pattern** — Story 1.8 logs profile changes with old/new values. This story follows the same pattern for project settings changes.
- **Rate limiting pattern** — Story 1.8 rate-limits per-user operations. This story rate-limits per-org (creation) and per-project (updates).

[Source: docs/stories/1-8-profile-notification-preferences.md]

### References

- [Source: docs/planning/prd.md#Project-Management] — FR11 (create projects), FR12 (configure project settings)
- [Source: docs/planning/prd.md#Roles-&-Permissions] — Owner/Admin can create projects
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.9: Project Creation & Configuration, FR11/FR12
- [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix] — Create projects: Owner/Admin only
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Schema-per-tenant isolation, tenant_schema.projects
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — RLS policies, parameterized queries, audit trails
- [Source: docs/epics/epics.md#Story-1.9] — AC source: create form, project settings, creator assignment
- [Source: docs/stories/1-2-organization-creation-setup.md] — Slug generation pattern, RBAC decorators, tenant context middleware
- [Source: docs/stories/1-5-login-session-management.md] — JWT auth middleware, tenant_id in JWT claims
- [Source: scripts/init-local-db.sql] — Existing projects table schema in tenant schemas
- [Source: scripts/dev-seed.ts] — seedProjects function, existing project seed data

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-17 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-9-project-creation-configuration.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
