/**
 * "Check your email" Interstitial Page
 * Story: 1-1-user-account-creation
 * AC: AC3 — shown after email/password signup; unverified users see this until verified
 * Subtask: 5.5
 */

import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { Mail, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError } from '@/lib/api'

export default function CheckEmailPage() {
  const location = useLocation()
  const email: string = (location.state as { email?: string })?.email ?? ''

  const [resendState, setResendState] = useState<'idle' | 'loading' | 'sent' | 'error'>('idle')
  const [resendMessage, setResendMessage] = useState<string | null>(null)

  const handleResend = async () => {
    if (!email) return
    setResendState('loading')
    setResendMessage(null)
    try {
      const response = await authApi.resendVerification(email)
      setResendState('sent')
      setResendMessage(response.message)
    } catch (err) {
      setResendState('error')
      if (err instanceof ApiError) {
        setResendMessage(err.message)
      } else {
        setResendMessage('Could not resend email. Please try again later.')
      }
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-lg shadow-sm border border-border p-8 text-center">
          {/* Icon */}
          <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
            <Mail className="h-8 w-8 text-primary" />
          </div>

          <h1 className="text-2xl font-bold text-foreground mb-2">Check your email</h1>
          <p className="text-muted-foreground mb-2">
            We've sent a verification link to:
          </p>
          {email && (
            <p className="font-medium text-foreground mb-6" data-testid="email-display">
              {email}
            </p>
          )}
          <p className="text-sm text-muted-foreground mb-8">
            Click the link in the email to verify your account. The link expires in{' '}
            <strong>24 hours</strong>.
          </p>

          {/* Resend — AC3 */}
          {resendMessage && (
            <div
              role="status"
              className={`mb-4 rounded-md px-4 py-3 text-sm ${
                resendState === 'error'
                  ? 'bg-destructive/10 text-destructive border border-destructive/20'
                  : 'bg-green-50 text-green-800 border border-green-200'
              }`}
              data-testid="resend-message"
            >
              {resendMessage}
            </div>
          )}

          <Button
            variant="outline"
            className="w-full"
            onClick={handleResend}
            disabled={resendState === 'loading' || resendState === 'sent' || !email}
            data-testid="resend-btn"
          >
            {resendState === 'loading' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {resendState === 'sent' ? 'Email sent!' : 'Resend verification email'}
          </Button>

          <p className="mt-4 text-xs text-muted-foreground">
            Wrong email?{' '}
            <a href="/signup" className="text-primary hover:underline">
              Go back to sign up
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
