/**
 * Login Page
 * Story: 1-5-login-session-management
 * AC1 — email/password form, show/hide toggle, redirect after login
 * AC2 — "Sign in with Google" button
 * AC5 — "Remember me" checkbox
 * AC6 — multi-org: redirect to /select-org
 * AC9 — error states: invalid credentials, account locked, rate limited
 */

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------
const loginSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  remember_me: z.boolean().default(false),
})

type LoginFormValues = z.infer<typeof loginSchema>

// ---------------------------------------------------------------------------
// Error message mapping from structured error codes (AC9)
// ---------------------------------------------------------------------------
function resolveErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.code) {
      case 'INVALID_CREDENTIALS':
        return 'Invalid email or password.'
      case 'EMAIL_NOT_VERIFIED':
        return 'Please verify your email address before logging in. Check your inbox.'
      case 'ACCOUNT_LOCKED':
        return 'Your account is locked after too many failed attempts. Check your email for an unlock link or wait 1 hour.'
      case 'RATE_LIMITED':
        return 'Too many login attempts. Please wait before trying again.'
      default:
        return err.message || 'Something went wrong. Please try again.'
    }
  }
  return 'Something went wrong. Please try again.'
}

// ---------------------------------------------------------------------------
// Safe redirect helper — prevents open redirect via ?next= parameter
// Only allows relative paths (e.g. /dashboard). Rejects absolute URLs and
// protocol-relative URLs (//evil.com) that could redirect off-domain.
// ---------------------------------------------------------------------------
function _safeRedirect(next: string | null): string {
  if (!next) return '/'
  if (next.startsWith('/') && !next.startsWith('//')) return next
  return '/'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const nextUrl = _safeRedirect(searchParams.get('next'))

  const [serverError, setServerError] = useState<string | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { remember_me: false },
  })

  const onSubmit = async (values: LoginFormValues) => {
    setServerError(null)
    try {
      const result = await authApi.login({
        email: values.email,
        password: values.password,
        remember_me: values.remember_me,
      })

      // Store org list in sessionStorage for the select-org page (AC6)
      if (result.has_multiple_orgs) {
        sessionStorage.setItem('pendingOrgs', JSON.stringify(result.orgs))
        navigate('/select-org')
      } else {
        // Single org or no org: go to the intended destination
        sessionStorage.removeItem('pendingOrgs')
        navigate(nextUrl, { replace: true })
      }
    } catch (err) {
      setServerError(resolveErrorMessage(err))
    }
  }

  const handleGoogleLogin = () => {
    setIsGoogleLoading(true)
    authApi.googleAuthorize()
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand mb-1">QUALISYS</h1>
          <p className="text-muted-foreground text-sm">AI-Powered Testing Platform</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-border p-8">
          <h2 className="text-xl font-semibold text-foreground mb-6">Welcome back</h2>

          {/* Google OAuth button — AC2 */}
          <Button
            type="button"
            variant="outline"
            className="w-full mb-4"
            onClick={handleGoogleLogin}
            disabled={isGoogleLoading}
            data-testid="google-login-btn"
          >
            {isGoogleLoading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
            )}
            Sign in with Google
          </Button>

          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-muted-foreground">or</span>
            </div>
          </div>

          {/* Server error banner — AC9 */}
          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="server-error"
            >
              {serverError}
            </div>
          )}

          {/* Login form — AC1 */}
          <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="login-form">
            {/* Email */}
            <div className="mb-4">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="mt-1"
                aria-invalid={!!errors.email}
                data-testid="input-email"
                {...register('email')}
              />
              {errors.email && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-email">
                  {errors.email.message}
                </p>
              )}
            </div>

            {/* Password — with show/hide toggle (AC1) */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <Label htmlFor="password">Password</Label>
                <a
                  href="/forgot-password"
                  className="text-xs text-primary hover:underline"
                  data-testid="forgot-password-link"
                >
                  Forgot password?
                </a>
              </div>
              <div className="relative mt-1">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  className="pr-10"
                  aria-invalid={!!errors.password}
                  data-testid="input-password"
                  {...register('password')}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  data-testid="toggle-password"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-password">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Remember me — AC5 */}
            <div className="flex items-center gap-2 mb-6">
              <input
                id="remember_me"
                type="checkbox"
                className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
                data-testid="remember-me"
                {...register('remember_me')}
              />
              <Label htmlFor="remember_me" className="text-sm font-normal cursor-pointer">
                Remember me for 30 days
              </Label>
            </div>

            {/* Submit */}
            <Button
              type="submit"
              className="w-full"
              disabled={isSubmitting}
              data-testid="submit-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in…
                </>
              ) : (
                'Log in'
              )}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Don't have an account?{' '}
            <a href="/signup" className="font-medium text-primary hover:underline" data-testid="signup-link">
              Sign up
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
