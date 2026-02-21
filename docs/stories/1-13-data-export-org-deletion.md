# Story 1.13: Data Export & Org Deletion

Status: ready-for-dev

## Story

As an Admin,
I want to export org data or delete organization,
so that I can migrate or close my account.

## Requirements Context

This is the **thirteenth and final story** in Epic 1 (Foundation & Administration). It provides GDPR-compliant data export (full organization data as JSON in ZIP) and organization deletion (complete tenant wipe). These are destructive, irreversible operations that require the highest confirmation barriers. Data export generates a background job with email notification; org deletion queues a background job that drops the entire tenant schema.

**FRs Covered:**
- FR106 — Admins can export all organization data for backup or migration
- FR107 — Admins can delete organization and all associated data

**Related FRs (context):**
- FR105 — Admins can configure data retention policies (established in Story 1.2 — `data_retention_days` on tenants table)

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model [Source: docs/architecture/architecture.md#ADR-001]
- Multi-tenancy: Org deletion = DROP SCHEMA `tenant_{slug}` CASCADE + remove public registry entries [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- GDPR: Data export (JSON), right to be forgotten (complete deletion within 30 days) [Source: docs/planning/prd.md#Data-Privacy]
- Security: 2FA verification required for org deletion (highest confirmation barrier) [Source: docs/epics/epics.md#Story-1.13]
- Object Storage: AWS S3 for export ZIP files (presigned download URLs, 30-day expiry) [Source: docs/architecture/architecture.md#Technology-Stack]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`
- Story 1.2 (Organization Creation & Setup) — tenant schema provisioning (reverse for deletion), `public.tenants` + `public.tenants_users` tables
- Story 1.3 (Team Member Invitation) — email notification pattern (SendGrid/SES), invitations table
- Story 1.5 (Login & Session Management) — JWT auth, session invalidation (logout all users on deletion)
- Story 1.7 (Two-Factor Authentication) — 2FA verification for deletion confirmation
- Story 1.10 (Project Team Assignment) — project_members table (included in export/deletion)
- Story 1.11 (Project Management) — hard-delete CASCADE pattern
- Story 1.12 (Usage Analytics & Audit Logs) — audit_logs table, AuditService (log export/deletion events)

## Acceptance Criteria

1. **AC1: Export Data Button & Settings** — Organization settings page shows "Export Data" section (Owner only — not Admin, only Owner). "Export All Data" button triggers a full organization data export. Export includes all tenant schema tables: organizations, projects, project_members, test_cases, test_executions, audit_logs, plus public schema data for this org (tenants, tenants_users, user profiles). Export format: JSON files per table, bundled in a ZIP archive. Estimated size shown before export (count of records per table).

2. **AC2: Background Export Job** — On export request: `POST /api/v1/orgs/{org_id}/export` creates a background job. Returns HTTP 202 with `{ job_id, status: 'processing', estimated_duration }`. Export runs asynchronously — queries all tenant schema tables, serializes to JSON, generates ZIP, uploads to S3 at `exports/{tenant_id}/{job_id}/{timestamp}.zip`. S3 object set to auto-expire in 30 days. Job status queryable via `GET /api/v1/orgs/{org_id}/export/{job_id}` — returns `{ status: 'processing'|'completed'|'failed', progress_percent, download_url?, error? }`. On completion: email sent to requesting admin with presigned S3 download link (24-hour URL expiry). Rate-limited: 1 export per organization per 24 hours.

3. **AC3: Delete Organization — Confirmation** — "Delete Organization" button in org settings (Owner only — highest privilege). Multi-step confirmation:
   - Step 1: Warning dialog: "Permanently delete {org_name}? This will delete ALL organization data including projects, test cases, test results, and team members. This action CANNOT be undone."
   - Step 2: Type exact organization name to proceed (case-sensitive match)
   - Step 3: 2FA verification — enter TOTP code (if 2FA enabled) or re-enter password (if 2FA not enabled)
   - On all confirmations passed: `POST /api/v1/orgs/{org_id}/delete` with `{ org_name_confirmation, totp_code_or_password }`

4. **AC4: Background Deletion Job** — On confirmed deletion request: creates background job. Deletion sequence (ordered, transactional where possible):
   1. Log `org.deletion_requested` audit entry (BEFORE any data deleted — includes org name, member count, requesting user)
   2. Send notification email to ALL org members: "Organization {org_name} has been deleted by {admin_name}. You will no longer have access."
   3. Invalidate ALL sessions for all org members (via AuthService — clear Redis sessions for all users in this org)
   4. Delete `public.tenants_users` rows for this tenant_id
   5. Delete S3 objects: org logo, any export files, any stored artifacts
   6. Execute `DROP SCHEMA tenant_{slug} CASCADE` — atomically removes ALL tenant data (projects, test_cases, test_executions, project_members, audit_logs, etc.)
   7. Delete `public.tenants` row
   8. Update `public.users.default_tenant_id` to NULL for affected users (users may belong to other orgs)
   Returns HTTP 202 with `{ job_id, status: 'processing' }`. Status queryable. Deletion completes within minutes for typical orgs.

5. **AC5: Export Download** — Export download page (`/settings/exports`) shows export history: date requested, status (processing/completed/failed), file size, download link (if completed and not expired). Download via presigned S3 URL (24-hour expiry, regenerable while S3 object exists — 30 days). Multiple past exports shown (up to 5, older auto-cleaned by S3 lifecycle). Download requires authentication (Owner only).

6. **AC6: User Impact on Org Deletion** — Users who belong to ONLY this organization: their account remains in `public.users` but they have no active organization (show "No Organization" state on next login, prompt to create new org or accept invitations). Users who belong to MULTIPLE organizations: their `default_tenant_id` updated to another org they belong to, seamless experience continues. No user accounts are deleted — only org membership removed. User data in `public.users` (email, name, avatar, auth credentials) preserved for re-use.

7. **AC7: Validation & Error Handling** — Export when export already in progress: returns 409 "Export already in progress". Export rate limit exceeded: returns 429. Delete with wrong org name: returns 400 "Organization name does not match". Delete with invalid 2FA/password: returns 403 "Verification failed". Delete non-existent org: returns 404. Delete when not Owner: returns 403 (Admin is NOT sufficient — Owner only). All API responses follow consistent error format from Story 1.1.

8. **AC8: Rate Limiting & Audit** — Export: 1 per org per 24 hours. Delete: no rate limit needed (irreversible, high confirmation barrier). Audit: `org.export_requested` (actor, timestamp), `org.export_completed` (file_size, s3_path), `org.export_failed` (error), `org.deletion_requested` (actor, org_name, member_count), `org.deleted` (org_name, slug, data_purged). Deletion audit entries stored in a SEPARATE location (since tenant schema is dropped) — log to application logs or a `public.deletion_audit` table.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema** (AC: #2, #4, #8)
  - [ ] 1.1 Create Alembic migration for `public.export_jobs` table: `id` (UUID PK), `tenant_id` (UUID FK→tenants), `requested_by` (UUID FK→users), `status` (VARCHAR 20: 'processing', 'completed', 'failed'), `progress_percent` (INTEGER DEFAULT 0), `file_size_bytes` (BIGINT, nullable), `s3_key` (VARCHAR 500, nullable), `error_message` (TEXT, nullable), `created_at` (TIMESTAMPTZ), `completed_at` (TIMESTAMPTZ, nullable)
  - [ ] 1.2 Create `public.deletion_audit` table: `id` (UUID PK), `tenant_id` (UUID), `org_name` (VARCHAR 255), `org_slug` (VARCHAR 100), `deleted_by` (UUID FK→users), `member_count` (INTEGER), `details` (JSONB), `created_at` (TIMESTAMPTZ) — preserves deletion records after schema drop
  - [ ] 1.3 Create indexes on export_jobs: `(tenant_id, created_at DESC)`
  - [ ] 1.4 Write migration rollback script

- [ ] **Task 2: Export Service** (AC: #1, #2, #5)
  - [ ] 2.1 Create `ExportService` class: `request_export()`, `get_export_status()`, `generate_export()`, `get_download_url()`
  - [ ] 2.2 Implement `request_export()`: create export_jobs record, launch background task
  - [ ] 2.3 Implement `generate_export()`: query all tenant schema tables (organizations, projects, project_members, test_cases, test_executions, audit_logs), query public schema data (tenants, tenants_users filtered by tenant_id), serialize each table to JSON, bundle into ZIP, upload to S3 (`exports/{tenant_id}/{job_id}/{timestamp}.zip`), set 30-day S3 lifecycle expiry, update export_jobs record
  - [ ] 2.4 Implement `get_export_status()`: return job status, progress, download URL if completed
  - [ ] 2.5 Implement `get_download_url()`: generate presigned S3 download URL (24-hour expiry)
  - [ ] 2.6 Send completion email with download link via SendGrid/SES

- [ ] **Task 3: Deletion Service** (AC: #3, #4, #6)
  - [ ] 3.1 Create `OrgDeletionService` class: `request_deletion()`, `verify_deletion()`, `execute_deletion()`, `get_deletion_status()`
  - [ ] 3.2 Implement `request_deletion()`: validate org name match, verify 2FA/password, create deletion job
  - [ ] 3.3 Implement `execute_deletion()`: ordered deletion sequence — audit log → notify members → invalidate sessions → delete tenants_users → delete S3 objects → DROP SCHEMA CASCADE → delete tenants row → update users.default_tenant_id
  - [ ] 3.4 Handle partial failures: if deletion fails midway, mark job as 'failed', preserve state for retry, alert admin
  - [ ] 3.5 Log deletion records to `public.deletion_audit` (survives schema drop)

- [ ] **Task 4: FastAPI Endpoints** (AC: #1, #2, #3, #5, #7, #8)
  - [ ] 4.1 Create `POST /api/v1/orgs/{org_id}/export` — request data export (Owner only), returns 202
  - [ ] 4.2 Create `GET /api/v1/orgs/{org_id}/export/{job_id}` — check export status
  - [ ] 4.3 Create `GET /api/v1/orgs/{org_id}/export/{job_id}/download` — redirect to presigned S3 URL
  - [ ] 4.4 Create `GET /api/v1/orgs/{org_id}/exports` — list export history (up to 5)
  - [ ] 4.5 Create `POST /api/v1/orgs/{org_id}/delete` — request org deletion (Owner only, requires org_name_confirmation + totp_code or password)
  - [ ] 4.6 Create `GET /api/v1/orgs/{org_id}/deletion-status` — check deletion progress
  - [ ] 4.7 RBAC enforcement: `@require_role(['owner'])` on all export/delete endpoints (Owner only, NOT Admin)
  - [ ] 4.8 Rate limiting: 1 export/org/24h
  - [ ] 4.9 Audit log all operations via AuditService

- [ ] **Task 5: React UI — Data Export** (AC: #1, #2, #5)
  - [ ] 5.1 Add "Data Export" section to org settings page
  - [ ] 5.2 Record count preview before export (table name + row count)
  - [ ] 5.3 "Export All Data" button with confirmation dialog
  - [ ] 5.4 Export progress indicator (polling job status)
  - [ ] 5.5 Export history list with download links
  - [ ] 5.6 Success toast + email notification message

- [ ] **Task 6: React UI — Delete Organization** (AC: #3, #4, #6)
  - [ ] 6.1 Add "Danger Zone" section at bottom of org settings (red border, Owner only)
  - [ ] 6.2 "Delete Organization" button
  - [ ] 6.3 Multi-step confirmation dialog: warning → type org name → 2FA/password verification
  - [ ] 6.4 Delete button disabled until all confirmations passed
  - [ ] 6.5 Deletion progress page (or redirect to "Organization deleted" page)
  - [ ] 6.6 Post-deletion state: redirect to "No Organization" page or org selector

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: export serialization (JSON format per table), ZIP generation, S3 upload mock
  - [ ] 7.2 Unit tests: deletion sequence ordering, partial failure handling
  - [ ] 7.3 Integration tests: `POST /orgs/{id}/export` — valid export, rate limiting (1/24h), RBAC (non-Owner 403)
  - [ ] 7.4 Integration tests: export status polling, download URL generation
  - [ ] 7.5 Integration tests: `POST /orgs/{id}/delete` — valid deletion (org name match + 2FA), wrong name (400), wrong 2FA (403), RBAC (Admin 403, Owner only)
  - [ ] 7.6 Integration tests: deletion cascade — verify tenant schema dropped, tenants_users removed, tenants removed
  - [ ] 7.7 Integration tests: user impact — users in multiple orgs retain access, single-org users show no-org state
  - [ ] 7.8 Integration tests: session invalidation — all org members logged out after deletion
  - [ ] 7.9 Integration tests: tenant isolation — deletion of org A does not affect org B
  - [ ] 7.10 Integration tests: deletion_audit preserved after schema drop
  - [ ] 7.11 Security tests: SQL injection in schema name (DROP SCHEMA validation), RBAC bypass, cross-tenant
  - [ ] 7.12 Frontend tests: export flow, delete multi-step confirmation, 2FA input, progress indicators

- [ ] **Task 8: Security Review** (AC: #3, #4, #7, #8)
  - [ ] 8.1 Verify DROP SCHEMA uses validated schema name (not user input — lookup from tenants table)
  - [ ] 8.2 Verify 2FA/password verification before deletion (cannot be bypassed)
  - [ ] 8.3 Verify RBAC: Owner only (not Admin) for export and delete
  - [ ] 8.4 Verify presigned S3 URLs expire (24h for download, 30d for object)
  - [ ] 8.5 Verify export ZIP does not contain cross-tenant data
  - [ ] 8.6 Verify all org member sessions invalidated on deletion
  - [ ] 8.7 Verify deletion audit preserved in public schema (survives DROP SCHEMA)
  - [ ] 8.8 Verify no PII leakage in export error messages

## Dev Notes

### Architecture Patterns

- **Schema-level deletion:** `DROP SCHEMA tenant_{slug} CASCADE` is the atomic operation that removes ALL tenant data. This is the power of schema-per-tenant — deletion is a single DDL statement. The schema name MUST be looked up from `public.tenants.schema_name`, never constructed from user input.
- **Background jobs:** Both export and deletion are long-running operations. Use FastAPI BackgroundTasks or a task queue (Celery/ARQ). Job status tracked in `public.export_jobs` table. Frontend polls for status updates.
- **Deletion audit preservation:** Since `DROP SCHEMA CASCADE` deletes the tenant's audit_logs table, deletion events are recorded in `public.deletion_audit` — a public schema table that survives the schema drop. This ensures GDPR compliance (proof of deletion).
- **Export format:** One JSON file per table, named `{table_name}.json`. Each file contains an array of records with all columns. ZIP archive named `{org_slug}-export-{timestamp}.zip`. S3 path: `exports/{tenant_id}/{job_id}/{filename}`.
- **Owner-only restriction:** Export and deletion are restricted to Owner role (not Admin). This is the highest privilege level — only the person who created the org (or was assigned Owner) can perform these irreversible operations.
- **2FA for deletion:** Follows Story 1.7 TOTP verification pattern. If user has 2FA enabled, require TOTP code. If not, require password re-entry. This provides the highest confirmation barrier before irreversible action.
- **User account preservation:** Org deletion removes org membership but NOT user accounts. Users can still log in and create/join other organizations. This supports multi-org users and account portability.

### Project Structure Notes

- Export service: `src/services/export_service.py`
- Deletion service: `src/services/org_deletion_service.py`
- API routes: `src/api/v1/orgs/export.py`, `src/api/v1/orgs/delete.py`
- Frontend: `src/pages/settings/organization/DataExport.tsx`, `src/pages/settings/organization/DeleteOrganization.tsx`
- Reuse: S3 presigned URL pattern from Story 1.2 (logo upload), email service from Story 1.3, AuthService.logout_all() from Story 1.5, MFA verification from Story 1.7, AuditService from Story 1.12
- New public tables: `public.export_jobs`, `public.deletion_audit`

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- S3 operations mocked in tests (verify upload/download URL generation)
- Schema DROP tested in isolated test database (verify cascade and cleanup)
- Multi-org user scenario: test user belonging to 2 orgs, delete 1, verify other unaffected
- Use existing `test_tenant` and `tenant_connection` fixtures from conftest.py

### Learnings from Previous Story

**From Story 1-12-usage-analytics-audit-logs-basic (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.12's specification establishes:

- **AuditService** — `log_action()` with non-blocking insertion. This story uses AuditService for export/deletion events. Special case: deletion audit logged to `public.deletion_audit` since tenant schema will be dropped.
- **Audit action catalog** — Story 1.12 defines 21 actions from Stories 1.1-1.11. This story adds: `org.export_requested`, `org.export_completed`, `org.export_failed`, `org.deletion_requested`, `org.deleted`.
- **INSERT-ONLY audit_logs** — Immutable audit trail in tenant schema. On org deletion, these are lost with DROP SCHEMA CASCADE — hence the `public.deletion_audit` table.

[Source: docs/stories/1-12-usage-analytics-audit-logs-basic.md]

### References

- [Source: docs/planning/prd.md#Administration-&-Configuration] — FR106 (data export), FR107 (org deletion), FR105 (data retention)
- [Source: docs/planning/prd.md#Data-Privacy] — GDPR compliance, data export JSON/CSV, right to be forgotten, 30-day deletion
- [Source: docs/planning/prd.md#NFR-INT2] — Export formats: JSON, CSV, PDF; bulk export for migration
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.13: Data Export & Org Deletion, FR106/FR107
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Schema-per-tenant, DROP SCHEMA CASCADE for deletion
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Audit trails, compliance, GDPR
- [Source: docs/architecture/architecture.md#Technology-Stack] — AWS S3 for object storage (export files)
- [Source: docs/epics/epics.md#Story-1.13] — AC source: export ZIP, background job, 2FA deletion, member notification
- [Source: docs/stories/1-2-organization-creation-setup.md] — Tenant schema provisioning (reverse for deletion), public.tenants table
- [Source: docs/stories/1-5-login-session-management.md] — AuthService session invalidation (logout all org members)
- [Source: docs/stories/1-7-two-factor-authentication-totp.md] — 2FA verification for deletion confirmation
- [Source: docs/stories/1-11-project-management-archive-delete-list.md] — Hard-delete CASCADE pattern
- [Source: docs/stories/1-12-usage-analytics-audit-logs-basic.md] — AuditService, audit_logs table, action catalog
- [Source: scripts/init-local-db.sql] — All tenant schema tables (inventory for export)

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-18 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |
| 2026-02-20 | Context regenerated (v2) after tech spec completion — endpoint paths, schemas, deletion sequence corrected. Status: drafted → ready-for-dev. | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-13-data-export-org-deletion.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
