/**
 * Frontend Tests — ResetPasswordPage
 * Story: 1-6-password-reset-flow (Task 7.9)
 * AC5 — /reset-password?token validates on load; shows form or error state
 * AC6 — On submit: update password, redirect to /login?reset=success
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ResetPasswordPage from '../ResetPasswordPage'

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

const mockValidateResetToken = vi.fn()
const mockResetPassword = vi.fn()

vi.mock('@/lib/api', () => ({
  authApi: {
    validateResetToken: (...args: unknown[]) => mockValidateResetToken(...args),
    resetPassword: (...args: unknown[]) => mockResetPassword(...args),
  },
  ApiError: class ApiError extends Error {
    constructor(
      public code: string,
      message: string,
      public status?: number,
    ) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// ---------------------------------------------------------------------------
// Render helpers
// ---------------------------------------------------------------------------

function renderWithToken(token = 'valid-token') {
  return render(
    <MemoryRouter initialEntries={[`/reset-password?token=${token}`]}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

function renderWithoutToken() {
  return render(
    <MemoryRouter initialEntries={['/reset-password']}>
      <Routes>
        <Route path="/reset-password" element={<ResetPasswordPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Validating state
  // -------------------------------------------------------------------------

  describe('Token validation loading state', () => {
    it('shows spinner while token is being validated', () => {
      mockValidateResetToken.mockReturnValueOnce(new Promise(() => {}))
      renderWithToken()
      // Spinner is rendered (Loader2 icon with animate-spin)
      expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    })

    it('shows invalid error when no token in URL', async () => {
      renderWithoutToken()
      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC5 — Token error states
  // -------------------------------------------------------------------------

  describe('AC5 — Token error states', () => {
    it('shows expired state for token_expired error', async () => {
      mockValidateResetToken.mockResolvedValueOnce({
        valid: false,
        error: 'token_expired',
      })
      renderWithToken('expired-token')

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/expired/i)).toBeInTheDocument()
    })

    it('shows used state for token_used error', async () => {
      mockValidateResetToken.mockResolvedValueOnce({
        valid: false,
        error: 'token_used',
      })
      renderWithToken('used-token')

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/already been used/i)).toBeInTheDocument()
    })

    it('shows invalid state for unknown error', async () => {
      mockValidateResetToken.mockResolvedValueOnce({
        valid: false,
        error: 'token_invalid',
      })
      renderWithToken('invalid-token')

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/invalid/i)).toBeInTheDocument()
    })

    it('shows invalid state when API call fails', async () => {
      mockValidateResetToken.mockRejectedValueOnce(new Error('Network error'))
      renderWithToken('bad-token')

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
    })

    it('error page has "Request a new reset link" link', async () => {
      mockValidateResetToken.mockResolvedValueOnce({
        valid: false,
        error: 'token_expired',
      })
      renderWithToken('expired-token')

      await waitFor(() => screen.getByTestId('token-error'))
      expect(screen.getByTestId('request-new-link')).toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // AC5 — Valid token, form display
  // -------------------------------------------------------------------------

  describe('AC5 — Reset password form', () => {
    beforeEach(() => {
      mockValidateResetToken.mockResolvedValue({
        valid: true,
        email: 'u***@example.com',
      })
    })

    it('shows reset password form for valid token', async () => {
      renderWithToken()
      await waitFor(() => {
        expect(screen.getByTestId('reset-password-form')).toBeInTheDocument()
      })
    })

    it('shows masked email address', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))
      expect(screen.getByText('u***@example.com')).toBeInTheDocument()
    })

    it('renders new password and confirm password inputs', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      expect(screen.getByTestId('input-new-password')).toBeInTheDocument()
      expect(screen.getByTestId('input-confirm-password')).toBeInTheDocument()
    })

    it('renders show/hide toggles for both password fields', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      expect(screen.getByTestId('toggle-new-password')).toBeInTheDocument()
      expect(screen.getByTestId('toggle-confirm-password')).toBeInTheDocument()
    })

    it('show/hide toggle changes input type for new password', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      const input = screen.getByTestId('input-new-password') as HTMLInputElement
      expect(input.type).toBe('password')

      await userEvent.click(screen.getByTestId('toggle-new-password'))
      expect(input.type).toBe('text')

      await userEvent.click(screen.getByTestId('toggle-new-password'))
      expect(input.type).toBe('password')
    })

    it('shows QUALISYS branding on the form page', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))
      expect(screen.getByText('QUALISYS')).toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // AC5 — Password strength indicator
  // -------------------------------------------------------------------------

  describe('AC5 — Password strength indicator', () => {
    beforeEach(() => {
      mockValidateResetToken.mockResolvedValue({ valid: true, email: 'u***@example.com' })
    })

    it('strength indicator appears when typing a password', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'abc')
      await waitFor(() => {
        expect(screen.getByTestId('password-strength')).toBeInTheDocument()
      })
    })

    it('shows "Weak" for short passwords', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'abc')
      await waitFor(() => screen.getByTestId('password-strength'))
      expect(screen.getByText(/weak/i)).toBeInTheDocument()
    })

    it('shows "Strong" for a password meeting all criteria', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'SecurePass123!')
      await waitFor(() => screen.getByTestId('password-strength'))
      expect(screen.getByText(/strong/i)).toBeInTheDocument()
    })

    it('strength indicator is not shown when password field is empty', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))
      expect(screen.queryByTestId('password-strength')).not.toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // Password validation
  // -------------------------------------------------------------------------

  describe('Password validation errors', () => {
    beforeEach(() => {
      mockValidateResetToken.mockResolvedValue({ valid: true, email: 'u***@example.com' })
    })

    it('shows error for password shorter than 12 characters', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'Short1!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('error-new-password')).toBeInTheDocument()
      })
      expect(screen.getByText(/at least 12 characters/i)).toBeInTheDocument()
      expect(mockResetPassword).not.toHaveBeenCalled()
    })

    it('shows error for missing uppercase letter', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'nouppercase123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('error-new-password')).toBeInTheDocument()
      })
    })

    it('shows error when passwords do not match', async () => {
      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'DifferentPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('error-confirm-password')).toBeInTheDocument()
      })
      expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
      expect(mockResetPassword).not.toHaveBeenCalled()
    })
  })

  // -------------------------------------------------------------------------
  // AC6 — Successful password reset
  // -------------------------------------------------------------------------

  describe('AC6 — Successful password reset', () => {
    beforeEach(() => {
      mockValidateResetToken.mockResolvedValue({ valid: true, email: 'u***@example.com' })
    })

    it('calls resetPassword API with correct args on valid submit', async () => {
      mockResetPassword.mockResolvedValueOnce({ success: true, message: 'Password reset.' })

      renderWithToken('my-reset-token')
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'NewSecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'NewSecurePass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(mockResetPassword).toHaveBeenCalledWith('my-reset-token', 'NewSecurePass123!')
      })
    })

    it('redirects to /login?reset=success on success — AC6', async () => {
      mockResetPassword.mockResolvedValueOnce({ success: true, message: 'Password reset.' })

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'NewSecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'NewSecurePass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?reset=success', { replace: true })
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC6 — Server-side error handling during submit
  // -------------------------------------------------------------------------

  describe('AC6 — Server error handling', () => {
    beforeEach(() => {
      mockValidateResetToken.mockResolvedValue({ valid: true, email: 'u***@example.com' })
    })

    it('shows server error banner on generic API error', async () => {
      mockResetPassword.mockRejectedValueOnce(new Error('Network error'))

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'ValidPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error')).toBeInTheDocument()
      })
    })

    it('transitions to expired state on TOKEN_EXPIRED error during submit', async () => {
      const { ApiError } = await import('@/lib/api')
      mockResetPassword.mockRejectedValueOnce(
        new ApiError('TOKEN_EXPIRED', 'Token has expired.', 400),
      )

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'ValidPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/expired/i)).toBeInTheDocument()
    })

    it('transitions to used state on TOKEN_USED error during submit', async () => {
      const { ApiError } = await import('@/lib/api')
      mockResetPassword.mockRejectedValueOnce(
        new ApiError('TOKEN_USED', 'Token already used.', 400),
      )

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'ValidPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('token-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/already been used/i)).toBeInTheDocument()
    })

    it('shows password policy error in server error banner', async () => {
      const { ApiError } = await import('@/lib/api')
      mockResetPassword.mockRejectedValueOnce(
        new ApiError('PASSWORD_POLICY', 'Password does not meet security requirements.', 422),
      )

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'ValidPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error')).toBeInTheDocument()
      })
      expect(screen.getByText(/security requirements/i)).toBeInTheDocument()
    })

    it('disables submit button while submitting', async () => {
      mockResetPassword.mockReturnValueOnce(new Promise(() => {}))

      renderWithToken()
      await waitFor(() => screen.getByTestId('reset-password-form'))

      await userEvent.type(screen.getByTestId('input-new-password'), 'ValidPass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'ValidPass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('submit-btn')).toBeDisabled()
      })
    })
  })
})
