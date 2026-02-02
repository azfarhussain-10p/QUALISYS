# Story 1.1: User Account Creation

Status: ready-for-dev

## Story

As a new user,
I want to sign up with email/password or Google SSO,
so that I can access the QUALISYS platform.

## Requirements Context

This is the **first feature story** in Epic 1 (Foundation & Administration). It establishes the user registration system that all subsequent stories depend on — organization creation (1.2), login (1.5), MFA (1.7), and all RBAC-gated features.

**FR Covered:** FR1 — Users can create accounts with email/password or Google SSO

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ with schema-per-tenant model; user records in `public.users` table for cross-tenant lookup [Source: docs/architecture/architecture.md#Four-Pillar-Multi-Tenancy]
- Password hashing: bcrypt with cost factor 12
- Password policy: Min 12 characters, complexity rules (uppercase, lowercase, number, special character) [Source: docs/planning/prd.md#Compliance-&-Security-Requirements]
- Session: JWT tokens (7-day expiry, httpOnly cookies), refresh token rotation [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Architecture]
- Cache: Redis 7+ for session storage and rate limiting
- Email service: SendGrid or AWS SES for verification emails [Source: docs/architecture/architecture.md#Third-Party-Services]
- OAuth: Google OAuth 2.0 provider [Source: docs/planning/prd.md#Authentication-&-Authorization]
- Encryption: TLS 1.3 in transit, AES-256 at rest [Source: docs/planning/prd.md#Data-Encryption]
- Security: Parameterized queries ONLY, zero dynamic SQL; sanitize all user input; never log credentials [Source: docs/architecture/architecture.md#Security-Threat-Model]

## Acceptance Criteria

1. **AC1: Email/Password Signup Form** — Signup page renders a form with email, password, confirm password, and full name fields. Email validated (RFC 5322 format). Password validated client-side AND server-side: min 12 characters, at least 1 uppercase, 1 lowercase, 1 digit, 1 special character. Real-time inline validation feedback displayed. Form submission disabled until all validations pass.

2. **AC2: Google OAuth Signup Flow** — "Sign up with Google" button initiates OAuth 2.0 authorization code flow with Google. On successful Google consent, system creates user account using Google profile data (email, name, avatar URL). If Google email already registered, link accounts or return error with guidance. OAuth callback handles errors gracefully (user denies consent, network failure).

3. **AC3: Email Verification** — On email/password signup, system sends verification email via SendGrid/AWS SES with a signed, time-limited token (24-hour expiry). Email contains verification link. Clicking link marks email as verified in database. Unverified users cannot access platform features beyond a "Please verify your email" interstitial. Resend verification email available on interstitial.

4. **AC4: Database Record Creation** — User record created in `public.users` table with: `id` (UUID v4), `email` (unique, lowercase), `full_name`, `password_hash` (bcrypt, cost 12, NULL for OAuth-only users), `email_verified` (boolean), `auth_provider` (enum: 'email', 'google'), `google_id` (nullable), `avatar_url` (nullable), `created_at`, `updated_at`. All writes use parameterized queries.

5. **AC5: Duplicate Email Prevention** — System rejects signup if email already exists (case-insensitive comparison via `LOWER(email)` unique index). Error message: "An account with this email already exists. Please log in or reset your password." No information leakage about which auth provider was used.

6. **AC6: Rate Limiting** — Signup endpoint rate-limited to 5 requests per IP per minute (Redis-backed). Return HTTP 429 with `Retry-After` header on exceeded limit. Google OAuth callback rate-limited to 10 requests per IP per minute.

7. **AC7: Security Compliance** — Passwords never logged or returned in API responses. API responses exclude `password_hash`. All traffic over TLS 1.3. CSRF protection on signup form. Input sanitized against XSS (HTML entities escaped). SQL injection prevented via ORM parameterized queries.

8. **AC8: Error Handling** — All signup errors return appropriate HTTP status codes (400 validation, 409 duplicate, 429 rate limit, 500 server error) with structured JSON error response `{ "error": { "code": string, "message": string } }`. Errors logged server-side with correlation ID (no PII in logs).

## Tasks / Subtasks

- [ ] **Task 1: Database Schema & Migration** (AC: #4, #5)
  - [ ] 1.1 Create Alembic migration for `public.users` table with columns: `id` (UUID PK), `email` (varchar 255, unique), `full_name` (varchar 255), `password_hash` (varchar 255, nullable), `email_verified` (boolean, default false), `auth_provider` (varchar 20), `google_id` (varchar 255, nullable), `avatar_url` (text, nullable), `created_at` (timestamptz), `updated_at` (timestamptz)
  - [ ] 1.2 Create unique index on `LOWER(email)` for case-insensitive duplicate detection
  - [ ] 1.3 Create SQLAlchemy model `User` with all fields and validation
  - [ ] 1.4 Write migration rollback (downgrade) script

- [ ] **Task 2: FastAPI Registration Endpoints** (AC: #1, #4, #5, #6, #8)
  - [ ] 2.1 Create `POST /api/v1/auth/register` endpoint with Pydantic request schema (email, password, full_name)
  - [ ] 2.2 Implement server-side validation: email format (RFC 5322), password policy (12+ chars, complexity), full_name (non-empty, max 255)
  - [ ] 2.3 Implement bcrypt password hashing (cost factor 12) using `passlib`
  - [ ] 2.4 Implement duplicate email check (case-insensitive) with proper 409 response
  - [ ] 2.5 Implement rate limiting middleware (5 req/IP/min) using Redis with `Retry-After` header
  - [ ] 2.6 Implement structured JSON error responses with correlation IDs
  - [ ] 2.7 Ensure `password_hash` excluded from all response schemas

- [ ] **Task 3: Google OAuth 2.0 Flow** (AC: #2)
  - [ ] 3.1 Create `GET /api/v1/auth/google` endpoint to initiate OAuth 2.0 authorization code flow (redirect to Google consent screen)
  - [ ] 3.2 Create `GET /api/v1/auth/google/callback` endpoint to handle OAuth callback
  - [ ] 3.3 Exchange authorization code for access token, fetch Google user profile
  - [ ] 3.4 Create or link user account from Google profile (email, name, avatar, google_id)
  - [ ] 3.5 Handle edge cases: consent denied, existing email with different provider, network failures
  - [ ] 3.6 Rate limit callback endpoint (10 req/IP/min)

- [ ] **Task 4: Email Verification** (AC: #3)
  - [ ] 4.1 Implement signed verification token generation (JWT with 24-hour expiry containing user ID)
  - [ ] 4.2 Create `POST /api/v1/auth/verify-email` endpoint to validate token and mark `email_verified = true`
  - [ ] 4.3 Create `POST /api/v1/auth/resend-verification` endpoint with rate limiting (3 per hour per user)
  - [ ] 4.4 Integrate SendGrid/AWS SES for transactional email delivery with HTML template
  - [ ] 4.5 Create verification email template (branded, mobile-responsive, CTA button)

- [ ] **Task 5: React Signup UI** (AC: #1, #2)
  - [ ] 5.1 Create `/signup` route with signup form component using shadcn/ui form elements
  - [ ] 5.2 Implement real-time client-side validation (email format, password strength meter, confirm password match)
  - [ ] 5.3 Implement "Sign up with Google" button with OAuth redirect
  - [ ] 5.4 Implement form submission with loading state, error display, and success redirect
  - [ ] 5.5 Create "Check your email" interstitial page for post-registration
  - [ ] 5.6 Create email verification landing page (token validation on mount)

- [ ] **Task 6: Testing** (AC: all)
  - [ ] 6.1 Unit tests: password hashing, email validation, token generation/verification, rate limiting logic
  - [ ] 6.2 Integration tests: `POST /api/v1/auth/register` (happy path, duplicate email, invalid input, rate limit exceeded)
  - [ ] 6.3 Integration tests: Google OAuth flow (mock Google API, success/failure/linking scenarios)
  - [ ] 6.4 Integration tests: email verification (valid token, expired token, invalid token, resend)
  - [ ] 6.5 Frontend tests: form validation behavior, OAuth button render, error display, interstitial navigation
  - [ ] 6.6 Security tests: SQL injection attempts rejected, XSS payloads sanitized, password not in response body, CSRF token required

- [ ] **Task 7: Security Review Checklist** (AC: #7)
  - [ ] 7.1 Verify parameterized queries in all DB operations (no raw SQL string concatenation)
  - [ ] 7.2 Verify `password_hash` excluded from all API response models
  - [ ] 7.3 Verify no PII in server logs (email masked in error logs)
  - [ ] 7.4 Verify CSRF token enforcement on form submission
  - [ ] 7.5 Verify rate limiting active and returning correct HTTP 429 responses

## Dev Notes

### Architecture Patterns

- **Multi-tenant context:** At signup, users are created in the `public.users` table (shared schema). Tenant association happens in Story 1.2 (Organization Creation) when the user creates or joins an organization. This story does NOT create tenant schemas.
- **Auth provider abstraction:** Use an enum (`email`, `google`) in the `auth_provider` column. Future providers (SAML, GitHub) can be added without schema changes.
- **JWT verification tokens:** Use project-scoped signing secret (not the session JWT secret). Tokens for email verification are single-purpose and short-lived.
- **Password hashing:** Use `passlib[bcrypt]` with automatic salt generation. Cost factor 12 balances security and login performance (~250ms hash time).
- **Rate limiting:** Use Redis `INCR` with `EXPIRE` for sliding window rate limiting. Key format: `rate:signup:{ip}` with 60-second TTL.

### Project Structure Notes

- Backend API routes: `src/api/v1/auth/` (register, google, verify-email endpoints)
- Database models: `src/models/user.py`
- Database migrations: `alembic/versions/`
- Frontend pages: `src/pages/signup/`, `src/pages/verify-email/`
- Email templates: `src/templates/email/`
- This is the first feature story — establish conventions for directory structure, error handling patterns, and test organization that subsequent stories will follow.

### Testing Standards

- Backend: Pytest with async test client (httpx), PostgreSQL test database with transaction rollback per test
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- Security tests explicitly required per architecture threat model [Source: docs/architecture/architecture.md#Security-Threat-Model]

### References

- [Source: docs/planning/prd.md#User-Account-&-Access-Management] — FR1 definition
- [Source: docs/planning/prd.md#Compliance-&-Security-Requirements] — Password policy, encryption, session management
- [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Architecture] — NextAuth/OAuth flow, JWT, session management, RBAC matrix
- [Source: docs/tech-specs/tech-spec-epic-1.md#Multi-Tenancy-Architecture] — Schema isolation, public.users table
- [Source: docs/architecture/architecture.md#Technology-Stack] — Vite+React, FastAPI, PostgreSQL, Redis, SendGrid/SES
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — SQL injection prevention, credential logging prohibition, SSRF protection
- [Source: docs/epics/epics.md#Story-1.1] — Acceptance criteria source

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-01 | Story drafted from epics, PRD, tech spec, and architecture | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-1-user-account-creation.context.xml

### Agent Model Used

Claude Opus 4.5

### Debug Log References

### Completion Notes List

### File List
