/**
 * Frontend Tests — SignupPage
 * Story: 1-1-user-account-creation (Task 6.5)
 * AC: AC1 — form validation, real-time feedback, submit disabled until valid
 * AC: AC2 — Google OAuth button renders
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SignupPage from '../SignupPage'

// Mock the API module
vi.mock('@/lib/api', () => ({
  authApi: {
    register: vi.fn(),
    googleAuthorize: vi.fn(),
    resendVerification: vi.fn(),
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

// Mock react-router navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function renderSignupPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SignupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC1: Form rendering', () => {
    it('renders all required form fields', () => {
      renderSignupPage()
      expect(screen.getByTestId('input-full-name')).toBeInTheDocument()
      expect(screen.getByTestId('input-email')).toBeInTheDocument()
      expect(screen.getByTestId('input-password')).toBeInTheDocument()
      expect(screen.getByTestId('input-confirm-password')).toBeInTheDocument()
    })

    it('renders submit button', () => {
      renderSignupPage()
      expect(screen.getByTestId('submit-btn')).toBeInTheDocument()
    })

    it('submit button is disabled when form is empty (AC1)', () => {
      renderSignupPage()
      expect(screen.getByTestId('submit-btn')).toBeDisabled()
    })
  })

  describe('AC2: Google OAuth button', () => {
    it('renders Google sign-up button', () => {
      renderSignupPage()
      expect(screen.getByTestId('google-signup-btn')).toBeInTheDocument()
      expect(screen.getByTestId('google-signup-btn')).toHaveTextContent('Sign up with Google')
    })

    it('calls googleAuthorize when Google button clicked', async () => {
      const { authApi } = await import('@/lib/api')
      renderSignupPage()
      await userEvent.click(screen.getByTestId('google-signup-btn'))
      expect(authApi.googleAuthorize).toHaveBeenCalledTimes(1)
    })
  })

  describe('AC1: Real-time validation', () => {
    it('shows email error on invalid format', async () => {
      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-email'), 'not-an-email')
      fireEvent.blur(screen.getByTestId('input-email'))
      await waitFor(() => {
        expect(screen.getByTestId('error-email')).toBeInTheDocument()
      })
    })

    it('shows password strength indicator when typing password', async () => {
      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await waitFor(() => {
        expect(screen.getByTestId('password-strength')).toBeInTheDocument()
      })
    })

    it('shows confirm password mismatch error', async () => {
      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'Different123!')
      fireEvent.blur(screen.getByTestId('input-confirm-password'))
      await waitFor(() => {
        expect(screen.getByTestId('error-confirm-password')).toBeInTheDocument()
      })
    })

    it('submit button enabled when all fields valid', async () => {
      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-full-name'), 'Jane Smith')
      await userEvent.type(screen.getByTestId('input-email'), 'jane@example.com')
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'SecurePass123!')
      await waitFor(() => {
        expect(screen.getByTestId('submit-btn')).not.toBeDisabled()
      })
    })
  })

  describe('AC1: Form submission', () => {
    it('calls register API with correct payload on submit', async () => {
      const { authApi } = await import('@/lib/api')
      vi.mocked(authApi.register).mockResolvedValueOnce({
        user: {
          id: '1',
          email: 'jane@example.com',
          full_name: 'Jane Smith',
          email_verified: false,
          auth_provider: 'email',
          avatar_url: null,
          created_at: '2026-02-20T00:00:00Z',
        },
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
      })

      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-full-name'), 'Jane Smith')
      await userEvent.type(screen.getByTestId('input-email'), 'jane@example.com')
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'SecurePass123!')

      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(authApi.register).toHaveBeenCalledWith({
          email: 'jane@example.com',
          password: 'SecurePass123!',
          full_name: 'Jane Smith',
        })
      })
    })

    it('navigates to /check-email after successful registration', async () => {
      const { authApi } = await import('@/lib/api')
      vi.mocked(authApi.register).mockResolvedValueOnce({
        user: {
          id: '1',
          email: 'jane@example.com',
          full_name: 'Jane Smith',
          email_verified: false,
          auth_provider: 'email',
          avatar_url: null,
          created_at: '2026-02-20T00:00:00Z',
        },
        access_token: 'tok',
        refresh_token: 'ref',
        token_type: 'bearer',
      })

      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-full-name'), 'Jane Smith')
      await userEvent.type(screen.getByTestId('input-email'), 'jane@example.com')
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'SecurePass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/check-email', expect.any(Object))
      })
    })

    it('displays server error on API failure', async () => {
      const { authApi, ApiError } = await import('@/lib/api')
      vi.mocked(authApi.register).mockRejectedValueOnce(
        new ApiError('DUPLICATE_EMAIL', 'An account with this email already exists.'),
      )

      renderSignupPage()
      await userEvent.type(screen.getByTestId('input-full-name'), 'Jane')
      await userEvent.type(screen.getByTestId('input-email'), 'dupe@example.com')
      await userEvent.type(screen.getByTestId('input-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('input-confirm-password'), 'SecurePass123!')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error')).toBeInTheDocument()
        expect(screen.getByTestId('server-error')).toHaveTextContent(
          'An account with this email already exists.',
        )
      })
    })
  })
})
