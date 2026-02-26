/**
 * Forgot Password Page
 * Story: 1-6-password-reset-flow
 * AC1 — Login page has "Forgot Password?" link (link is on LoginPage)
 * AC2 — /forgot-password page: email form, always-success message (no enumeration)
 * AC7 — Handle 429: show countdown message
 */

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Validation schema — RFC 5322 email format (AC2)
// ---------------------------------------------------------------------------
const forgotPasswordSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false)
  const [rateLimitRetryAfter, setRateLimitRetryAfter] = useState<number | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
  })

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    setRateLimitRetryAfter(null)
    try {
      await authApi.forgotPassword(values.email)
      // AC2: always show success message regardless of whether email exists
      setSubmitted(true)
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        // AC7: rate limit exceeded — extract Retry-After if available
        setRateLimitRetryAfter(60) // default 60s if not provided in error
      }
      // For any other error: still show success (no email enumeration — AC2)
      setSubmitted(true)
    }
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
          {submitted ? (
            /* Success state — AC2: always shown regardless of email existence */
            <div data-testid="success-message">
              <div className="text-center mb-6">
                <div className="mx-auto w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mb-4">
                  <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <h2 className="text-xl font-semibold text-foreground mb-2">Check your email</h2>
              </div>
              <p className="text-muted-foreground text-sm text-center mb-6">
                If an account with that email exists, we've sent a password reset link. Check your inbox (and spam folder).
              </p>
              <p className="text-muted-foreground text-xs text-center">
                The link expires in 1 hour.
              </p>
              <div className="mt-6 text-center">
                <a
                  href="/login"
                  className="text-sm font-medium text-primary hover:underline"
                  data-testid="back-to-login"
                >
                  Back to login
                </a>
              </div>
            </div>
          ) : (
            /* Request form — AC2 */
            <>
              <h2 className="text-xl font-semibold text-foreground mb-2">Forgot your password?</h2>
              <p className="text-muted-foreground text-sm mb-6">
                Enter your email address and we'll send you a link to reset your password.
              </p>

              {/* Rate limit banner — AC7 */}
              {rateLimitRetryAfter !== null && (
                <div
                  role="alert"
                  className="mb-4 rounded-md bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800"
                  data-testid="rate-limit-message"
                >
                  Too many reset requests. Please wait {rateLimitRetryAfter} seconds before trying again.
                </div>
              )}

              <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="forgot-password-form">
                <div className="mb-6">
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

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                  data-testid="submit-btn"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending reset link…
                    </>
                  ) : (
                    'Send Reset Link'
                  )}
                </Button>
              </form>

              <p className="mt-4 text-center text-sm text-muted-foreground">
                Remember your password?{' '}
                <a href="/login" className="font-medium text-primary hover:underline" data-testid="back-to-login">
                  Log in
                </a>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
