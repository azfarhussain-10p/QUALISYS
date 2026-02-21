/**
 * Email Verification Landing Page
 * Story: 1-1-user-account-creation
 * AC: AC3 — validates token from URL, marks email_verified=true
 * Subtask: 5.6
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError } from '@/lib/api'

type VerifyState = 'loading' | 'success' | 'error'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')

  const [state, setState] = useState<VerifyState>('loading')
  const [message, setMessage] = useState<string>('')

  useEffect(() => {
    if (!token) {
      setState('error')
      setMessage('No verification token found. Please use the link from your email.')
      return
    }

    authApi
      .verifyEmail(token)
      .then((response) => {
        setState('success')
        setMessage(response.message)
      })
      .catch((err: unknown) => {
        setState('error')
        if (err instanceof ApiError) {
          setMessage(err.message)
        } else {
          setMessage('Verification failed. The link may have expired.')
        }
      })
  }, [token])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-lg shadow-sm border border-border p-8 text-center">
          {state === 'loading' && (
            <>
              <Loader2 className="mx-auto mb-4 h-12 w-12 animate-spin text-primary" data-testid="loading-indicator" />
              <h1 className="text-xl font-semibold text-foreground">Verifying your email…</h1>
            </>
          )}

          {state === 'success' && (
            <>
              <CheckCircle2
                className="mx-auto mb-4 h-12 w-12 text-green-500"
                data-testid="success-icon"
              />
              <h1 className="text-xl font-semibold text-foreground mb-2">Email verified!</h1>
              <p className="text-muted-foreground mb-6" data-testid="success-message">
                {message}
              </p>
              <Button className="w-full" onClick={() => navigate('/onboarding/create-org')}>
                Continue to set up your organization
              </Button>
            </>
          )}

          {state === 'error' && (
            <>
              <XCircle
                className="mx-auto mb-4 h-12 w-12 text-destructive"
                data-testid="error-icon"
              />
              <h1 className="text-xl font-semibold text-foreground mb-2">Verification failed</h1>
              <p className="text-muted-foreground mb-6" data-testid="error-message">
                {message}
              </p>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => navigate('/check-email')}
              >
                Request a new verification link
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
