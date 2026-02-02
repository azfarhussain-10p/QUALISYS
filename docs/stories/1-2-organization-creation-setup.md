# Story 1.2: Organization Creation & Setup

Status: ready-for-dev

## Story

As an Owner,
I want to create my organization and configure settings,
so that my team can collaborate on the QUALISYS platform.

## Requirements Context

This is the **second story** in Epic 1 (Foundation & Administration). It establishes the multi-tenant organizational boundary — the tenant schema, organization settings, and Owner/Admin role assignment. All subsequent stories (team invites 1.3, project creation 1.9, RBAC features) depend on organizations existing.

**FRs Covered:**
- FR2 — Users can create organizations and become the first Owner/Admin
- FR102 — Admins can configure organization-wide settings (name, logo, domain)
- FR105 — Admins can configure data retention policies for their organization

**Architecture Constraints:**
- Multi-tenancy: Schema-per-tenant PostgreSQL isolation (ADR-001) [Source: docs/architecture/architecture.md#ADR-001]
- `public.tenants` registry table for tenant lookup; tenant-specific schema for all org data
- Alembic migrations run per-tenant schema (scripted in deployment) [Source: docs/architecture/architecture.md#ADR-001]
- ContextVar-based DB connection routing to tenant schema [Source: docs/architecture/architecture.md#ADR-001]
- Schema naming convention: `tenant_{slug}` where slug is URL-safe org identifier
- Row-level security policies as defense-in-depth layer [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- Automated daily audit scanning for cross-tenant queries [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Object storage: AWS S3 for org logo uploads [Source: docs/architecture/architecture.md#Technology-Stack]
- Data retention: Configurable per tenant (30/90/180/365 days) [Source: docs/planning/prd.md#Data-Privacy]
- RBAC: 6 roles (Owner/Admin, PM/CSM, QA-Manual, QA-Automation, Dev, Viewer) [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix]
- Backend: Python 3.11+ / FastAPI
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui

**Dependency:** Story 1.1 (User Account Creation) — users must exist before creating organizations.

## Acceptance Criteria

1. **AC1: First-Time User Onboarding Prompt** — After email verification or Google OAuth signup, first-time users (no organization membership) are redirected to a "Create Your Organization" page. Page displays a form with: organization name (required, 3-100 chars), organization slug (auto-generated from name, editable, URL-safe, unique), logo upload (optional, max 2MB, PNG/JPG/SVG), and custom domain (optional, validated format). Skip option available: "Join an existing organization" link (for invited users who haven't accepted yet).

2. **AC2: Organization Database Record** — Organization record created in `public.tenants` table with: `id` (UUID v4), `name` (varchar 100), `slug` (varchar 50, unique, lowercase), `logo_url` (text, nullable), `custom_domain` (varchar 255, nullable), `data_retention_days` (integer, default 365), `plan` (varchar 50, default 'free'), `settings` (JSONB, default {}), `created_by` (UUID FK to public.users), `created_at` (timestamptz), `updated_at` (timestamptz). Slug validated: lowercase alphanumeric and hyphens only, no leading/trailing hyphens, unique across all tenants.

3. **AC3: Tenant Schema Provisioning** — On organization creation, system creates a new PostgreSQL schema named `tenant_{slug}`. Base migration tables applied to the new schema (initially: `org_members`, `audit_logs`). Schema creation wrapped in a database transaction — if migration fails, schema is dropped and user sees error with retry option. Schema provisioning runs asynchronously (user sees "Setting up your organization..." progress indicator).

4. **AC4: Owner/Admin Role Assignment** — Creating user automatically assigned `owner` role in `public.tenants_users` join table (fields: `tenant_id`, `user_id`, `role`, `joined_at`). User's default tenant set in `public.users.default_tenant_id`. After creation, user redirected to organization dashboard with Owner/Admin permissions active.

5. **AC5: Organization Settings Page** — Settings page accessible to Owner/Admin only (RBAC enforced). Displays and allows editing: organization name, slug (with uniqueness re-check), logo (upload/remove), custom domain, data retention policy dropdown (30/90/180/365 days). Settings saved via `PATCH /api/v1/orgs/{org_id}/settings`. Changes to slug trigger confirmation dialog ("Changing slug will update all URLs").

6. **AC6: Logo Upload** — Logo uploaded to S3 bucket under path `tenants/{tenant_id}/logo/{filename}`. Accepted formats: PNG, JPG, SVG. Max file size: 2MB. Image resized server-side to 256x256px thumbnail + original preserved. Pre-signed upload URL generated for direct browser-to-S3 upload (no backend proxy for large files). Logo URL stored in `public.tenants.logo_url`.

7. **AC7: Duplicate Organization Prevention** — System rejects organization creation if slug already exists (case-insensitive). Error message: "This organization URL is already taken. Please choose a different name." Slug auto-generation appends incrementing number if collision detected (e.g., `my-org`, `my-org-1`, `my-org-2`).

8. **AC8: Tenant Context Middleware** — FastAPI middleware that extracts tenant context from authenticated user's `default_tenant_id`. Sets PostgreSQL `search_path` to the tenant schema for the duration of the request. Tenant context stored in Python ContextVar (immutable per request). All subsequent database queries automatically scoped to tenant schema. Middleware validates tenant exists and user has membership.

9. **AC9: Security & Audit** — Organization creation logged in audit trail (actor, action, timestamp, tenant_id). Tenant schema name validated against SQL injection (alphanumeric + underscore only). Schema creation uses parameterized DDL (no string interpolation). Rate limit: 3 org creations per user per hour.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema — Tenants & Membership** (AC: #2, #4)
  - [ ] 1.1 Create Alembic migration for `public.tenants` table (id UUID PK, name, slug unique, logo_url, custom_domain, data_retention_days default 365, plan default 'free', settings JSONB, created_by FK, created_at, updated_at)
  - [ ] 1.2 Create unique index on `LOWER(slug)` for case-insensitive uniqueness
  - [ ] 1.3 Create Alembic migration for `public.tenants_users` join table (tenant_id FK, user_id FK, role varchar 30, joined_at timestamptz, PK on tenant_id + user_id)
  - [ ] 1.4 Add `default_tenant_id` column (UUID FK nullable) to `public.users` table via migration
  - [ ] 1.5 Create SQLAlchemy models: `Tenant`, `TenantUser`
  - [ ] 1.6 Write migration rollback scripts

- [ ] **Task 2: Tenant Schema Provisioning Service** (AC: #3)
  - [ ] 2.1 Create `TenantProvisioningService` that creates PostgreSQL schema `tenant_{slug}`
  - [ ] 2.2 Implement base migration runner for new tenant schemas (creates `org_members`, `audit_logs` tables)
  - [ ] 2.3 Wrap schema creation + migration in a transaction with rollback on failure
  - [ ] 2.4 Implement async provisioning with status tracking (pending → provisioning → ready → failed)
  - [ ] 2.5 Validate schema name against SQL injection: allow only `[a-z0-9_]` pattern

- [ ] **Task 3: Tenant Context Middleware** (AC: #8)
  - [ ] 3.1 Create FastAPI middleware that extracts `default_tenant_id` from authenticated user JWT
  - [ ] 3.2 Set PostgreSQL `search_path` to `tenant_{slug}` for current request using ContextVar
  - [ ] 3.3 Validate tenant exists in `public.tenants` and user has membership in `public.tenants_users`
  - [ ] 3.4 Return 403 if user has no membership in the requested tenant
  - [ ] 3.5 Ensure ContextVar is immutable per request (prevent tenant context switching mid-request)

- [ ] **Task 4: FastAPI Organization Endpoints** (AC: #1, #2, #4, #5, #7, #9)
  - [ ] 4.1 Create `POST /api/v1/orgs` endpoint — create organization (name, slug, logo_url, custom_domain)
  - [ ] 4.2 Implement slug auto-generation from name (slugify + collision detection with incrementing suffix)
  - [ ] 4.3 Implement Owner/Admin role assignment in `tenants_users` + update `users.default_tenant_id`
  - [ ] 4.4 Trigger async tenant schema provisioning after org record created
  - [ ] 4.5 Create `GET /api/v1/orgs/{org_id}/settings` endpoint (Owner/Admin only)
  - [ ] 4.6 Create `PATCH /api/v1/orgs/{org_id}/settings` endpoint (Owner/Admin only, validate slug uniqueness on change)
  - [ ] 4.7 Rate limit org creation: 3 per user per hour (Redis-backed)
  - [ ] 4.8 Audit log all org creation and settings changes

- [ ] **Task 5: Logo Upload** (AC: #6)
  - [ ] 5.1 Create `POST /api/v1/orgs/{org_id}/logo/presigned-url` endpoint — generates S3 pre-signed upload URL
  - [ ] 5.2 Validate file type (PNG, JPG, SVG) and size (max 2MB) before generating URL
  - [ ] 5.3 Create S3 bucket path structure: `tenants/{tenant_id}/logo/{filename}`
  - [ ] 5.4 Implement server-side image resize to 256x256 thumbnail (Pillow or Lambda trigger)
  - [ ] 5.5 Update `tenants.logo_url` after successful upload confirmation

- [ ] **Task 6: React Organization UI** (AC: #1, #5, #6)
  - [ ] 6.1 Create `/create-org` route with organization creation form (name, slug preview, logo upload, custom domain)
  - [ ] 6.2 Implement slug auto-preview (debounced, shows availability check)
  - [ ] 6.3 Implement logo drag-and-drop upload with preview and crop
  - [ ] 6.4 Create "Setting up your organization..." progress page with async status polling
  - [ ] 6.5 Create `/settings/organization` page for Owner/Admin (edit name, slug, logo, domain, retention)
  - [ ] 6.6 Implement data retention policy dropdown (30/90/180/365 days)
  - [ ] 6.7 First-time user detection: redirect to `/create-org` if no org membership

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: slug generation, slug validation, schema name sanitization, tenant context middleware
  - [ ] 7.2 Integration tests: `POST /api/v1/orgs` (happy path, duplicate slug, rate limit, invalid input)
  - [ ] 7.3 Integration tests: tenant schema provisioning (schema created, migration applied, rollback on failure)
  - [ ] 7.4 Integration tests: tenant context middleware (correct search_path, 403 on no membership, immutable context)
  - [ ] 7.5 Integration tests: org settings CRUD (Owner access, non-Owner denied, slug change validation)
  - [ ] 7.6 Integration tests: logo upload (pre-signed URL generation, file type validation, size limit)
  - [ ] 7.7 Security tests: SQL injection in slug/schema name rejected, cross-tenant access denied, RBAC enforced
  - [ ] 7.8 Frontend tests: create-org form, slug preview, logo upload, settings page

- [ ] **Task 8: Security Review** (AC: #9)
  - [ ] 8.1 Verify tenant schema name uses parameterized DDL (no string interpolation)
  - [ ] 8.2 Verify ContextVar prevents tenant context switching mid-request
  - [ ] 8.3 Verify RBAC check on all settings endpoints (Owner/Admin only)
  - [ ] 8.4 Verify audit logging captures all org creation and modification events
  - [ ] 8.5 Verify S3 bucket policy restricts access to tenant-scoped paths only

## Dev Notes

### Architecture Patterns

- **Multi-tenant provisioning flow:** User creates org → record in `public.tenants` → async schema provisioning → Owner role assigned → redirect to dashboard. If provisioning fails, org record remains with `status=failed`, user can retry.
- **Tenant context via ContextVar:** Python `contextvars.ContextVar` holds the current tenant slug. Set once per request in middleware, immutable afterward. SQLAlchemy session uses this to set `search_path`. This pattern prevents the RLS race condition identified in the architecture threat model.
- **Schema naming:** `tenant_{slug}` (e.g., `tenant_acme_corp`). Slug must be alphanumeric + hyphens for user-facing, converted to underscores for schema name. Max 50 chars to stay within PostgreSQL's 63-char identifier limit.
- **RBAC enforcement:** Story 1.2 introduces the `tenants_users` join table with `role` column. For this story, only `owner` role is assigned. Role-based endpoint protection (`@require_role('owner')` decorator) established here for use in all subsequent stories.
- **Logo upload pattern:** Pre-signed S3 URLs for direct browser upload avoids proxying large files through the API server. After upload, a callback confirms the file and triggers thumbnail generation.

### Project Structure Notes

- Tenant provisioning service: `src/services/tenant_provisioning.py`
- Tenant context middleware: `src/middleware/tenant_context.py`
- Organization API routes: `src/api/v1/orgs/`
- Tenant models: `src/models/tenant.py`
- RBAC decorators: `src/middleware/rbac.py`
- Base tenant migrations: `src/migrations/tenant_base/`
- Frontend pages: `src/pages/create-org/`, `src/pages/settings/organization/`
- Builds on conventions established in Story 1.1 (error handling, response format, test organization).

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Tenant provisioning tests need dedicated test schemas (cleaned up after each test run)
- Security tests for cross-tenant access are critical per architecture threat model

### References

- [Source: docs/planning/prd.md#User-Account-&-Access-Management] — FR2 (org creation)
- [Source: docs/planning/prd.md#Administration-&-Configuration] — FR102 (org settings), FR105 (data retention)
- [Source: docs/planning/prd.md#Multi-Tenancy-Architecture] — Schema isolation, tenant onboarding
- [Source: docs/planning/prd.md#Data-Privacy] — Data retention policies (30/90/180/365 days)
- [Source: docs/architecture/architecture.md#ADR-001] — Schema-per-tenant strategy, Alembic per-tenant migrations
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Data/performance/cost/failure isolation
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — RLS race condition prevention, cross-tenant audit
- [Source: docs/tech-specs/tech-spec-epic-1.md#Multi-Tenancy-Architecture] — Schema diagram, public tables
- [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix] — 6 roles, permission boundaries
- [Source: docs/epics/epics.md#Story-1.2] — Acceptance criteria source

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-01 | Story drafted from epics, PRD, tech spec, and architecture | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-2-organization-creation-setup.context.xml

### Agent Model Used

Claude Opus 4.5

### Debug Log References

### Completion Notes List

### File List
