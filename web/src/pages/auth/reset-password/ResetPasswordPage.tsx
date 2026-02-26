/**
 * Reset Password Page
 * Story: 1-6-password-reset-flow
 * AC5 — /reset-password?token validates on load; shows form or error page
 * AC6 — On submit: update password, invalidate sessions, redirect to /login with success banner
 */

import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Password validation — matches Story 1.1 policy (AC5)
// ---------------------------------------------------------------------------
const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(12, 'Password must be at least 12 characters')
      .regex(/[A-Z]/, 'Must contain at least 1 uppercase letter')
      .regex(/[a-z]/, 'Must contain at least 1 lowercase letter')
      .regex(/\d/, 'Must contain at least 1 number')
      .regex(/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`']/, 'Must contain at least 1 special character'),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

// ---------------------------------------------------------------------------
// Password strength indicator — reused from SignupPage (AC5)
// ---------------------------------------------------------------------------
function getPasswordStrength(password: string): { level: number; label: string; color: string } {
  if (!password) return { level: 0, label: '', color: '' }
  let score = 0
  if (password.length >= 12) score++
  if (/[A-Z]/.test(password)) score++
  if (/[a-z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`']/.test(password)) score++

  if (score <= 2) return { level: score, label: 'Weak', color: 'bg-red-500' }
  if (score === 3) return { level: score, label: 'Fair', color: 'bg-yellow-500' }
  if (score === 4) return { level: score, label: 'Good', color: 'bg-blue-500' }
  return { level: score, label: 'Strong', color: 'bg-green-500' }
}

// ---------------------------------------------------------------------------
// Token validation states
// ---------------------------------------------------------------------------
type TokenState = 'validating' | 'valid' | 'expired' | 'used' | 'invalid'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [tokenState, setTokenState] = useState<TokenState>('validating')
  const [maskedEmail, setMaskedEmail] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    mode: 'onChange',
  })

  const passwordValue = watch('new_password', '')
  const strength = getPasswordStrength(passwordValue)

  // AC5: Validate token on page load
  useEffect(() => {
    if (!token) {
      setTokenState('invalid')
      return
    }

    authApi.validateResetToken(token).then((result) => {
      if (result.valid) {
        setTokenState('valid')
        setMaskedEmail(result.email ?? null)
      } else {
        const err = result.error
        if (err === 'token_expired') setTokenState('expired')
        else if (err === 'token_used') setTokenState('used')
        else setTokenState('invalid')
      }
    }).catch(() => {
      setTokenState('invalid')
    })
  }, [token])

  const onSubmit = async (values: ResetPasswordFormValues) => {
    setServerError(null)
    try {
      await authApi.resetPassword(token, values.new_password)
      // AC6: redirect to login with success banner
      navigate('/login?reset=success', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        switch (err.code) {
          case 'TOKEN_EXPIRED':
            setTokenState('expired')
            break
          case 'TOKEN_USED':
            setTokenState('used')
            break
          case 'TOKEN_INVALID':
            setTokenState('invalid')
            break
          case 'PASSWORD_POLICY':
            setServerError(err.message)
            break
          default:
            setServerError(err.message || 'Something went wrong. Please try again.')
        }
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  if (tokenState === 'validating') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (tokenState !== 'valid') {
    // AC5: Error page for invalid/expired/used tokens
    const errorMessages: Record<Exclude<TokenState, 'validating' | 'valid'>, { title: string; body: string }> = {
      expired: {
        title: 'Reset link expired',
        body: 'This password reset link has expired. Reset links are valid for 1 hour.',
      },
      used: {
        title: 'Reset link already used',
        body: 'This password reset link has already been used. If you need to reset your password again, please request a new link.',
      },
      invalid: {
        title: 'Invalid reset link',
        body: 'This password reset link is invalid or has been revoked.',
      },
    }
    const { title, body } = errorMessages[tokenState]

    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-brand mb-1">QUALISYS</h1>
          </div>
          <div className="bg-white rounded-lg shadow-sm border border-border p-8 text-center" data-testid="token-error">
            <div className="mx-auto w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-foreground mb-2">{title}</h2>
            <p className="text-muted-foreground text-sm mb-6">{body}</p>
            <a
              href="/forgot-password"
              className="inline-block text-sm font-medium text-primary hover:underline"
              data-testid="request-new-link"
            >
              Request a new reset link
            </a>
          </div>
        </div>
      </div>
    )
  }

  // Valid token — show reset form
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand mb-1">QUALISYS</h1>
          <p className="text-muted-foreground text-sm">AI-Powered Testing Platform</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-border p-8">
          <h2 className="text-xl font-semibold text-foreground mb-2">Reset your password</h2>
          {maskedEmail && (
            <p className="text-muted-foreground text-sm mb-6">
              Resetting password for <span className="font-medium text-foreground">{maskedEmail}</span>
            </p>
          )}

          {/* Server error banner */}
          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="server-error"
            >
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="reset-password-form">
            {/* New Password + strength indicator */}
            <div className="mb-4">
              <Label htmlFor="new_password">New password</Label>
              <div className="relative mt-1">
                <Input
                  id="new_password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Min. 12 characters"
                  className="pr-10"
                  aria-invalid={!!errors.new_password}
                  data-testid="input-new-password"
                  {...register('new_password')}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  data-testid="toggle-new-password"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* AC5: Real-time strength indicator (reused from SignupPage) */}
              {passwordValue && (
                <div className="mt-2" data-testid="password-strength">
                  <div className="flex gap-1 mb-1">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors ${
                          i <= strength.level ? strength.color : 'bg-muted'
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Strength: <span className="font-medium">{strength.label}</span>
                  </p>
                </div>
              )}
              {errors.new_password && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-new-password">
                  {errors.new_password.message}
                </p>
              )}
            </div>

            {/* Confirm Password — AC5 */}
            <div className="mb-6">
              <Label htmlFor="confirm_password">Confirm new password</Label>
              <div className="relative mt-1">
                <Input
                  id="confirm_password"
                  type={showConfirm ? 'text' : 'password'}
                  autoComplete="new-password"
                  placeholder="Re-enter new password"
                  className="pr-10"
                  aria-invalid={!!errors.confirm_password}
                  data-testid="input-confirm-password"
                  {...register('confirm_password')}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowConfirm((v) => !v)}
                  aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                  data-testid="toggle-confirm-password"
                >
                  {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.confirm_password && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-confirm-password">
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full"
              disabled={isSubmitting}
              data-testid="submit-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resetting password…
                </>
              ) : (
                'Reset Password'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
