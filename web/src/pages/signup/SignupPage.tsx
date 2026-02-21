/**
 * Signup Page
 * Story: 1-1-user-account-creation
 * AC: AC1 — email/password form with real-time inline validation
 * AC: AC2 — "Sign up with Google" OAuth redirect
 * AC: AC8 — error display with structured error messages
 */

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { authApi, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Validation schema — mirrors server-side policy (AC1)
// ---------------------------------------------------------------------------
const signupSchema = z
  .object({
    full_name: z
      .string()
      .min(1, 'Full name is required')
      .max(255, 'Full name must be at most 255 characters'),
    email: z.string().email('Please enter a valid email address'),
    password: z
      .string()
      .min(12, 'Password must be at least 12 characters')
      .regex(/[A-Z]/, 'Must contain at least 1 uppercase letter')
      .regex(/[a-z]/, 'Must contain at least 1 lowercase letter')
      .regex(/\d/, 'Must contain at least 1 number')
      .regex(/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`']/, 'Must contain at least 1 special character'),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  })

type SignupFormValues = z.infer<typeof signupSchema>

// Password strength indicator levels
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

export default function SignupPage() {
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [isGoogleLoading, setIsGoogleLoading] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting, isValid },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
    mode: 'onChange',   // real-time validation — AC1
  })

  const passwordValue = watch('password', '')
  const strength = getPasswordStrength(passwordValue)

  const onSubmit = async (values: SignupFormValues) => {
    setServerError(null)
    try {
      await authApi.register({
        email: values.email,
        password: values.password,
        full_name: values.full_name,
      })
      // AC3: redirect to "check your email" interstitial
      navigate('/check-email', { state: { email: values.email } })
    } catch (err) {
      if (err instanceof ApiError) {
        setServerError(err.message)
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    }
  }

  const handleGoogleSignup = () => {
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
          <h2 className="text-xl font-semibold text-foreground mb-6">Create your account</h2>

          {/* Google OAuth button — AC2 */}
          <Button
            type="button"
            variant="outline"
            className="w-full mb-4"
            onClick={handleGoogleSignup}
            disabled={isGoogleLoading}
            data-testid="google-signup-btn"
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
            Sign up with Google
          </Button>

          <div className="relative mb-4">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-muted-foreground">or</span>
            </div>
          </div>

          {/* Server error banner — AC8 */}
          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="server-error"
            >
              {serverError}
            </div>
          )}

          {/* Signup form — AC1 */}
          <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="signup-form">
            {/* Full Name */}
            <div className="mb-4">
              <Label htmlFor="full_name">Full name</Label>
              <Input
                id="full_name"
                type="text"
                autoComplete="name"
                placeholder="Jane Smith"
                className="mt-1"
                aria-invalid={!!errors.full_name}
                data-testid="input-full-name"
                {...register('full_name')}
              />
              {errors.full_name && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-full-name">
                  {errors.full_name.message}
                </p>
              )}
            </div>

            {/* Email */}
            <div className="mb-4">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="jane@example.com"
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

            {/* Password + strength meter */}
            <div className="mb-4">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="new-password"
                placeholder="Min. 12 characters"
                className="mt-1"
                aria-invalid={!!errors.password}
                data-testid="input-password"
                {...register('password')}
              />
              {/* Real-time strength indicator — AC1 */}
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
              {errors.password && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-password">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Confirm Password */}
            <div className="mb-6">
              <Label htmlFor="confirm_password">Confirm password</Label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                placeholder="Re-enter password"
                className="mt-1"
                aria-invalid={!!errors.confirm_password}
                data-testid="input-confirm-password"
                {...register('confirm_password')}
              />
              {errors.confirm_password && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-confirm-password">
                  {errors.confirm_password.message}
                </p>
              )}
            </div>

            {/* Submit — disabled until valid (AC1) */}
            <Button
              type="submit"
              className="w-full"
              disabled={!isValid || isSubmitting}
              data-testid="submit-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating account…
                </>
              ) : (
                'Create account'
              )}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <a href="/login" className="font-medium text-primary hover:underline">
              Log in
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
