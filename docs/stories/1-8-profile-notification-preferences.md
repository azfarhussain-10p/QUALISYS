# Story 1.8: Profile & Notification Preferences

Status: ready-for-dev

## Story

As a user,
I want to configure my profile information and notification preferences,
so that I receive relevant updates and my profile reflects my identity across the platform.

## Requirements Context

This is the **eighth story** in Epic 1 (Foundation & Administration). It provides self-service profile management (name, avatar, timezone) and basic notification preferences (email). This story establishes the user preferences infrastructure that Epic 5 (Story 5.15) extends with Slack integration and advanced notification rules. Profile information (name, avatar) is displayed throughout the platform — in team member lists, activity logs, and the app header.

**FRs Covered:**
- FR10 — Users can configure their profile information and notification preferences

**Scope Boundary:**
- This story covers: profile editing (name, avatar, timezone), basic email notification preferences (on/off, frequency), password change (non-reset, from settings)
- Story 5.15 extends with: Slack preferences, severity filters, per-channel routing, advanced scheduling
- Story 1.7 handles: 2FA settings on the same security settings page (separate section)

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ [Source: docs/architecture/architecture.md#ADR-001]
- Object Storage: AWS S3 for avatar uploads (presigned URLs, same pattern as org logo in Story 1.2) [Source: docs/architecture/architecture.md#Technology-Stack]
- Security: Parameterized queries ONLY; TLS 1.3 in transit [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Session: JWT + refresh tokens in Redis (Story 1.5); profile changes do NOT invalidate sessions

**Dependencies:**
- Story 1.1 (User Account Creation) — `public.users` table with `full_name`, `avatar_url`, `email`, `auth_provider`
- Story 1.2 (Organization Creation & Setup) — S3 upload pattern (presigned URLs), RBAC decorators
- Story 1.5 (Login & Session Management) — JWT auth middleware, session management (password change triggers logout-all)

## Acceptance Criteria

1. **AC1: Profile Settings Page** — User settings page (`/settings/profile`) displays current profile information: full name (editable), email (read-only, shows auth provider badge — "Email" or "Google"), avatar (current image or initials fallback), timezone (dropdown with common timezones). Page accessible from user avatar menu in app header → "Settings". Tabbed settings layout: Profile, Security (Story 1.7), Notifications.

2. **AC2: Edit Profile — Name** — User can update `full_name` via inline edit or form. Validation: required, 2-100 characters, no leading/trailing whitespace. On save: `PATCH /api/v1/users/me/profile` updates `public.users.full_name`. Success toast: "Profile updated." Name change reflected immediately in app header and across the platform (no cache staleness — JWT does not store name, fetched from DB).

3. **AC3: Edit Profile — Avatar** — "Change Avatar" button opens file picker. Accepted: PNG, JPG, WebP. Max 5MB. Image uploaded to S3 via presigned URL: `users/{user_id}/avatar/{uuid}.{ext}`. Server-side processing: resize to 128x128px thumbnail + preserve original. Avatar URL stored in `public.users.avatar_url`. Old avatar deleted from S3 on replacement. "Remove Avatar" option returns to initials fallback. Google OAuth users: default avatar is Google profile picture (can be overridden).

4. **AC4: Edit Profile — Timezone** — User can set their timezone from a searchable dropdown (IANA timezone database, e.g., "America/New_York", "Europe/London", "Asia/Karachi"). Stored in `public.users.timezone` (varchar, default "UTC"). Timezone used for: notification delivery scheduling (daily/weekly digests), date/time display formatting in the UI, audit log timestamps display.

5. **AC5: Change Password (from Settings)** — Security tab includes "Change Password" section (only for `auth_provider='local'` users, hidden for Google-only). Form: current password, new password, confirm new password. Validates: current password correct (bcrypt compare), new password meets policy (Story 1.1: min 12 chars, complexity), new ≠ current. On success: update `password_hash`, invalidate ALL existing sessions (`AuthService.logout_all()`), redirect to login with message "Password changed successfully. Please log in with your new password." Rate-limited: 3 attempts per user per hour.

6. **AC6: Notification Preferences — Email** — Notifications tab (`/settings/notifications`) shows email notification preferences: "Email me about" section with toggles for each notification category: Test run completions (default: on), Test failures (default: on), Team member changes (default: on), Security alerts — login from new device, password changes (default: on, cannot be disabled). "Email frequency" dropdown: Real-time (default), Daily digest (configurable time, default 9:00 AM user timezone), Weekly digest (configurable day + time, default Monday 9:00 AM). Preferences stored in `public.user_notification_preferences` table.

7. **AC7: Notification Preferences — Save & Apply** — Preferences saved via `PUT /api/v1/users/me/notifications`. Changes take effect immediately for new notifications. Existing queued notifications (if any) are not retroactively modified. Backend notification dispatcher reads preferences before sending any email. Security notifications (login from new device, password change) are always sent regardless of user preference (non-disableable for security compliance).

8. **AC8: API Endpoints & Validation** — All profile/notification endpoints require JWT authentication. `GET /api/v1/users/me` returns full profile (name, email, avatar_url, timezone, auth_provider, email_verified, created_at). `PATCH /api/v1/users/me/profile` updates name, timezone. `POST /api/v1/users/me/avatar` returns presigned S3 upload URL. `DELETE /api/v1/users/me/avatar` removes avatar. `GET /api/v1/users/me/notifications` returns notification preferences. `PUT /api/v1/users/me/notifications` saves notification preferences. `POST /api/v1/users/me/change-password` changes password. All endpoints return structured JSON errors.

9. **AC9: Audit Trail** — Profile changes logged: name updated (old_value, new_value), avatar uploaded/removed, timezone changed, password changed (no password values logged), notification preferences updated (changed categories). Audit entries include user_id, IP, user_agent, timestamp.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema Updates** (AC: #4, #6)
  - [ ] 1.1 Add `timezone` column to `public.users` via Alembic migration (varchar 50, default 'UTC')
  - [ ] 1.2 Create `public.user_notification_preferences` table: `id` (UUID PK), `user_id` (UUID FK, unique), `email_test_completions` (boolean, default true), `email_test_failures` (boolean, default true), `email_team_changes` (boolean, default true), `email_security_alerts` (boolean, default true), `email_frequency` (varchar 20, default 'realtime'), `digest_time` (time, default '09:00'), `digest_day` (varchar 10, default 'monday'), `created_at` (timestamptz), `updated_at` (timestamptz)
  - [ ] 1.3 Create unique index on `user_notification_preferences.user_id`
  - [ ] 1.4 Write migration rollback script

- [ ] **Task 2: Profile Service** (AC: #2, #3, #4, #5)
  - [ ] 2.1 Create `ProfileService` class: `get_profile()`, `update_profile()`, `upload_avatar()`, `remove_avatar()`, `change_password()`
  - [ ] 2.2 Implement `update_profile()`: validate name (2-100 chars), validate timezone (IANA database check), update `public.users`
  - [ ] 2.3 Implement `upload_avatar()`: generate presigned S3 upload URL (`users/{user_id}/avatar/{uuid}.{ext}`), validate content type, return URL
  - [ ] 2.4 Implement avatar processing: after upload callback, resize to 128x128 thumbnail, store URL in `public.users.avatar_url`, delete old avatar from S3
  - [ ] 2.5 Implement `remove_avatar()`: delete from S3, set `avatar_url = null`
  - [ ] 2.6 Implement `change_password()`: verify current password (bcrypt), validate new password policy, update `password_hash`, call `AuthService.logout_all()`

- [ ] **Task 3: Notification Preferences Service** (AC: #6, #7)
  - [ ] 3.1 Create `NotificationPreferencesService` class: `get_preferences()`, `update_preferences()`, `should_notify()`
  - [ ] 3.2 Implement `get_preferences()`: return user's notification preferences (create default row on first access)
  - [ ] 3.3 Implement `update_preferences()`: validate preference values, upsert `public.user_notification_preferences`
  - [ ] 3.4 Implement `should_notify()`: check user preferences for given notification category — used by notification dispatcher in future stories
  - [ ] 3.5 Enforce security notifications always sent (email_security_alerts cannot be set to false)

- [ ] **Task 4: FastAPI Endpoints** (AC: #8, #9)
  - [ ] 4.1 Create `GET /api/v1/users/me` — returns full user profile
  - [ ] 4.2 Create `PATCH /api/v1/users/me/profile` — updates name, timezone
  - [ ] 4.3 Create `POST /api/v1/users/me/avatar` — returns presigned S3 upload URL
  - [ ] 4.4 Create `DELETE /api/v1/users/me/avatar` — removes avatar
  - [ ] 4.5 Create `GET /api/v1/users/me/notifications` — returns notification preferences
  - [ ] 4.6 Create `PUT /api/v1/users/me/notifications` — saves notification preferences
  - [ ] 4.7 Create `POST /api/v1/users/me/change-password` — changes password with session invalidation
  - [ ] 4.8 Rate limiting: change-password 3/user/hour; profile updates 30/user/hour
  - [ ] 4.9 Audit log all profile and notification changes

- [ ] **Task 5: React UI — Profile Settings** (AC: #1, #2, #3, #4)
  - [ ] 5.1 Create `/settings` layout with tab navigation: Profile, Security, Notifications
  - [ ] 5.2 Profile tab: full name input, email display (read-only with auth provider badge), timezone searchable dropdown
  - [ ] 5.3 Avatar section: current avatar display (image or initials fallback), "Change Avatar" button with file picker, "Remove Avatar" button, upload progress indicator
  - [ ] 5.4 Avatar upload: validate file type (PNG/JPG/WebP) and size (max 5MB) client-side, upload to presigned URL, display new avatar on success
  - [ ] 5.5 "Save Changes" button with form validation, success/error toast notifications
  - [ ] 5.6 Add "Settings" link to user avatar menu in app header

- [ ] **Task 6: React UI — Security & Notifications** (AC: #5, #6, #7)
  - [ ] 6.1 Security tab: "Change Password" section (hidden for Google-only users), current/new/confirm password fields, password strength indicator (reuse from Story 1.1), save button
  - [ ] 6.2 Security tab: 2FA section placeholder (implemented by Story 1.7)
  - [ ] 6.3 Notifications tab: email notification toggles for each category, frequency dropdown (Real-time, Daily digest, Weekly digest), digest time picker, digest day selector (for weekly)
  - [ ] 6.4 Security alerts toggle shown but disabled with tooltip "Security notifications cannot be disabled"
  - [ ] 6.5 "Save Preferences" button with success/error feedback

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: profile validation (name length, timezone IANA check), password policy, notification preference defaults
  - [ ] 7.2 Integration tests: `GET /api/v1/users/me` — returns profile; `PATCH /api/v1/users/me/profile` — updates name, timezone
  - [ ] 7.3 Integration tests: avatar upload presigned URL generation, avatar removal, old avatar cleanup
  - [ ] 7.4 Integration tests: `POST /api/v1/users/me/change-password` — correct current password, wrong current password, weak new password, same-as-old, session invalidation after change
  - [ ] 7.5 Integration tests: notification preferences CRUD — get defaults, update, security alerts non-disableable
  - [ ] 7.6 Integration tests: rate limiting on change-password (3/user/hour)
  - [ ] 7.7 Security tests: auth_provider check (password change hidden for Google-only), profile endpoints require JWT, no PII in error responses
  - [ ] 7.8 Frontend tests: profile form, avatar upload/remove, timezone selector, password change form, notification toggles, tab navigation

- [ ] **Task 8: Security Review** (AC: #5, #9)
  - [ ] 8.1 Verify avatar uploads restricted to image types (no executable files)
  - [ ] 8.2 Verify presigned URLs expire quickly (5 minutes) and are scoped to user's path
  - [ ] 8.3 Verify password change requires current password verification
  - [ ] 8.4 Verify all sessions invalidated after password change
  - [ ] 8.5 Verify security notifications cannot be disabled
  - [ ] 8.6 Verify no PII (password values) in audit logs
  - [ ] 8.7 Verify rate limiting on password change endpoint

## Dev Notes

### Architecture Patterns

- **Settings page structure:** Tabbed layout (Profile, Security, Notifications) at `/settings/*`. Security tab hosts both password change (this story) and 2FA (Story 1.7). This establishes the settings page framework that future stories add sections to.
- **Avatar upload via presigned URL:** Same pattern as org logo upload (Story 1.2). Browser uploads directly to S3 via presigned URL — no backend proxy needed. Server generates URL, client uploads, server processes (resize) on callback or async.
- **Notification preferences table:** Separate table (`public.user_notification_preferences`) rather than JSONB column on users. This allows schema evolution as new notification categories are added (Epic 5 adds Slack). Default preferences created lazily on first access.
- **Password change vs reset:** Story 1.6 handles forgot-password (email-based reset). This story handles change-password-from-settings (requires current password). Both invalidate all sessions after success. Reuse `AuthService.logout_all()` from Story 1.5.
- **Timezone handling:** Store IANA timezone string (e.g., "America/New_York"). Used for digest scheduling and UI date formatting. Frontend uses Intl API or date-fns-tz for display. Backend uses pytz or zoneinfo for scheduling.
- **Scope for Epic 5:** Story 5.15 (User Notification Preferences Management) adds Slack notification preferences, severity filters, per-channel routing. This story establishes the preferences infrastructure that Story 5.15 extends.

### Project Structure Notes

- Profile service: `src/services/profile_service.py`
- Notification preferences service: `src/services/notification_preferences_service.py`
- API routes: `src/api/v1/users/` (me, profile, avatar, notifications, change-password)
- Frontend settings: `src/pages/settings/` (profile, security, notifications tabs)
- Reuse: password policy validation from Story 1.1, S3 upload pattern from Story 1.2, `AuthService.logout_all()` from Story 1.5
- Settings framework: `src/layouts/SettingsLayout.tsx` (tab navigation wrapper)

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- S3 operations mocked in tests (verify presigned URL generation and delete calls)
- Redis required for session invalidation tests (password change)

### Learnings from Previous Story

**From Story 1-7-two-factor-authentication-totp (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.7's specification establishes:

- **Security settings page** at `/settings/security` — this story creates the tabbed settings layout that hosts the security section. Story 1.7 adds the 2FA section within the security tab.
- **Password confirmation pattern** — Story 1.7 requires password for disable/regenerate. This story's change-password also requires current password. Shared UI pattern: password confirmation modal/inline.
- **Auth endpoint router** — `src/api/v1/auth/` has login, refresh, logout, MFA routes. This story adds `src/api/v1/users/` routes for profile and preferences.

[Source: docs/stories/1-7-two-factor-authentication-totp.md]

### References

- [Source: docs/planning/prd.md#User-Account-&-Access-Management] — FR10 (profile and notification preferences)
- [Source: docs/planning/prd.md#Administration-&-Configuration] — FR109 (notification preferences — extended in Story 5.15)
- [Source: docs/tech-specs/tech-spec-epic-1.md#In-Scope-Stories] — Story 1.8: Profile & Notification Preferences
- [Source: docs/architecture/architecture.md#Technology-Stack] — AWS S3 for object storage (avatar uploads)
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Audit trails, rate limiting
- [Source: docs/epics/epics.md#Story-1.8] — AC source: profile page, notification preferences, email frequency
- [Source: docs/planning/ux-design-specification.md#Common-Elements] — Top nav with notifications bell and user avatar menu
- [Source: docs/stories/1-1-user-account-creation.md] — public.users table (full_name, avatar_url, auth_provider), password policy
- [Source: docs/stories/1-2-organization-creation-setup.md] — S3 presigned URL pattern for logo upload, RBAC decorators
- [Source: docs/stories/1-5-login-session-management.md] — AuthService.logout_all(), JWT auth middleware
- [Source: docs/stories/1-7-two-factor-authentication-totp.md] — Security settings page, password confirmation pattern

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-17 | Story drafted from epics, PRD, tech spec, architecture, UX design, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-8-profile-notification-preferences.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
