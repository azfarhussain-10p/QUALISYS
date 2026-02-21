# Story 1.7: Two-Factor Authentication (TOTP)

Status: ready-for-dev

## Story

As a security-conscious user,
I want to enable two-factor authentication with an authenticator app,
so that my account is protected even if my password is compromised.

## Requirements Context

This is the **seventh story** in Epic 1 (Foundation & Administration). It adds optional TOTP-based multi-factor authentication as an additional security layer. This story modifies the login flow (Story 1.5) to include a TOTP challenge step when MFA is enabled, and provides setup/management UI in user security settings. Password reset (Story 1.6) must handle MFA-enabled accounts.

**FRs Covered:**
- FR5 — Users can enable two-factor authentication (TOTP) for their accounts

**Architecture Constraints:**
- Backend: Python 3.11+ / FastAPI with async endpoints
- Frontend: Vite + React 18, Tailwind CSS + shadcn/ui
- Database: PostgreSQL 15+ [Source: docs/architecture/architecture.md#ADR-001]
- Authentication: JWT + refresh tokens in Redis (Story 1.5); MFA challenge at login time [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Flow]
- TOTP: RFC 6238 compliant, 30-second window, 6-digit codes [Source: docs/planning/prd.md#NFR-SEC1]
- Compatible apps: Google Authenticator, Authy, Microsoft Authenticator, 1Password
- Security: TOTP secrets encrypted at rest (AES-256); backup codes stored as bcrypt hashes
- Session: MFA challenge occurs between password validation and JWT issuance [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Flow]

**Dependencies:**
- Story 1.1 (User Account Creation) — user accounts in `public.users`
- Story 1.5 (Login & Session Management) — login flow, JWT issuance, auth middleware
- Story 1.6 (Password Reset Flow) — password reset must handle MFA-enabled accounts (MFA bypassed on reset since user proved email ownership)

## Acceptance Criteria

1. **AC1: Enable 2FA — Settings UI** — User security settings page (`/settings/security`) shows "Two-Factor Authentication" section with current status (Enabled/Disabled). "Enable 2FA" button available when disabled. "Disable 2FA" button available when enabled (requires current password confirmation). Section shows when 2FA was enabled (date) and last used (date).

2. **AC2: TOTP Setup Flow — QR Code** — Clicking "Enable 2FA" initiates setup: system generates TOTP secret (RFC 6238, 160-bit base32-encoded), displays QR code in `otpauth://` URI format containing: issuer ("QUALISYS"), account (user's email), secret, algorithm (SHA1), digits (6), period (30). QR code rendered as SVG (no external service dependency). Manual entry option: displays the secret key as text for users who cannot scan QR codes.

3. **AC3: TOTP Setup Confirmation** — After scanning QR code, user must enter a valid 6-digit TOTP code to confirm setup. System validates the code against the generated secret (±1 time window tolerance for clock drift). On valid code: TOTP secret encrypted (AES-256) and stored in `public.users` (`totp_secret_encrypted`, `totp_enabled_at`). On invalid code: error message "Invalid code. Please try again." with retry (up to 5 attempts). Setup is not complete until confirmation code validates — secret is temporary until confirmed.

4. **AC4: Backup/Recovery Codes** — After successful 2FA setup confirmation, system generates 10 single-use backup codes (8 alphanumeric characters each). Codes displayed once in a modal with: "Save these codes in a safe place. Each code can only be used once.", "Download" button (text file), "Copy" button. Backup codes stored as bcrypt hashes in `public.user_backup_codes` table (`id`, `user_id`, `code_hash`, `used_at`, `created_at`). User must acknowledge they have saved the codes before modal closes ("I have saved these codes" checkbox + "Done" button).

5. **AC5: Login with TOTP Challenge** — When MFA-enabled user logs in with correct password: instead of issuing JWT immediately, system returns HTTP 200 with `{mfa_required: true, mfa_token: string}`. Frontend displays TOTP code entry form (6-digit numeric input with auto-focus, auto-submit on 6th digit). User enters code from authenticator app. System validates TOTP code against stored secret (±1 window). On valid: issue JWT + refresh token (normal login flow continues). On invalid: error message, allow retry (up to 5 attempts per `mfa_token`). `mfa_token` is a short-lived token (5 minutes) that proves password was validated — prevents re-entering password.

6. **AC6: Login with Backup Code** — TOTP entry form includes "Use a backup code" link. Clicking it shows backup code input field (8 alphanumeric characters). System validates against stored backup code hashes. On valid: mark code as used (`used_at = now()`), proceed with login. Each backup code is single-use. When fewer than 3 backup codes remain: show warning "You have X backup codes remaining. Consider generating new ones."

7. **AC7: Disable 2FA** — User can disable 2FA from security settings. Requires current password confirmation for security. On disable: clear `totp_secret_encrypted`, set `totp_enabled_at = null`, delete all unused backup codes. All existing sessions remain valid (no session invalidation needed — they're already authenticated).

8. **AC8: Regenerate Backup Codes** — Security settings page shows "Regenerate Backup Codes" button (only when 2FA is enabled). Requires current password confirmation. On regeneration: delete all existing backup codes (used and unused), generate 10 new codes, display in same modal as initial setup. Useful when user has used most backup codes or suspects compromise.

9. **AC9: Rate Limiting & Security** — TOTP verification rate-limited to 5 attempts per `mfa_token` (5-minute window). Backup code verification rate-limited to 5 attempts per `mfa_token`. After exceeding: `mfa_token` invalidated, user must re-enter password. Brute-force protection: 10 failed MFA attempts per user per hour triggers temporary MFA lockout (1 hour). TOTP secrets encrypted at rest with AES-256 (encryption key in AWS Secrets Manager / Azure Key Vault). Backup codes stored as bcrypt hashes (not plaintext).

10. **AC10: Audit Trail** — All MFA actions logged: 2FA enabled (user_id, timestamp), 2FA disabled (user_id, timestamp), TOTP code verified (user_id, success/failure), backup code used (user_id, code_index), backup codes regenerated (user_id), MFA lockout triggered (user_id). Audit entries include IP address and user_agent.

## Tasks / Subtasks

- [ ] **Task 1: Database Schema Updates** (AC: #3, #4)
  - [ ] 1.1 Add columns to `public.users` via Alembic migration: `totp_secret_encrypted` (bytea, nullable), `totp_enabled_at` (timestamptz, nullable), `mfa_lockout_until` (timestamptz, nullable)
  - [ ] 1.2 Create `public.user_backup_codes` table: `id` (UUID PK), `user_id` (UUID FK), `code_hash` (varchar 255), `used_at` (timestamptz nullable), `created_at` (timestamptz)
  - [ ] 1.3 Create index on `(user_id)` for backup codes lookup
  - [ ] 1.4 Write migration rollback script

- [ ] **Task 2: TOTP Service** (AC: #2, #3, #5, #9)
  - [ ] 2.1 Create `TOTPService` class: `generate_secret()`, `generate_qr_uri()`, `verify_code()`, `encrypt_secret()`, `decrypt_secret()`
  - [ ] 2.2 Implement TOTP secret generation: 160-bit random, base32-encoded (RFC 6238)
  - [ ] 2.3 Implement QR URI: `otpauth://totp/QUALISYS:{email}?secret={secret}&issuer=QUALISYS&algorithm=SHA1&digits=6&period=30`
  - [ ] 2.4 Implement TOTP verification with ±1 time window tolerance (accepts codes from previous, current, and next 30-second period)
  - [ ] 2.5 Implement AES-256 encryption/decryption for TOTP secrets (key from Secrets Manager)

- [ ] **Task 3: Backup Code Service** (AC: #4, #6, #8)
  - [ ] 3.1 Create `BackupCodeService` class: `generate_codes()`, `verify_code()`, `regenerate_codes()`, `get_remaining_count()`
  - [ ] 3.2 Implement code generation: 10 codes, 8 alphanumeric chars each (`secrets.token_hex(4)` formatted)
  - [ ] 3.3 Store codes as bcrypt hashes in `public.user_backup_codes`
  - [ ] 3.4 Implement verification: hash input, compare against unused codes, mark used on match
  - [ ] 3.5 Implement regeneration: delete all existing codes, generate 10 new

- [ ] **Task 4: MFA Integration with Login Flow** (AC: #5, #6, #9)
  - [ ] 4.1 Modify `AuthService.login_with_password()` (Story 1.5): after password validation, check if user has MFA enabled (`totp_enabled_at IS NOT NULL`)
  - [ ] 4.2 If MFA enabled: return `{mfa_required: true, mfa_token: string}` instead of JWT. `mfa_token` is short-lived (5 min, stored in Redis: `mfa:{token_hash} → {user_id, device_id, remember_me}`)
  - [ ] 4.3 Create `POST /api/v1/auth/mfa/verify` — accepts `{mfa_token, totp_code}`, validates TOTP, issues JWT + refresh tokens
  - [ ] 4.4 Create `POST /api/v1/auth/mfa/backup` — accepts `{mfa_token, backup_code}`, validates backup code, issues JWT + refresh tokens
  - [ ] 4.5 Implement MFA lockout: 10 failed attempts/user/hour → `mfa_lockout_until` set, reject all MFA attempts until lockout expires

- [ ] **Task 5: FastAPI MFA Management Endpoints** (AC: #1, #2, #3, #7, #8, #10)
  - [ ] 5.1 Create `POST /api/v1/auth/mfa/setup` — generates TOTP secret, returns QR URI + manual secret (temporary, not yet stored permanently)
  - [ ] 5.2 Create `POST /api/v1/auth/mfa/setup/confirm` — accepts `{totp_code}`, validates against temp secret, stores encrypted secret, generates backup codes, returns codes
  - [ ] 5.3 Create `POST /api/v1/auth/mfa/disable` — accepts `{password}`, validates, clears TOTP data and backup codes
  - [ ] 5.4 Create `POST /api/v1/auth/mfa/backup-codes/regenerate` — accepts `{password}`, regenerates backup codes, returns new codes
  - [ ] 5.5 Create `GET /api/v1/auth/mfa/status` — returns MFA enabled status, enabled date, last used, remaining backup codes count
  - [ ] 5.6 Audit log all MFA operations

- [ ] **Task 6: React UI — MFA Setup & Management** (AC: #1, #2, #3, #4, #7, #8)
  - [ ] 6.1 Add "Two-Factor Authentication" section to `/settings/security` page
  - [ ] 6.2 Display MFA status: enabled/disabled badge, enabled date, last used
  - [ ] 6.3 "Enable 2FA" button → triggers setup flow
  - [ ] 6.4 Setup step 1: QR code display (SVG rendered via `qrcode` library) + manual secret text fallback
  - [ ] 6.5 Setup step 2: 6-digit code input for confirmation (auto-focus, numeric only)
  - [ ] 6.6 Setup step 3: backup codes modal (display codes, Download button, Copy button, "I have saved these codes" checkbox)
  - [ ] 6.7 "Disable 2FA" button with password confirmation dialog
  - [ ] 6.8 "Regenerate Backup Codes" button with password confirmation, shows new codes in modal
  - [ ] 6.9 Show remaining backup codes count with warning when < 3

- [ ] **Task 7: React UI — MFA Login Challenge** (AC: #5, #6)
  - [ ] 7.1 Create MFA challenge page/modal that appears after password validation when `mfa_required: true`
  - [ ] 7.2 6-digit TOTP code input: numeric-only, auto-focus, auto-submit on 6th digit (shadcn/ui InputOTP or custom)
  - [ ] 7.3 "Use a backup code" link → switches to 8-character alphanumeric input
  - [ ] 7.4 Error handling: invalid code, rate limited, lockout
  - [ ] 7.5 5-minute timeout: if `mfa_token` expires, redirect to password entry

- [ ] **Task 8: Testing** (AC: all)
  - [ ] 8.1 Unit tests: TOTP secret generation, QR URI formatting, TOTP code verification (valid, expired, ±1 window), AES encryption/decryption
  - [ ] 8.2 Unit tests: backup code generation, verification (valid, used, invalid), regeneration
  - [ ] 8.3 Integration tests: setup flow — generate secret, confirm with valid code, verify stored encrypted
  - [ ] 8.4 Integration tests: login with MFA — password → mfa_required → TOTP verify → JWT issued
  - [ ] 8.5 Integration tests: login with backup code — password → mfa_required → backup code → JWT issued, code marked used
  - [ ] 8.6 Integration tests: disable MFA — password confirmation, TOTP data cleared, backup codes deleted, subsequent login skips MFA
  - [ ] 8.7 Integration tests: rate limiting — 5 failed TOTP attempts invalidate mfa_token, 10 failures trigger lockout
  - [ ] 8.8 Integration tests: backup code depletion warning at < 3 remaining
  - [ ] 8.9 Security tests: TOTP secret encrypted in DB (not plaintext), backup codes stored as bcrypt hash, mfa_token is short-lived and single-purpose
  - [ ] 8.10 Frontend tests: QR code display, code input auto-submit, backup code toggle, setup flow steps, disable confirmation, remaining codes warning

- [ ] **Task 9: Security Review** (AC: #9, #10)
  - [ ] 9.1 Verify TOTP secrets encrypted with AES-256 (key from Secrets Manager, not in code)
  - [ ] 9.2 Verify backup codes stored as bcrypt hashes (not plaintext or reversible encryption)
  - [ ] 9.3 Verify mfa_token is short-lived (5 min), single-purpose, stored as hash in Redis
  - [ ] 9.4 Verify ±1 time window tolerance (not wider — prevents replay with old codes)
  - [ ] 9.5 Verify rate limiting prevents brute-force on 6-digit TOTP (10^6 space)
  - [ ] 9.6 Verify QR code rendered locally (no external API call that could leak secret)
  - [ ] 9.7 Verify disable/regenerate require password confirmation (prevent CSRF-style attacks)
  - [ ] 9.8 Verify audit trail captures all MFA lifecycle events

## Dev Notes

### Architecture Patterns

- **TOTP (RFC 6238):** Time-based one-time password. Uses HMAC-SHA1 with a shared secret and current time (30-second intervals) to generate 6-digit codes. Compatible with Google Authenticator, Authy, Microsoft Authenticator, 1Password.
- **Two-step login:** Login flow becomes: (1) validate password → (2) if MFA enabled, return `mfa_token` → (3) validate TOTP/backup code → (4) issue JWT. The `mfa_token` is a short-lived Redis-stored token that proves password was validated, avoiding re-entry.
- **Secret encryption at rest:** TOTP secrets encrypted with AES-256 before storage. Encryption key in AWS Secrets Manager / Azure Key Vault (Story 0.7). This prevents secret leakage even if DB is compromised.
- **Backup codes as bcrypt hashes:** Backup codes stored as one-way hashes (like passwords). Cannot be recovered — only verified. This prevents leakage from DB compromise.
- **Temporary secret during setup:** TOTP secret generated on setup initiation is stored temporarily (Redis, 10-minute TTL) until the user confirms with a valid code. Only then is it permanently stored in the DB. This prevents partial setup states.
- **Password reset and MFA:** After password reset (Story 1.6), user is redirected to login. If MFA is enabled, they still need TOTP code. This maintains MFA protection even after password reset. However, backup codes can be used if authenticator app is unavailable.

### Project Structure Notes

- TOTP service: `src/services/totp_service.py`
- Backup code service: `src/services/backup_code_service.py`
- MFA API routes: `src/api/v1/auth/mfa/` (setup, confirm, verify, backup, disable, regenerate, status)
- Frontend: `src/pages/settings/security/` (MFA section), `src/components/auth/MFAChallenge/` (login challenge)
- Modify: `src/services/auth_service.py` (add MFA check to login flow), `src/api/v1/auth/login` (return mfa_required)
- Builds on: Story 1.5 (login flow, JWT issuance, Redis sessions), Story 1.6 (password reset interaction)

### Testing Standards

- Backend: Pytest with async test client, PostgreSQL test database with per-test transaction rollback
- Frontend: Vitest + React Testing Library
- Coverage target: 80%+ for new code
- TOTP tests: use known secret + known timestamp to generate deterministic codes
- AES encryption tests: verify round-trip (encrypt → decrypt = original)
- Redis required for mfa_token and rate limiting tests

### Learnings from Previous Story

**From Story 1-6-password-reset-flow (Status: ready-for-dev)**

Previous story not yet implemented — no dev agent learnings available. However, Story 1.6's specification establishes:

- **Password confirmation pattern** — Story 1.6 validates passwords server-side. This story reuses password confirmation for disable/regenerate operations.
- **Public.users table** — This story adds columns: `totp_secret_encrypted`, `totp_enabled_at`, `mfa_lockout_until`. Must coordinate with Story 1.6's password_hash update.
- **Auth endpoint router** — `src/api/v1/auth/` already has login, refresh, logout, forgot-password, reset-password. This story adds `/mfa/*` routes to the same router.
- **Audit logging pattern** — established in Stories 1.3-1.6, reused for MFA events.

[Source: docs/stories/1-6-password-reset-flow.md]

### References

- [Source: docs/planning/prd.md#User-Account-&-Access-Management] — FR5 (enable 2FA TOTP)
- [Source: docs/planning/prd.md#NFR-SEC1] — MFA: support TOTP-based two-factor authentication
- [Source: docs/tech-specs/tech-spec-epic-1.md#Session-Management] — MFA (TOTP) challenge at login time
- [Source: docs/tech-specs/tech-spec-epic-1.md#Authentication-Flow] — Mermaid: MFA Check → TOTP Verification → JWT
- [Source: docs/architecture/architecture.md#Security-Threat-Model] — Token security, audit trails
- [Source: docs/epics/epics.md#Story-1.7] — AC source: QR code, 6-digit code, backup codes, login challenge
- [Source: docs/stories/1-5-login-session-management.md] — Login flow, AuthService, JWT issuance, Redis session keys
- [Source: docs/stories/1-6-password-reset-flow.md] — Password reset interaction with MFA

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-02-17 | Story drafted from epics, PRD, tech spec, architecture, and predecessor stories | SM Agent (Bob) |

## Dev Agent Record

### Context Reference

- docs/stories/1-7-two-factor-authentication-totp.context.xml

### Agent Model Used

Claude Opus 4.6

### Debug Log References

### Completion Notes List

### File List
