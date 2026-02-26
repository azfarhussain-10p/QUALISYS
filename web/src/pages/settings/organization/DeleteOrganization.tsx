/**
 * Delete Organization — Danger Zone section
 * Story: 1-13-data-export-org-deletion
 * AC: #3, #4, #6 — multi-step confirmation: warning → type org name → 2FA/password
 * Owner only. Not shown to Admin.
 */

import { useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { exportApi, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Step = 'idle' | 'warning' | 'name-confirm' | 'verification' | 'deleting' | 'deleted'

interface DeleteOrgProps {
  orgId: string
  orgName: string
  /** Whether the current user has MFA (TOTP) enabled */
  mfaEnabled: boolean
  /** Current user's role — section only renders for 'owner' */
  userRole: string
  /** Callback when deletion completes (redirect parent) */
  onDeleted?: () => void
}

// ---------------------------------------------------------------------------
// DeleteOrganization Component
// ---------------------------------------------------------------------------

export default function DeleteOrganization({
  orgId,
  orgName,
  mfaEnabled,
  userRole,
  onDeleted,
}: DeleteOrgProps) {
  const [step, setStep] = useState<Step>('idle')
  const [nameInput, setNameInput] = useState('')
  const [verificationInput, setVerificationInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  // Owner only
  if (userRole !== 'owner') return null

  const nameMatches = nameInput === orgName
  const verificationFilled = verificationInput.trim().length > 0

  const handleOpenWarning = () => {
    setStep('warning')
    setError(null)
    setNameInput('')
    setVerificationInput('')
  }

  const handleCancel = () => {
    setStep('idle')
    setError(null)
    setNameInput('')
    setVerificationInput('')
  }

  const handleNameConfirm = () => {
    if (!nameMatches) return
    setStep('verification')
  }

  const handleDelete = async () => {
    if (!verificationFilled) return
    setDeleting(true)
    setError(null)
    try {
      await exportApi.deleteOrg(orgId, {
        org_name_confirmation: nameInput,
        ...(mfaEnabled
          ? { totp_code: verificationInput }
          : { password: verificationInput }),
      })
      setStep('deleted')
      onDeleted?.()
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Failed to delete organization. Please try again.'
      setError(msg)
      setDeleting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render: idle
  // ---------------------------------------------------------------------------
  if (step === 'idle') {
    return (
      <section
        data-testid="danger-zone"
        className="border border-red-200 rounded-lg p-6 space-y-4"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-red-600" />
          <h3 className="text-base font-semibold text-red-700">Danger Zone</h3>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">Delete this organization</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Permanently delete all organization data. This action cannot be undone.
            </p>
          </div>
          <Button
            data-testid="delete-org-btn"
            variant="destructive"
            onClick={handleOpenWarning}
          >
            Delete Organization
          </Button>
        </div>
      </section>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: deleted state
  // ---------------------------------------------------------------------------
  if (step === 'deleted') {
    return (
      <div
        data-testid="deletion-initiated"
        className="text-center py-8 space-y-2"
      >
        <AlertTriangle className="h-8 w-8 text-red-500 mx-auto" />
        <h3 className="text-lg font-semibold text-foreground">Organization deletion initiated</h3>
        <p className="text-sm text-muted-foreground">
          All members will be notified. You will be redirected shortly.
        </p>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render: confirmation dialog (step-based)
  // ---------------------------------------------------------------------------
  return (
    <section
      data-testid="deletion-dialog"
      className="border border-red-300 rounded-lg p-6 bg-red-50 space-y-5"
    >
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-red-600" />
        <h3 className="text-base font-semibold text-red-700">Delete Organization</h3>
      </div>

      {/* Step 1: Warning */}
      {step === 'warning' && (
        <div className="space-y-4" data-testid="step-warning">
          <p className="text-sm text-red-800">
            <strong>Warning:</strong> You are about to permanently delete{' '}
            <strong>{orgName}</strong>. This will delete ALL organization data including
            projects, test cases, test results, and team members.{' '}
            <strong>This action CANNOT be undone.</strong>
          </p>
          <div className="flex gap-3">
            <Button
              data-testid="warning-proceed-btn"
              variant="destructive"
              onClick={() => setStep('name-confirm')}
            >
              I understand, continue
            </Button>
            <Button
              data-testid="warning-cancel-btn"
              variant="outline"
              onClick={handleCancel}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Type org name */}
      {step === 'name-confirm' && (
        <div className="space-y-4" data-testid="step-name-confirm">
          <p className="text-sm text-red-800">
            Please type <strong>{orgName}</strong> exactly to confirm deletion:
          </p>
          <div className="space-y-2">
            <Label htmlFor="org-name-input" className="text-sm">
              Organization name
            </Label>
            <Input
              id="org-name-input"
              data-testid="org-name-input"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              placeholder={orgName}
              className={nameInput && !nameMatches ? 'border-red-400' : ''}
            />
            {nameInput && !nameMatches && (
              <p className="text-xs text-red-600">Name does not match.</p>
            )}
          </div>
          <div className="flex gap-3">
            <Button
              data-testid="name-confirm-btn"
              variant="destructive"
              onClick={handleNameConfirm}
              disabled={!nameMatches}
            >
              Continue
            </Button>
            <Button
              data-testid="name-cancel-btn"
              variant="outline"
              onClick={handleCancel}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: 2FA or password verification */}
      {step === 'verification' && (
        <div className="space-y-4" data-testid="step-verification">
          <p className="text-sm text-red-800">
            {mfaEnabled
              ? 'Enter your authenticator app code to confirm deletion:'
              : 'Enter your password to confirm deletion:'}
          </p>
          <div className="space-y-2">
            <Label htmlFor="verification-input" className="text-sm">
              {mfaEnabled ? '6-digit TOTP code' : 'Password'}
            </Label>
            <Input
              id="verification-input"
              data-testid="verification-input"
              type={mfaEnabled ? 'text' : 'password'}
              value={verificationInput}
              onChange={(e) => setVerificationInput(e.target.value)}
              placeholder={mfaEnabled ? '123456' : '••••••••'}
              maxLength={mfaEnabled ? 6 : undefined}
              inputMode={mfaEnabled ? 'numeric' : undefined}
            />
          </div>

          {error && (
            <p
              data-testid="delete-error"
              className="text-sm text-red-700 bg-red-100 border border-red-200 rounded px-3 py-2"
            >
              {error}
            </p>
          )}

          <div className="flex gap-3">
            <Button
              data-testid="delete-confirm-btn"
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting || !verificationFilled}
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting…
                </>
              ) : (
                'Delete Organization'
              )}
            </Button>
            <Button
              data-testid="verification-cancel-btn"
              variant="outline"
              onClick={handleCancel}
              disabled={deleting}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
