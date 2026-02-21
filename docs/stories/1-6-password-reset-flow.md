# Story 1.6: Password Reset Flow

Status: ready-for-dev

## Story

As a user who forgot their password,
I want to reset it via email verification,
so that I can regain access to my account.

## Requirements Context

This is the **sixth story** in Epic 1 (Foundation & Administration). It provides the self-service password recovery mechanism for users who cannot log in. This story depends on the user account system (Story 1.1), the email service infrastructure (Stories 1.1/1.3), and the login/session system (Story 1.5). After a successful password reset, all existing sessions are invalidated for security.

**FRs Covered:**
- FR4 — Users can reset passwords via email verification workflow

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ [Source: docs/architecture/architecture.md#ADR-001]
- Email: SendGrid or AWS SES for transactional emails [Source: docs/architecture/architecture.md#Third-Party-Services]
- Password: bcrypt hashing, min 12 chars, uppercase, lowercase, number, special character [Source: docs/planning/prd.md#NFR-SEC1]
- Security: Parameterized queries ONLY; TLS 1.3 in transit; rate limiting [Source: docs/architecture/architecture.md#Security-Threat-Model]
- Session: JWT + refresh tokens in Redis (Story 1.5); all sessions invalidated on password reset

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`, bcrypt password hashing, email service
- Story 1.3 (Team Member Invitation) — email template patterns, async email delivery, retry logic
- Story 1.5 (Login & Session Management) — session invalidation (logout-all), login redirect after reset

## Acceptance Criteria

1. **AC1: Forgot Password Link** — Login page (`/login`) includes a "Forgot Password?" link below the password field. Link navigates to `/forgot-password` page.

2. **AC2: Reset Request Form** — Forgot password page (`/forgot-password`) with email input field and "Send Reset Link" button. On submission, calls `POST /api/v1/auth/forgot-password`. **Always** returns success message: "If an account with that email exists, we've sent a password reset link." — regardless of whether the email exists (no email enumeration). Email field validates RFC 5322 format client-side.

3. **AC3: Reset Token Generation** — If the email exists in `public.users`: system generates a cryptographically random reset token (`secrets.token_urlsafe(32)`), stores token hash (SHA-256) in `public.password_resets` table with: `id` (UUID), `user_id` (UUID FK), `token_hash` (varchar 64), `expires_at` (timestamptz, 1 hour from creation), `used_at` (timestamptz, nullable), `created_at` (timestamptz). Previous unused reset tokens for the same user are invalidated (set `used_at = now()`). If user has `auth_provider='google'` only (no local password): still send email, but with message "Your account uses Google Sign-In. Use the Google login button instead."

4. **AC4: Reset Email Delivery** — System sends password reset email via SendGrid/AWS SES containing: user's name, "Reset Password" CTA button linking to `/reset-password?token={token}`, expiry notice ("This link expires in 1 hour"), security notice ("If you didn't request this, you can ignore this email"). Email sent asynchronously (non-blocking). Retry logic: up to 3 attempts with exponential backoff (1s, 4s, 16s). Email is mobile-responsive HTML, branded with QUALISYS styling.

5. **AC5: Reset Password Page** — Reset password page (`/reset-password?token={token}`) validates token on page load via `GET /api/v1/auth/reset-password?token={token}`. If valid: displays new password form with two fields (new password + confirm password). If invalid/expired/used: displays error page with message and link back to forgot password. Password requirements enforced (same as Story 1.1): min 12 chars, uppercase, lowercase, number, special character. Real-time strength indicator (weak/medium/strong). Passwords must match.

6. **AC6: Password Update** — On form submission, calls `POST /api/v1/auth/reset-password` with `{token, new_password}`. Server validates: token exists, not expired, not used, new password meets policy, new password is not the same as old password. Updates `public.users.password_hash` with new bcrypt hash. Marks reset token as used (`used_at = now()`). Invalidates ALL existing sessions for the user (calls `AuthService.logout_all()` from Story 1.5). Redirects to login page with success message: "Password reset successfully. Please log in with your new password."

7. **AC7: Rate Limiting & Abuse Prevention** — Reset request endpoint rate-limited to 3 requests per email per hour (Redis-backed). Reset password endpoint rate-limited to 5 attempts per token per hour (prevents brute-force on token). After 10 failed reset attempts from same IP per hour: temporary block (HTTP 429 with `Retry-After`). Token brute-force prevention: tokens are 32 bytes (256 bits of entropy), infeasible to guess.

8. **AC8: Audit Trail** — All password reset actions logged: reset requested (email, IP, user_agent, timestamp), reset email sent (email, delivery status), reset completed (user_id, IP, timestamp), reset failed (reason: expired, used, invalid, policy violation). Audit entries include IP address and user_agent for security analysis.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema — Password Resets** (AC: #3)
  - [ ] 1.1 Create Alembic migration for `public.password_resets` table: `id` (UUID PK), `user_id` (UUID FK to `public.users`), `token_hash` (varchar 64, indexed), `expires_at` (timestamptz), `used_at` (timestamptz nullable), `created_at` (timestamptz)
  - [ ] 1.2 Create index on `token_hash` for fast lookup
  - [ ] 1.3 Create index on `(user_id, used_at)` for invalidating previous tokens
  - [ ] 1.4 Write migration rollback script

- [ ] **Task 2: Password Reset Service** (AC: #3, #6)
  - [ ] 2.1 Create `PasswordResetService` class: `request_reset()`, `validate_token()`, `reset_password()`, `invalidate_previous_tokens()`
  - [ ] 2.2 Implement `request_reset()`: look up user by email, generate token (`secrets.token_urlsafe(32)`), store SHA-256 hash in DB, invalidate previous unused tokens, trigger email
  - [ ] 2.3 Implement `validate_token()`: hash provided token, look up in DB, check not expired, check not used
  - [ ] 2.4 Implement `reset_password()`: validate token, validate password policy, check not same as old password (bcrypt compare), update `password_hash`, mark token used, call `AuthService.logout_all()`
  - [ ] 2.5 Handle Google-only accounts: detect `auth_provider='google'`, send alternative email message

- [ ] **Task 3: FastAPI Endpoints** (AC: #2, #5, #6, #7)
  - [ ] 3.1 Create `POST /api/v1/auth/forgot-password` — accepts `{email}`, always returns 200 (no enumeration), triggers reset flow if email exists
  - [ ] 3.2 Create `GET /api/v1/auth/reset-password?token={token}` — validates token, returns `{valid: bool, email: string}` (email partially masked for UX)
  - [ ] 3.3 Create `POST /api/v1/auth/reset-password` — accepts `{token, new_password}`, resets password, invalidates sessions
  - [ ] 3.4 Rate limiting: 3 requests/email/hour on forgot-password, 5 attempts/token/hour on reset, 10 attempts/IP/hour global
  - [ ] 3.5 Audit log all operations

- [ ] **Task 4: Reset Email Template** (AC: #4)
  - [ ] 4.1 Create password reset email HTML template (branded, mobile-responsive, CTA button with reset URL)
  - [ ] 4.2 Create Google-only account email variant (message directing user to Google login)
  - [ ] 4.3 Send via existing email service (reuse from Story 1.1/1.3)
  - [ ] 4.4 Implement retry logic: up to 3 attempts with exponential backoff
  - [ ] 4.5 Log delivery status with correlation to reset request

- [ ] **Task 5: React UI — Forgot Password** (AC: #1, #2)
  - [ ] 5.1 Add "Forgot Password?" link to login page
  - [ ] 5.2 Create `/forgot-password` page with email input and "Send Reset Link" button (shadcn/ui Input, Button)
  - [ ] 5.3 Show success message on submission (always, regardless of email existence)
  - [ ] 5.4 Form validation: RFC 5322 email format
  - [ ] 5.5 Handle rate limit (429): show countdown message

- [ ] **Task 6: React UI — Reset Password** (AC: #5, #6)
  - [ ] 6.1 Create `/reset-password` page that reads `token` from query params
  - [ ] 6.2 Validate token on page load (call `GET /api/v1/auth/reset-password?token=...`)
  - [ ] 6.3 If valid: show new password form with password + confirm password fields
  - [ ] 6.4 If invalid: show error message with link to forgot-password page
  - [ ] 6.5 Implement password strength indicator (weak/medium/strong) matching Story 1.1 signup policy
  - [ ] 6.6 Implement password match validation (confirm field)
  - [ ] 6.7 On successful reset: redirect to login page with success banner
  - [ ] 6.8 Reuse password policy components from Story 1.1 signup form

- [ ] **Task 7: Testing** (AC: all)
  - [ ] 7.1 Unit tests: token generation randomness, token hash verification, password policy validation, expiry checking
  - [ ] 7.2 Integration tests: `POST /api/v1/auth/forgot-password` — existing email (sends email), non-existing email (still returns 200), Google-only account (alternative email)
  - [ ] 7.3 Integration tests: `GET /api/v1/auth/reset-password?token=...` — valid token, expired token, used token, invalid token
  - [ ] 7.4 Integration tests: `POST /api/v1/auth/reset-password` — valid reset, expired token, used token, weak password, same-as-old password
  - [ ] 7.5 Integration tests: session invalidation — after reset, all existing refresh tokens for user are deleted from Redis
  - [ ] 7.6 Integration tests: previous token invalidation — requesting new reset invalidates old unused token
  - [ ] 7.7 Rate limiting tests: 3 requests/email/hour, 5 attempts/token/hour, IP-based blocking
  - [ ] 7.8 Security tests: no email enumeration (timing + response identical), token entropy sufficient, token stored as hash only
  - [ ] 7.9 Frontend tests: forgot password form, success message, reset password form, strength indicator, error states, redirect after reset

- [ ] **Task 8: Security Review** (AC: #3, #7, #8)
  - [ ] 8.1 Verify reset tokens are cryptographically random (32 bytes / 256 bits entropy)
  - [ ] 8.2 Verify tokens stored as SHA-256 hash (not plaintext) in database
  - [ ] 8.3 Verify no email enumeration: identical response and timing for existing vs non-existing emails
  - [ ] 8.4 Verify tokens are single-use (marked as used after successful reset)
  - [ ] 8.5 Verify all sessions invalidated after password reset
  - [ ] 8.6 Verify old password check prevents reuse of same password
  - [ ] 8.7 Verify rate limiting cannot be bypassed

## Dev Notes

### Architecture Patterns

- **Token-based reset (not JWT):** Reset tokens are opaque, cryptographically random, stored as SHA-256 hash in DB. Not JWT — no claims needed, and DB storage enables revocation and single-use enforcement.
- **No email enumeration:** Both existing and non-existing emails get the same HTTP 200 response with the same message. Timing must also be constant (use dummy operations for non-existing emails to match response time).
- **Session invalidation on reset:** After successful password reset, call `AuthService.logout_all()` (Story 1.5) to invalidate all refresh tokens in Redis. This forces the user (and any attacker with stolen credentials) to re-authenticate with the new password.
- **Previous token invalidation:** When a new reset is requested, all previous unused tokens for that user are marked as used. Only the latest token works.
- **Email service reuse:** Story 1.1 (verification) and Story 1.3 (invitations) establish the email sending pattern. This story adds two new templates (reset, Google-only) using the same infrastructure.
- **Password policy reuse:** Story 1.1 establishes password requirements (min 12 chars, complexity). This story reuses the same validation logic and frontend strength indicator component.

### Project Structure Notes

- Password reset service: `src/services/password_reset_service.py`
- API routes: `src/api/v1/auth/` (add forgot-password and reset-password endpoints alongside login endpoints from Story 1.5)
- Email templates: `src/templates/email/password-reset.html`, `src/templates/email/password-reset-google.html`
- Frontend pages: `src/pages/auth/forgot-password/`, `src/pages/auth/reset-password/`
- Reuse: password policy validation from Story 1.1 signup, email service from Story 1.1/1.3, session invalidation from Story 1.5

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Email sending mocked in tests (verify template rendering and delivery calls)
- Redis required for session invalidation tests
- Timing tests for no-enumeration: measure response time for existing vs non-existing emails (should be within 10ms)

### Learnings from Previous Story

**From Story 1-5-login-session-management (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.5's specification establishes key patterns this story depends on:

- **AuthService.logout_all()** at `src/services/auth_service.py` — call after successful password reset to invalidate all sessions
- **Redis session key structure** `user_sessions:{user_id}` → SET of token hashes — used by logout_all to find and delete all refresh tokens
- **Auth API routes** at `src/api/v1/auth/` — add forgot-password and reset-password endpoints alongside existing login/logout/refresh endpoints
- **httpOnly cookie pattern** — reset flow redirects to login after success; user re-authenticates with new password, gets fresh JWT cookies
- **Rate limiting pattern** from Story 1.3/1.5 — Redis-backed, per-entity limits with 429 response

[Source: docs/stories/1-5-login-session-management.md]

### References

- [Source: docs/planning/prd.md#User-Account-&-Access-Management] — FR4 (password reset via email verification)
- [Source: docs/planning/prd.md#NFR-SEC1] — Password: min 12 chars, complexity rules
- [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Flow] — Auth flow diagram
- [Source: docs/architecture/architecture.md#Third-Party-Services] — SendGrid/AWS SES
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Rate limiting, audit trails
- [Source: docs/epics/epics.md#Story-1.6] — Acceptance criteria source
- [Source: docs/stories/1-1-user-account-creation.md] — User model, bcrypt, email service, password policy
- [Source: docs/stories/1-3-team-member-invitation.md] — Email template patterns, retry logic
- [Source: docs/stories/1-5-login-session-management.md] — AuthService.logout_all(), session key structure, login redirect

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-17 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-6-password-reset-flow.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
