/**
 * Security Settings Page
 * Story: 1-5-login-session-management (Sessions — AC7, AC8)
 * Story: 1-7-two-factor-authentication-totp (MFA — AC1–AC4, AC7, AC8)
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Monitor, Loader2, Trash2, LogOut, Shield, ShieldCheck,
  Copy, Download, AlertTriangle, Eye, EyeOff,
} from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, userApi, ApiError, SessionInfo } from '@/lib/api'

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function parseDevice(userAgent: string | null): string {
  if (!userAgent) return 'Unknown device'
  if (/Mobile|Android|iPhone|iPad/.test(userAgent)) return 'Mobile device'
  if (/Windows/.test(userAgent)) return 'Windows PC'
  if (/Mac OS/.test(userAgent)) return 'Mac'
  if (/Linux/.test(userAgent)) return 'Linux PC'
  return 'Unknown device'
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Session row
// ---------------------------------------------------------------------------
function SessionRow({
  session,
  onRevoke,
  revoking,
}: {
  session: SessionInfo
  onRevoke: (id: string) => void
  revoking: boolean
}) {
  const device = session.device_name || parseDevice(session.user_agent)

  return (
    <div
      className="flex items-start justify-between gap-4 rounded-lg border border-border px-4 py-3"
      data-testid={`session-row-${session.session_id}`}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex-shrink-0 mt-0.5 h-9 w-9 rounded-full bg-secondary flex items-center justify-center">
          <Monitor className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium truncate">{device}</span>
            {session.is_current && (
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                Current
              </span>
            )}
          </div>
          {session.ip && (
            <p className="text-xs text-muted-foreground mt-0.5">IP: {session.ip}</p>
          )}
          <p className="text-xs text-muted-foreground">
            Started: {formatDate(session.created_at)}
          </p>
        </div>
      </div>

      {!session.is_current && (
        <Button
          variant="ghost"
          size="sm"
          className="flex-shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
          disabled={revoking}
          onClick={() => onRevoke(session.session_id)}
          aria-label={`Revoke session on ${device}`}
          data-testid={`revoke-btn-${session.session_id}`}
        >
          {revoking ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </Button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Backup codes display (used in both setup flow and regenerate flow)
// ---------------------------------------------------------------------------
function BackupCodesModal({
  codes,
  saved,
  onSavedChange,
  onDone,
  title = 'Save Your Backup Codes',
}: {
  codes: string[]
  saved: boolean
  onSavedChange: (v: boolean) => void
  onDone: () => void
  title?: string
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(codes.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const blob = new Blob(
      [`QUALISYS — Backup Codes\nGenerated: ${new Date().toLocaleString()}\n\n${codes.join('\n')}\n\nEach code can only be used once.`],
      { type: 'text/plain' },
    )
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'qualisys-backup-codes.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      data-testid="backup-codes-modal"
    >
      <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-lg">
        <h3 className="text-lg font-semibold mb-1">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Save these codes in a safe place. Each code can only be used once.
        </p>

        {/* Code grid */}
        <div
          className="grid grid-cols-2 gap-2 mb-4 p-3 rounded-md bg-secondary font-mono text-sm"
          data-testid="backup-codes-list"
        >
          {codes.map((code) => (
            <span key={code} className="text-center tracking-widest py-1">
              {code}
            </span>
          ))}
        </div>

        <div className="flex gap-2 mb-6">
          <Button variant="outline" size="sm" className="flex-1" onClick={handleDownload} data-testid="download-codes-btn">
            <Download className="mr-2 h-4 w-4" />
            Download
          </Button>
          <Button variant="outline" size="sm" className="flex-1" onClick={handleCopy} data-testid="copy-codes-btn">
            <Copy className="mr-2 h-4 w-4" />
            {copied ? 'Copied!' : 'Copy'}
          </Button>
        </div>

        <label className="flex items-start gap-3 cursor-pointer mb-4" data-testid="codes-saved-label">
          <input
            type="checkbox"
            checked={saved}
            onChange={(e) => onSavedChange(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-border accent-primary"
            data-testid="codes-saved-checkbox"
          />
          <span className="text-sm text-muted-foreground">
            I have saved these codes in a safe place
          </span>
        </label>

        <Button
          className="w-full"
          disabled={!saved}
          onClick={onDone}
          data-testid="backup-codes-done-btn"
        >
          Done
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Password confirmation dialog (used for disable + regenerate)
// ---------------------------------------------------------------------------
function PasswordConfirmDialog({
  title,
  description,
  confirmLabel,
  confirmVariant = 'destructive',
  loading,
  error,
  onConfirm,
  onCancel,
  testIdPrefix,
}: {
  title: string
  description: string
  confirmLabel: string
  confirmVariant?: 'default' | 'destructive'
  loading: boolean
  error: string | null
  onConfirm: (password: string) => void
  onCancel: () => void
  testIdPrefix: string
}) {
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      data-testid={`${testIdPrefix}-dialog`}
    >
      <div className="w-full max-w-sm rounded-xl border border-border bg-background p-6 shadow-lg">
        <h3 className="text-lg font-semibold mb-1">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{description}</p>

        {error && (
          <div
            role="alert"
            className="mb-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive"
            data-testid={`${testIdPrefix}-error`}
          >
            {error}
          </div>
        )}

        <div className="mb-4">
          <Label htmlFor={`${testIdPrefix}-pw`} className="sr-only">
            Current Password
          </Label>
          <div className="relative">
            <Input
              id={`${testIdPrefix}-pw`}
              type={showPw ? 'text' : 'password'}
              placeholder="Enter your current password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              onKeyDown={(e) => e.key === 'Enter' && password && onConfirm(password)}
              data-testid={`${testIdPrefix}-pw-input`}
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShowPw((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showPw ? 'Hide password' : 'Show password'}
            >
              {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1"
            disabled={loading}
            onClick={onCancel}
            data-testid={`${testIdPrefix}-cancel-btn`}
          >
            Cancel
          </Button>
          <Button
            variant={confirmVariant}
            className="flex-1"
            disabled={!password || loading}
            onClick={() => onConfirm(password)}
            data-testid={`${testIdPrefix}-confirm-btn`}
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MFA Setup flow (inline, replaces "Enable 2FA" button)
// ---------------------------------------------------------------------------
type MfaSetupStep = 'qr' | 'backup-codes'

function MfaSetupFlow({
  qrUri,
  secret,
  onConfirm,
  onConfirmSuccess,
  onCancel,
}: {
  qrUri: string
  secret: string
  onConfirm: (code: string) => Promise<string[]>
  onConfirmSuccess: () => void
  onCancel: () => void
}) {
  const [step, setStep] = useState<MfaSetupStep>('qr')
  const [code, setCode] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const [confirmLoading, setConfirmLoading] = useState(false)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [backupCodes, setBackupCodes] = useState<string[]>([])
  const [backupSaved, setBackupSaved] = useState(false)
  const codeRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    codeRef.current?.focus()
  }, [])

  const handleConfirm = async () => {
    if (code.length !== 6) return
    setConfirmLoading(true)
    setConfirmError(null)
    try {
      const codes = await onConfirm(code)
      setBackupCodes(codes)
      setStep('backup-codes')
    } catch (err) {
      setConfirmError(
        err instanceof ApiError ? err.message : 'Invalid code. Please try again.',
      )
    } finally {
      setConfirmLoading(false)
    }
  }

  if (step === 'backup-codes') {
    return (
      <BackupCodesModal
        codes={backupCodes}
        saved={backupSaved}
        onSavedChange={setBackupSaved}
        onDone={onConfirmSuccess}
      />
    )
  }

  return (
    <div
      className="mt-4 rounded-lg border border-border p-5 space-y-5"
      data-testid="mfa-setup-flow"
    >
      <div>
        <p className="text-sm font-medium mb-1">
          1. Scan this QR code with your authenticator app
        </p>
        <p className="text-xs text-muted-foreground mb-3">
          Compatible with Google Authenticator, Authy, Microsoft Authenticator, and 1Password.
        </p>
        <div
          className="inline-block rounded-lg border border-border p-3 bg-white"
          data-testid="mfa-qr-code"
        >
          <QRCodeSVG value={qrUri} size={160} level="M" />
        </div>
      </div>

      {/* Manual secret entry fallback */}
      <div>
        <button
          type="button"
          className="text-xs text-primary underline underline-offset-2"
          onClick={() => setShowSecret((v) => !v)}
          data-testid="toggle-manual-secret"
        >
          {showSecret ? 'Hide manual entry key' : "Can't scan? Enter key manually"}
        </button>
        {showSecret && (
          <div
            className="mt-2 p-2 rounded-md bg-secondary font-mono text-sm tracking-widest break-all select-all"
            data-testid="mfa-manual-secret"
          >
            {secret}
          </div>
        )}
      </div>

      {/* Confirm code input */}
      <div>
        <p className="text-sm font-medium mb-1">
          2. Enter the 6-digit code from your app to confirm setup
        </p>
        {confirmError && (
          <div
            role="alert"
            className="mb-2 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive"
            data-testid="setup-confirm-error"
          >
            {confirmError}
          </div>
        )}
        <div className="flex gap-2 items-center">
          <Input
            ref={codeRef}
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={6}
            placeholder="000000"
            value={code}
            onChange={(e) => {
              const val = e.target.value.replace(/\D/g, '').slice(0, 6)
              setCode(val)
            }}
            disabled={confirmLoading}
            className="max-w-[140px] font-mono text-lg tracking-widest text-center"
            data-testid="setup-totp-input"
          />
          <Button
            onClick={handleConfirm}
            disabled={code.length !== 6 || confirmLoading}
            data-testid="setup-confirm-btn"
          >
            {confirmLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verify & Enable'}
          </Button>
          <Button variant="ghost" onClick={onCancel} disabled={confirmLoading} data-testid="setup-cancel-btn">
            Cancel
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MFA Section
// ---------------------------------------------------------------------------
type MfaStatus = {
  enabled: boolean
  enabled_at: string | null
  backup_codes_remaining: number
}

function MfaSection() {
  const [mfaStatus, setMfaStatus] = useState<MfaStatus | null>(null)
  const [mfaLoading, setMfaLoading] = useState(true)
  const [mfaError, setMfaError] = useState<string | null>(null)

  // Setup flow
  const [setupData, setSetupData] = useState<{
    qr_uri: string; secret: string; setup_token: string
  } | null>(null)
  const [setupStartLoading, setSetupStartLoading] = useState(false)
  const [setupStartError, setSetupStartError] = useState<string | null>(null)

  // Disable dialog
  const [showDisable, setShowDisable] = useState(false)
  const [disableLoading, setDisableLoading] = useState(false)
  const [disableError, setDisableError] = useState<string | null>(null)

  // Regen dialog
  const [showRegen, setShowRegen] = useState(false)
  const [regenLoading, setRegenLoading] = useState(false)
  const [regenError, setRegenError] = useState<string | null>(null)
  const [regenCodes, setRegenCodes] = useState<string[]>([])
  const [regenSaved, setRegenSaved] = useState(false)

  const refreshStatus = () => {
    setMfaLoading(true)
    authApi
      .mfaStatus()
      .then((data) => setMfaStatus(data))
      .catch((err) => {
        setMfaError(err instanceof ApiError ? err.message : 'Failed to load 2FA status.')
      })
      .finally(() => setMfaLoading(false))
  }

  useEffect(() => {
    refreshStatus()
  }, [])

  const handleEnableSetup = async () => {
    setSetupStartError(null)
    setSetupStartLoading(true)
    try {
      const data = await authApi.mfaSetup()
      setSetupData(data)
    } catch (err) {
      setSetupStartError(
        err instanceof ApiError ? err.message : 'Failed to initiate 2FA setup.',
      )
    } finally {
      setSetupStartLoading(false)
    }
  }

  const handleSetupConfirm = async (code: string): Promise<string[]> => {
    if (!setupData) throw new Error('No setup data')
    const result = await authApi.mfaSetupConfirm(setupData.setup_token, code)
    return result.backup_codes
  }

  const handleSetupSuccess = () => {
    setSetupData(null)
    refreshStatus()
  }

  const handleSetupCancel = () => {
    setSetupData(null)
    setSetupStartError(null)
  }

  const handleDisable = async (password: string) => {
    setDisableLoading(true)
    setDisableError(null)
    try {
      await authApi.mfaDisable(password)
      setShowDisable(false)
      refreshStatus()
    } catch (err) {
      setDisableError(
        err instanceof ApiError ? err.message : 'Failed to disable 2FA.',
      )
    } finally {
      setDisableLoading(false)
    }
  }

  const handleRegen = async (password: string) => {
    setRegenLoading(true)
    setRegenError(null)
    try {
      const result = await authApi.mfaRegenerateCodes(password)
      setRegenCodes(result.backup_codes)
      setShowRegen(false)
      setRegenSaved(false)
      // Show codes modal inline (reuse BackupCodesModal after closing regen dialog)
    } catch (err) {
      setRegenError(
        err instanceof ApiError ? err.message : 'Failed to regenerate backup codes.',
      )
    } finally {
      setRegenLoading(false)
    }
  }

  const handleRegenCodesDone = () => {
    setRegenCodes([])
    refreshStatus()
  }

  if (mfaLoading) {
    return (
      <div className="flex justify-center py-6" data-testid="mfa-status-loading">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (mfaError) {
    return (
      <p className="text-sm text-destructive" data-testid="mfa-status-error">
        {mfaError}
      </p>
    )
  }

  const enabled = mfaStatus?.enabled ?? false
  const lowCodes = enabled && (mfaStatus?.backup_codes_remaining ?? 10) < 3

  return (
    <div data-testid="mfa-section">
      {/* Status summary */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            {enabled ? (
              <ShieldCheck className="h-4 w-4 text-green-600" />
            ) : (
              <Shield className="h-4 w-4 text-muted-foreground" />
            )}
            <span
              className={`text-sm font-medium px-2 py-0.5 rounded ${
                enabled
                  ? 'bg-green-100 text-green-700'
                  : 'bg-secondary text-muted-foreground'
              }`}
              data-testid="mfa-status-badge"
            >
              {enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          {enabled && mfaStatus?.enabled_at && (
            <p className="text-xs text-muted-foreground" data-testid="mfa-enabled-at">
              Enabled on {formatDate(mfaStatus.enabled_at)}
            </p>
          )}
          {enabled && (
            <p
              className={`text-xs mt-0.5 ${lowCodes ? 'text-amber-600 font-medium' : 'text-muted-foreground'}`}
              data-testid="mfa-backup-count"
            >
              {lowCodes && <AlertTriangle className="inline h-3 w-3 mr-1" />}
              {mfaStatus?.backup_codes_remaining ?? 0} backup codes remaining
              {lowCodes && ' — consider regenerating'}
            </p>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {enabled ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { setRegenError(null); setShowRegen(true) }}
                data-testid="regen-codes-btn"
              >
                Regenerate Backup Codes
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
                onClick={() => { setDisableError(null); setShowDisable(true) }}
                data-testid="disable-2fa-btn"
              >
                Disable 2FA
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={handleEnableSetup}
              disabled={setupStartLoading || !!setupData}
              data-testid="enable-2fa-btn"
            >
              {setupStartLoading ? (
                <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Setting up…</>
              ) : (
                'Enable 2FA'
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Setup start error */}
      {setupStartError && (
        <div
          role="alert"
          className="mt-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive"
          data-testid="setup-start-error"
        >
          {setupStartError}
        </div>
      )}

      {/* Setup flow */}
      {setupData && (
        <MfaSetupFlow
          qrUri={setupData.qr_uri}
          secret={setupData.secret}
          onConfirm={handleSetupConfirm}
          onConfirmSuccess={handleSetupSuccess}
          onCancel={handleSetupCancel}
        />
      )}

      {/* Disable dialog */}
      {showDisable && (
        <PasswordConfirmDialog
          title="Disable Two-Factor Authentication"
          description="Enter your current password to confirm. This will remove 2FA protection from your account."
          confirmLabel="Disable 2FA"
          confirmVariant="destructive"
          loading={disableLoading}
          error={disableError}
          onConfirm={handleDisable}
          onCancel={() => setShowDisable(false)}
          testIdPrefix="disable-2fa"
        />
      )}

      {/* Regenerate codes dialog */}
      {showRegen && (
        <PasswordConfirmDialog
          title="Regenerate Backup Codes"
          description="Enter your current password to confirm. All existing backup codes will be invalidated."
          confirmLabel="Regenerate"
          loading={regenLoading}
          error={regenError}
          onConfirm={handleRegen}
          onCancel={() => setShowRegen(false)}
          testIdPrefix="regen-codes"
        />
      )}

      {/* New codes from regeneration */}
      {regenCodes.length > 0 && (
        <BackupCodesModal
          title="New Backup Codes"
          codes={regenCodes}
          saved={regenSaved}
          onSavedChange={setRegenSaved}
          onDone={handleRegenCodesDone}
        />
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Change Password section (AC5 — local accounts only)
// ---------------------------------------------------------------------------
function ChangePasswordSection({ authProvider }: { authProvider: string | null }) {
  const navigate = useNavigate()
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Password strength — reuse same rules as signup (min 12 chars, at least one each: upper, lower, digit, special)
  const getStrength = (pw: string): { score: number; label: string; color: string } => {
    let score = 0
    if (pw.length >= 12) score++
    if (/[A-Z]/.test(pw)) score++
    if (/[a-z]/.test(pw)) score++
    if (/[0-9]/.test(pw)) score++
    if (/[^A-Za-z0-9]/.test(pw)) score++
    const labels = ['', 'Very weak', 'Weak', 'Fair', 'Good', 'Strong']
    const colors = ['', 'bg-red-500', 'bg-orange-500', 'bg-yellow-500', 'bg-blue-500', 'bg-green-500']
    return { score, label: labels[score] ?? '', color: colors[score] ?? '' }
  }

  const strength = newPw ? getStrength(newPw) : null
  const canSubmit = currentPw && newPw && confirmPw && !saving

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPw !== confirmPw) {
      setSaveError('New passwords do not match.')
      return
    }
    setSaving(true)
    setSaveError(null)
    try {
      await userApi.changePassword({
        current_password: currentPw,
        new_password: newPw,
        confirm_new_password: confirmPw,
      })
      navigate('/login', { replace: true, state: { message: 'Password changed successfully. Please log in with your new password.' } })
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Failed to change password.')
      setSaving(false)
    }
  }

  // AC5: hidden while loading (null) or for Google-only users
  if (authProvider === null) return null
  if (authProvider === 'google') return null

  return (
    <section className="mb-10" data-testid="change-password-section">
      <h3 className="text-lg font-medium mb-1">Change Password</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Update your password. You will be logged out of all devices after changing.
      </p>

      <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
        {/* Current password */}
        <div>
          <Label htmlFor="current-password">Current Password</Label>
          <div className="relative mt-1">
            <Input
              id="current-password"
              type={showCurrent ? 'text' : 'password'}
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              autoComplete="current-password"
              data-testid="current-password-input"
            />
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setShowCurrent((v) => !v)}
              aria-label={showCurrent ? 'Hide password' : 'Show password'}
              tabIndex={-1}
            >
              {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* New password */}
        <div>
          <Label htmlFor="new-password">New Password</Label>
          <div className="relative mt-1">
            <Input
              id="new-password"
              type={showNew ? 'text' : 'password'}
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              autoComplete="new-password"
              data-testid="new-password-input"
            />
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setShowNew((v) => !v)}
              aria-label={showNew ? 'Hide password' : 'Show password'}
              tabIndex={-1}
            >
              {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {/* Strength bar */}
          {strength && (
            <div className="mt-1.5" data-testid="password-strength">
              <div className="flex gap-1 mb-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <div
                    key={n}
                    className={`h-1 flex-1 rounded-full transition-colors ${
                      n <= strength.score ? strength.color : 'bg-border'
                    }`}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{strength.label}</p>
            </div>
          )}
          <p className="mt-1 text-xs text-muted-foreground">
            Min 12 characters, uppercase, lowercase, number, and special character.
          </p>
        </div>

        {/* Confirm password */}
        <div>
          <Label htmlFor="confirm-password">Confirm New Password</Label>
          <Input
            id="confirm-password"
            type="password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            autoComplete="new-password"
            className="mt-1"
            data-testid="confirm-password-input"
          />
        </div>

        {saveError && (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive"
            data-testid="change-password-error"
          >
            {saveError}
          </div>
        )}

        <Button
          type="submit"
          disabled={!canSubmit}
          data-testid="change-password-submit"
        >
          {saving ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Updating…</>
          ) : (
            'Update Password'
          )}
        </Button>
      </form>
    </section>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SecurityPage() {
  const navigate = useNavigate()
  const [authProvider, setAuthProvider] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [logoutAllLoading, setLogoutAllLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  useEffect(() => {
    // Fetch auth provider to determine if Change Password section is visible
    userApi.getMe().then((data) => setAuthProvider(data.auth_provider)).catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    authApi
      .getSessions()
      .then((data) => {
        if (!cancelled) setSessions(data.sessions)
      })
      .catch((err) => {
        if (!cancelled) {
          setFetchError(
            err instanceof ApiError
              ? err.message
              : 'Failed to load sessions. Please refresh.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleRevoke = async (sessionId: string) => {
    setActionError(null)
    setRevokingId(sessionId)
    try {
      await authApi.revokeSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId))
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : 'Failed to revoke session.',
      )
    } finally {
      setRevokingId(null)
    }
  }

  const handleLogoutAll = async () => {
    setActionError(null)
    setLogoutAllLoading(true)
    try {
      await authApi.logoutAll()
      navigate('/login', { replace: true })
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : 'Failed to log out all devices.',
      )
      setLogoutAllLoading(false)
    }
  }

  return (
    <div className="space-y-0" data-testid="security-page">
      <div className="mb-6">
        <h2 className="text-xl font-semibold">Security</h2>
        <p className="text-muted-foreground text-sm mt-1">
          Manage your password, two-factor authentication, and active sessions.
        </p>
      </div>

      {/* Change Password — AC5 */}
      <ChangePasswordSection authProvider={authProvider} />

      {authProvider !== null && authProvider !== 'google' && <hr className="border-border mb-10" />}

      {/* Two-Factor Authentication — AC1 */}
      <section className="mb-10">
        <h3 className="text-lg font-medium mb-1">Two-Factor Authentication</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Add an extra layer of security to your account by requiring a code from your
          authenticator app at sign-in.
        </p>
        <MfaSection />
      </section>

      <hr className="border-border mb-10" />

      {/* Active sessions — AC7 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium">Active Sessions</h3>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
            disabled={logoutAllLoading || sessions.length === 0}
            onClick={handleLogoutAll}
            data-testid="logout-all-btn"
          >
            {logoutAllLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Logging out…
              </>
            ) : (
              <>
                <LogOut className="mr-2 h-4 w-4" />
                Log out of all devices
              </>
            )}
          </Button>
        </div>

        {actionError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="action-error"
          >
            {actionError}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-10" data-testid="sessions-loading">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : fetchError ? (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="fetch-error"
          >
            {fetchError}
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center" data-testid="no-sessions">
            No active sessions found.
          </p>
        ) : (
          <div className="space-y-3" data-testid="sessions-list">
            {sessions.map((session) => (
              <SessionRow
                key={session.session_id}
                session={session}
                onRevoke={handleRevoke}
                revoking={revokingId === session.session_id}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
