# Story 1.10: Project Team Assignment

Status: ready-for-dev

## Story

As a PM,
I want to assign team members to projects with role-based access,
so that the right people can collaborate.

## Requirements Context

This is the **tenth story** in Epic 1 (Foundation & Administration). It establishes the project membership model — mapping organization users to specific projects. Projects (created in Story 1.9) need team assignment so that the right people see the right projects. Organization-level roles (6 roles from Story 1.2) govern what actions a member can take; this story controls *which projects* they can access. Story 1.11 handles project archive/delete/list operations.

**FRs Covered:**
- FR13 — Users can assign team members to projects with role-based access

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model [Source: docs/architecture/architecture.md#ADR-001]
- Multi-tenancy: All project operations scoped to tenant via ContextVar middleware (Story 1.2) [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- RBAC: Only Owner/Admin can manage project team membership [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix]
- RLS: Row-level security policies enforce tenant isolation on project_members table [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Security: Parameterized queries ONLY; TLS 1.3 in transit [Source: docs/architecture/architecture.md#Security-Threat-Model]
- No project-level roles: RBAC is organization-level (6 roles). Project membership controls *access* to a project, not *permissions* within it. Permissions come from the user's org-level role. [Source: docs/stories/1-9-project-creation-configuration.md#Dev-Notes]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`
- Story 1.2 (Organization Creation & Setup) — tenant schema provisioning, ContextVar middleware, RBAC decorators, `public.tenants` registry, org member roster
- Story 1.3 (Team Member Invitation) — email notification pattern (SendGrid/SES), invitation flow establishes org membership
- Story 1.5 (Login & Session Management) — JWT auth middleware, tenant context in JWT
- Story 1.9 (Project Creation & Configuration) — projects table, `created_by` field, project settings page framework

## Acceptance Criteria

1. **AC1: Team Members Tab** — Project settings page (`/projects/{project_slug}/settings`) shows a "Team Members" tab (in addition to General and Advanced from Story 1.9). Tab displays a table of current project members: avatar (or initials fallback), full name, email, organization role (Owner/Admin, PM/CSM, QA-Manual, QA-Automation, Dev, Viewer), date added, and a "Remove" action button. Owner/Admin sees all management controls; other assigned members see the list in read-only mode. If no members are assigned yet, show empty state: "No team members assigned. Add members to start collaborating."

2. **AC2: Add Member to Project** — "Add Member" button (visible to Owner/Admin only) opens a dropdown/dialog showing organization members who are NOT already assigned to this project. List shows: avatar, full name, email, org role. Searchable by name or email. Selecting a member calls `POST /api/v1/projects/{project_id}/members` with `{ "user_id": "<uuid>" }`. Member is added with their existing org-level role (no separate project role assignment needed). Returns HTTP 201 with the new membership record. Bulk add supported: Owner/Admin can select multiple members and add them in a single action.

3. **AC3: Project Access Enforcement** — Only users assigned to a project (via project_members) OR users with Owner/Admin org role can access project resources. Owner/Admin users have implicit access to ALL projects in the organization (they are not required to be in project_members). For other roles: if not in project_members, API returns 403 on project-specific endpoints. Project list (`GET /api/v1/projects`) returns only projects the user is a member of (plus all projects for Owner/Admin). This is enforced via a `check_project_access()` dependency/middleware that verifies membership before allowing project-scoped operations.

4. **AC4: Remove Member from Project** — Owner/Admin can remove a member from a project via "Remove" button next to each member row. Confirmation dialog: "Remove {name} from {project_name}? They will lose access to this project." Calls `DELETE /api/v1/projects/{project_id}/members/{user_id}`. Owner/Admin cannot be removed from a project (they have implicit access). Returns HTTP 204 on success. Removed user immediately loses access to project resources.

5. **AC5: Email Notification on Assignment** — When a member is added to a project, they receive an email notification: subject "You've been added to {project_name}", body includes project name, who added them, and a link to the project dashboard (`/projects/{slug}`). Email sent asynchronously (non-blocking). Uses the same email service pattern as Story 1.3 (team invitation). Email respects the user's notification preferences from Story 1.8 (email_team_changes toggle) — if disabled, no email sent. Security notifications bypass preference check (not applicable here).

6. **AC6: Project Creator Auto-Assignment** — When a project is created (Story 1.9), the creator is automatically added as a project member in the `project_members` table. This ensures the creator appears in the Team Members tab. Since creators are always Owner/Admin (only they can create projects), they also have implicit access, but the explicit membership record provides visibility and consistency.

7. **AC7: Validation & Error Handling** — Duplicate membership: adding a user already in the project returns HTTP 409 with `{ "error": { "code": "ALREADY_MEMBER", "message": "User is already a member of this project." } }`. User not in org: adding a user_id not in the organization returns HTTP 404. Project not found: returns HTTP 404. All API responses follow consistent error format established in Story 1.1. Validation: user_id must be valid UUID.

8. **AC8: Rate Limiting & Audit** — Member add/remove rate-limited to 30 operations per project per hour (Redis-backed). All membership actions logged to audit trail: member added (user_id, added_by, project_id), member removed (user_id, removed_by, project_id). Audit entries include user_id, IP, user_agent, timestamp.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema — Project Members Table** (AC: #1, #2, #3, #6)
  - [ ] 1.1 Create Alembic migration to add `{tenant_schema}.project_members` table: `id` (UUID PK), `project_id` (UUID FK to projects.id, NOT NULL), `user_id` (UUID FK to public.users.id, NOT NULL), `added_by` (UUID FK to public.users.id), `created_at` (timestamptz, default NOW())
  - [ ] 1.2 Create unique index on `(project_id, user_id)` to prevent duplicate membership
  - [ ] 1.3 Create index on `user_id` for efficient lookup of "which projects is this user in?"
  - [ ] 1.4 Create RLS policy on `project_members` scoped to tenant context
  - [ ] 1.5 Write migration rollback script

- [ ] **Task 2: Project Member Service** (AC: #2, #3, #4, #5, #6, #7)
  - [ ] 2.1 Create `ProjectMemberService` class: `add_member()`, `remove_member()`, `list_members()`, `check_access()`, `auto_assign_creator()`
  - [ ] 2.2 Implement `add_member()`: validate user is in org, check not already member, insert into project_members, trigger email notification
  - [ ] 2.3 Implement `add_members_bulk()`: accept list of user_ids, validate all, insert batch, trigger email notifications
  - [ ] 2.4 Implement `remove_member()`: validate not removing implicit Owner/Admin access, delete from project_members
  - [ ] 2.5 Implement `list_members()`: return project members with user profile data (name, email, avatar, org role, date added)
  - [ ] 2.6 Implement `check_access()`: return true if user is Owner/Admin OR exists in project_members for the project. Used as FastAPI dependency for project-scoped endpoints.
  - [ ] 2.7 Implement `auto_assign_creator()`: called by ProjectService.create_project() (Story 1.9) to add creator to project_members

- [ ] **Task 3: FastAPI Endpoints** (AC: #1, #2, #4, #7, #8)
  - [ ] 3.1 Create `POST /api/v1/projects/{project_id}/members` — add member(s) to project (Owner/Admin only), returns 201
  - [ ] 3.2 Create `GET /api/v1/projects/{project_id}/members` — list project members (all project members can view)
  - [ ] 3.3 Create `DELETE /api/v1/projects/{project_id}/members/{user_id}` — remove member (Owner/Admin only), returns 204
  - [ ] 3.4 Create `check_project_access` FastAPI dependency: verifies user is Owner/Admin or in project_members before allowing project-scoped operations
  - [ ] 3.5 Update `GET /api/v1/projects` (from Story 1.9) to filter by project membership (non-Admin users see only their projects)
  - [ ] 3.6 RBAC enforcement: `@require_role(['owner', 'admin'])` on add/remove endpoints
  - [ ] 3.7 Rate limiting: 30 member operations/project/hour
  - [ ] 3.8 Audit log all membership operations

- [ ] **Task 4: Email Notification** (AC: #5)
  - [ ] 4.1 Create email template for project assignment notification: subject, body with project name, added_by name, project link
  - [ ] 4.2 Integrate with email service (SendGrid/SES pattern from Story 1.3)
  - [ ] 4.3 Check user notification preferences (email_team_changes from Story 1.8) before sending
  - [ ] 4.4 Send emails asynchronously (non-blocking, background task or queue)

- [ ] **Task 5: React UI — Team Members Tab** (AC: #1, #2, #4)
  - [ ] 5.1 Add "Team Members" tab to project settings page (`/projects/{slug}/settings`)
  - [ ] 5.2 Team members table: avatar, name, email, org role, date added, remove action
  - [ ] 5.3 Empty state when no members assigned
  - [ ] 5.4 "Add Member" button (Owner/Admin only) with searchable dropdown/dialog of org members not yet in project
  - [ ] 5.5 Bulk member selection and add
  - [ ] 5.6 Remove member confirmation dialog
  - [ ] 5.7 Success/error toast notifications for add/remove actions
  - [ ] 5.8 Read-only view for non-Admin project members

- [ ] **Task 6: Project Access Integration** (AC: #3, #6)
  - [ ] 6.1 Update Story 1.9's `ProjectService.create_project()` to call `auto_assign_creator()` after project creation
  - [ ] 6.2 Apply `check_project_access` dependency to all project-scoped endpoints (current and future)
  - [ ] 6.3 Update project list endpoint to filter by membership for non-Admin users
  - [ ] 6.4 Update frontend project list to reflect access-filtered results

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: access check logic (Owner/Admin bypass, member check, non-member denied)
  - [ ] 7.2 Integration tests: `POST /api/v1/projects/{id}/members` — valid add, duplicate (409), user not in org (404), RBAC (non-admin rejected)
  - [ ] 7.3 Integration tests: `GET /api/v1/projects/{id}/members` — returns members with profile data, access enforcement
  - [ ] 7.4 Integration tests: `DELETE /api/v1/projects/{id}/members/{user_id}` — valid remove, RBAC enforcement
  - [ ] 7.5 Integration tests: project list filtering — non-Admin sees only assigned projects, Admin sees all
  - [ ] 7.6 Integration tests: project access enforcement — non-member gets 403 on project endpoints
  - [ ] 7.7 Integration tests: tenant isolation — project members in tenant A not visible in tenant B
  - [ ] 7.8 Integration tests: auto-assign creator on project creation
  - [ ] 7.9 Integration tests: rate limiting — 31st operation within hour returns 429
  - [ ] 7.10 Integration tests: email notification sent on add (with preference check)
  - [ ] 7.11 Security tests: SQL injection prevention, RBAC bypass attempts, cross-tenant access
  - [ ] 7.12 Frontend tests: team members tab, add member dialog, remove confirmation, bulk add, empty state

- [ ] **Task 8: Security Review** (AC: #3, #7, #8)
  - [ ] 8.1 Verify all queries use parameterized statements
  - [ ] 8.2 Verify tenant isolation: project_members scoped to tenant schema via ContextVar + RLS
  - [ ] 8.3 Verify RBAC: only Owner/Admin can add/remove members
  - [ ] 8.4 Verify project access enforcement cannot be bypassed (direct ID access, slug manipulation)
  - [ ] 8.5 Verify Owner/Admin implicit access cannot be removed
  - [ ] 8.6 Verify rate limiting prevents abuse

## Dev Notes

### Architecture Patterns

- **Project membership model:** `{tenant_schema}.project_members` is a simple join table between projects and users. It does NOT store a project-specific role — the user's org-level role determines their permissions. This keeps the permission model simple: one role per user per organization, applied to whichever projects they're assigned to.
- **Implicit Owner/Admin access:** Owner/Admin users can access ALL projects without being in project_members. The `check_project_access()` dependency checks org role first, then falls back to membership check. This means Owner/Admin don't need to be explicitly added to every project.
- **Creator auto-assignment:** Despite Owner/Admin having implicit access, the creator is still added to project_members for consistency — they appear in the Team Members tab and the membership provides an audit record.
- **Access enforcement pattern:** A reusable FastAPI dependency (`check_project_access`) that can be applied to any project-scoped endpoint. Checks: (1) is user Owner/Admin? → allow. (2) is user in project_members for this project? → allow. (3) → deny with 403. This becomes the standard pattern for all project-scoped endpoints in subsequent epics.
- **Email notification pattern:** Follows Story 1.3 (team invitation) email pattern. Uses SendGrid/SES. Respects Story 1.8 notification preferences (email_team_changes toggle). Sent asynchronously to avoid blocking the API response.
- **Bulk operations:** Add multiple members in a single request for efficiency. Backend validates all user_ids, inserts batch, sends individual emails per member.

### Project Structure Notes

- Project member service: `src/services/project_member_service.py`
- API routes: `src/api/v1/projects/members.py` (add, list, remove)
- Access dependency: `src/api/dependencies/project_access.py`
- Email template: `src/templates/emails/project_assignment.html`
- Frontend: `src/pages/projects/settings/TeamMembers.tsx`
- Reuse: RBAC decorators from Story 1.2, email service from Story 1.3, notification preferences from Story 1.8, project settings layout from Story 1.9
- Existing: `scripts/init-local-db.sql` for project_members table DDL addition

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Tenant isolation critical: all tests must verify project_members scoped to tenant schema
- Access enforcement critical: test that non-members cannot access project resources
- Use existing `test_tenant` and `tenant_connection` fixtures from conftest.py

### Learnings from Previous Story

**From Story 1-9-project-creation-configuration (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.9's specification establishes:

- **Project settings page framework** — Story 1.9 creates the project settings page at `/projects/{slug}/settings` with General and Advanced tabs. This story adds a "Team Members" tab to the same settings page.
- **Created_by pattern** — Story 1.9 records `created_by` on project creation. This story hooks into the creation flow to auto-assign the creator as a project member.
- **Slug-based routing** — Story 1.9 establishes `/projects/{slug}/*` URL pattern. This story uses the same pattern for team members tab.
- **Rate limiting pattern** — Story 1.9 rate-limits per-org (creation) and per-project (updates). This story rate-limits member operations per-project.

[Source: docs/stories/1-9-project-creation-configuration.md]

### References

- [Source: docs/planning/prd.md#Project-Management] — FR13 (assign team members with role-based access)
- [Source: docs/planning/prd.md#Roles-&-Permissions] — Admin can assign team members
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.10: Project Team Assignment, FR13
- [Source: docs/tech-specs/tech-spec-epic-1.md#RBAC-Permission-Matrix] — Role-based permissions per action
- [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy] — Schema-per-tenant isolation
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — RLS policies, parameterized queries, audit trails
- [Source: docs/epics/epics.md#Story-1.10] — AC source: team members tab, add member, permissions, email notification
- [Source: docs/stories/1-2-organization-creation-setup.md] — RBAC decorators, tenant context middleware, org member roster
- [Source: docs/stories/1-3-team-member-invitation.md] — Email notification pattern, SendGrid/SES
- [Source: docs/stories/1-5-login-session-management.md] — JWT auth middleware, tenant_id in JWT claims
- [Source: docs/stories/1-8-profile-notification-preferences.md] — Notification preferences (email_team_changes toggle)
- [Source: docs/stories/1-9-project-creation-configuration.md] — Projects table, created_by, project settings page
- [Source: scripts/init-local-db.sql] — Existing tenant schema tables

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-18 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-10-project-team-assignment.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
