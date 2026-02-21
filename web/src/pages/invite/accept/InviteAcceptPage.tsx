/**
 * Invite Accept Page — Public (unauthenticated)
 * Story: 1-3-team-member-invitation
 * AC: AC4 — token inspection on load; two-path accept (existing user / new user)
 * AC: AC5 — success redirect after accept
 * AC: AC9 — generic error messages; no token info leakage
 */

import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  invitationApi,
  AcceptInviteDetailsResponse,
  ApiError,
} from '@/lib/api'

// ---------------------------------------------------------------------------
// Password policy — mirrors Story 1.1 AC2
// ---------------------------------------------------------------------------

const PASSWORD_MIN = 12
const PASSWORD_POLICY_RE = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{12,}$/

function validatePassword(pw: string): string | null {
  if (pw.length < PASSWORD_MIN) return `Password must be at least ${PASSWORD_MIN} characters.`
  if (!PASSWORD_POLICY_RE.test(pw))
    return 'Password must contain uppercase, lowercase, number, and special character (!@#$%^&*).'
  return null
}

// ---------------------------------------------------------------------------
// Views
// ---------------------------------------------------------------------------

type PageState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'details'; details: AcceptInviteDetailsResponse }
  | { kind: 'success'; orgName: string }

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function InviteAcceptPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [pageState, setPageState] = useState<PageState>({ kind: 'loading' })

  // Form state (new-user path)
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [formErrors, setFormErrors] = useState<Record<string, string>>({})

  // Submission state
  const [accepting, setAccepting] = useState(false)
  const [acceptError, setAcceptError] = useState<string | null>(null)

  // Load invitation details on mount — AC4
  useEffect(() => {
    if (!token) {
      setPageState({ kind: 'error', message: 'Invitation link is missing or invalid.' })
      return
    }

    invitationApi
      .getAcceptDetails(token)
      .then((details) => setPageState({ kind: 'details', details }))
      .catch((err) => {
        // AC9: do not expose token specifics — show generic error
        const msg =
          err instanceof ApiError && err.status !== 500
            ? err.message
            : 'This invitation link is invalid or has expired.'
        setPageState({ kind: 'error', message: msg })
      })
  }, [token])

  // ---------------------------------------------------------------------------
  // Accept — existing user path (AC4: no password re-entry, relies on session)
  // ---------------------------------------------------------------------------

  const handleAcceptExisting = useCallback(async () => {
    setAcceptError(null)
    setAccepting(true)
    try {
      await invitationApi.accept({ token })
      const orgName =
        pageState.kind === 'details' ? pageState.details.org_name : 'the organization'
      setPageState({ kind: 'success', orgName })
    } catch (err) {
      setAcceptError(
        err instanceof ApiError ? err.message : 'Failed to accept invitation. Please try again.',
      )
    } finally {
      setAccepting(false)
    }
  }, [token, pageState])

  // ---------------------------------------------------------------------------
  // Accept — new user path (register + join)
  // ---------------------------------------------------------------------------

  const handleAcceptNew = useCallback(async () => {
    const errors: Record<string, string> = {}

    if (!fullName.trim()) errors.fullName = 'Full name is required.'
    const pwErr = validatePassword(password)
    if (pwErr) errors.password = pwErr
    if (password !== confirmPassword) errors.confirmPassword = 'Passwords do not match.'

    if (Object.keys(errors).length > 0) {
      setFormErrors(errors)
      return
    }
    setFormErrors({})
    setAcceptError(null)
    setAccepting(true)

    try {
      await invitationApi.accept({ token, full_name: fullName.trim(), password })
      const orgName =
        pageState.kind === 'details' ? pageState.details.org_name : 'the organization'
      setPageState({ kind: 'success', orgName })
    } catch (err) {
      setAcceptError(
        err instanceof ApiError ? err.message : 'Failed to create account. Please try again.',
      )
    } finally {
      setAccepting(false)
    }
  }, [token, fullName, password, confirmPassword, pageState])

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (pageState.kind === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center" data-testid="invite-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (pageState.kind === 'error') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div
          className="max-w-md w-full text-center space-y-4"
          data-testid="invite-error"
        >
          <XCircle className="h-12 w-12 text-destructive mx-auto" />
          <h1 className="text-xl font-semibold text-foreground">Invitation Unavailable</h1>
          <p className="text-sm text-muted-foreground" data-testid="invite-error-message">
            {pageState.message}
          </p>
          <Button variant="outline" onClick={() => navigate('/signup')}>
            Create a new account
          </Button>
        </div>
      </div>
    )
  }

  if (pageState.kind === 'success') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-4">
        <div
          className="max-w-md w-full text-center space-y-4"
          data-testid="invite-success"
        >
          <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto" />
          <h1 className="text-xl font-semibold text-foreground">You're in!</h1>
          <p className="text-sm text-muted-foreground">
            You've successfully joined <strong>{pageState.orgName}</strong> on QUALISYS.
          </p>
          <Button onClick={() => navigate('/')}>Go to dashboard</Button>
        </div>
      </div>
    )
  }

  // pageState.kind === 'details'
  const { details } = pageState

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="max-w-md w-full" data-testid="invite-accept-form">
        {/* Branding header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-foreground">QUALISYS</h1>
          <p className="text-sm text-muted-foreground mt-1">AI-Powered Testing Platform</p>
        </div>

        {/* Invitation card */}
        <div className="bg-white rounded-lg shadow-sm border border-border p-6 mb-6">
          <h2 className="text-lg font-semibold text-foreground mb-1">You've been invited</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Join <strong>{details.org_name}</strong> on QUALISYS.
          </p>

          <div className="bg-muted/40 rounded-md px-4 py-3 text-sm space-y-1 mb-6">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Organization</span>
              <span className="font-medium">{details.org_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Your role</span>
              <span className="font-medium capitalize">{details.role}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Invited email</span>
              <span className="font-medium">{details.email}</span>
            </div>
          </div>

          {/* Existing user path — AC4 */}
          {details.user_exists ? (
            <div data-testid="existing-user-path">
              <p className="text-sm text-muted-foreground mb-4">
                You already have a QUALISYS account with{' '}
                <strong>{details.email}</strong>. Click below to join the organization.
              </p>
              {acceptError && (
                <p
                  role="alert"
                  className="mb-3 text-sm text-destructive"
                  data-testid="accept-error"
                >
                  {acceptError}
                </p>
              )}
              <Button
                className="w-full"
                onClick={handleAcceptExisting}
                disabled={accepting}
                data-testid="accept-btn"
              >
                {accepting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Joining…
                  </>
                ) : (
                  'Accept & Join Organization'
                )}
              </Button>
            </div>
          ) : (
            /* New user path — AC4: registration form */
            <div data-testid="new-user-path">
              <p className="text-sm text-muted-foreground mb-4">
                Create your QUALISYS account to accept this invitation.
              </p>

              <div className="space-y-4">
                {/* Email — read-only, pre-filled from token */}
                <div>
                  <Label htmlFor="invite-email">Email</Label>
                  <Input
                    id="invite-email"
                    type="email"
                    value={details.email}
                    readOnly
                    className="mt-1 bg-muted cursor-not-allowed"
                    data-testid="invite-email"
                  />
                </div>

                {/* Full name */}
                <div>
                  <Label htmlFor="invite-full-name">Full name</Label>
                  <Input
                    id="invite-full-name"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Jane Smith"
                    className="mt-1"
                    aria-invalid={!!formErrors.fullName}
                    data-testid="invite-full-name"
                  />
                  {formErrors.fullName && (
                    <p role="alert" className="mt-1 text-xs text-destructive">
                      {formErrors.fullName}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div>
                  <Label htmlFor="invite-password">Password</Label>
                  <Input
                    id="invite-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Min 8 chars, upper + lower + number + symbol"
                    className="mt-1"
                    aria-invalid={!!formErrors.password}
                    data-testid="invite-password"
                  />
                  {formErrors.password && (
                    <p role="alert" className="mt-1 text-xs text-destructive">
                      {formErrors.password}
                    </p>
                  )}
                </div>

                {/* Confirm password */}
                <div>
                  <Label htmlFor="invite-confirm-password">Confirm password</Label>
                  <Input
                    id="invite-confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="mt-1"
                    aria-invalid={!!formErrors.confirmPassword}
                    data-testid="invite-confirm-password"
                  />
                  {formErrors.confirmPassword && (
                    <p role="alert" className="mt-1 text-xs text-destructive">
                      {formErrors.confirmPassword}
                    </p>
                  )}
                </div>
              </div>

              {acceptError && (
                <p
                  role="alert"
                  className="mt-3 text-sm text-destructive"
                  data-testid="accept-error"
                >
                  {acceptError}
                </p>
              )}

              <Button
                className="w-full mt-6"
                onClick={handleAcceptNew}
                disabled={accepting}
                data-testid="accept-btn"
              >
                {accepting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating account…
                  </>
                ) : (
                  'Create Account & Join'
                )}
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
