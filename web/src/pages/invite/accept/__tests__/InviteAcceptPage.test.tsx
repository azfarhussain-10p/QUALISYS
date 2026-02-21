/**
 * Frontend Tests — InviteAcceptPage
 * Story: 1-3-team-member-invitation (Task 7.4)
 * AC: AC4 — two-path accept (existing user / new user), token inspection on load
 * AC: AC5 — success state after accept
 * AC: AC9 — generic error messages, no token leakage
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import InviteAcceptPage from '../InviteAcceptPage'

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

const mockGetAcceptDetails = vi.fn()
const mockAccept = vi.fn()

vi.mock('@/lib/api', () => ({
  invitationApi: {
    getAcceptDetails: (...args: unknown[]) => mockGetAcceptDetails(...args),
    accept: (...args: unknown[]) => mockAccept(...args),
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
// Render helper — always renders at /invite/accept?token=<token>
// ---------------------------------------------------------------------------

function renderWithToken(token = 'valid-token') {
  return render(
    <MemoryRouter initialEntries={[`/invite/accept?token=${token}`]}>
      <Routes>
        <Route path="/invite/accept" element={<InviteAcceptPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('InviteAcceptPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('Loading', () => {
    it('shows a loading spinner while fetching details', () => {
      // Never resolve so we stay in loading state
      mockGetAcceptDetails.mockReturnValue(new Promise(() => {}))
      renderWithToken()
      expect(screen.getByTestId('invite-loading')).toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // Missing / invalid token
  // -------------------------------------------------------------------------

  describe('AC9 — Error states', () => {
    it('shows error when token is missing from URL', async () => {
      render(
        <MemoryRouter initialEntries={['/invite/accept']}>
          <Routes>
            <Route path="/invite/accept" element={<InviteAcceptPage />} />
          </Routes>
        </MemoryRouter>,
      )
      await waitFor(() => {
        expect(screen.getByTestId('invite-error')).toBeInTheDocument()
      })
    })

    it('shows generic error for invalid token — no token value in message', async () => {
      const { ApiError } = await import('@/lib/api')
      mockGetAcceptDetails.mockRejectedValueOnce(
        new ApiError('TOKEN_NOT_FOUND', 'Invitation not found or expired.', 404),
      )
      renderWithToken('malicious-token-guess')
      await waitFor(() => {
        expect(screen.getByTestId('invite-error')).toBeInTheDocument()
      })
      const errorMsg = screen.getByTestId('invite-error-message').textContent ?? ''
      // AC9: raw token must not appear in error text
      expect(errorMsg).not.toContain('malicious-token-guess')
    })

    it('shows generic error for expired token', async () => {
      const { ApiError } = await import('@/lib/api')
      mockGetAcceptDetails.mockRejectedValueOnce(
        new ApiError('TOKEN_EXPIRED', 'This invitation link has expired.', 410),
      )
      renderWithToken('expired-token')
      await waitFor(() => {
        expect(screen.getByTestId('invite-error')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // Existing user path — AC4
  // -------------------------------------------------------------------------

  describe('AC4 — Existing user path', () => {
    const existingUserDetails = {
      org_name: 'Acme Corp',
      role: 'developer',
      email: 'alice@example.com',
      user_exists: true,
      expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    }

    it('renders existing-user join UI when user_exists=true', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(existingUserDetails)
      renderWithToken()
      await waitFor(() => {
        expect(screen.getByTestId('existing-user-path')).toBeInTheDocument()
      })
      expect(screen.getByTestId('accept-btn')).toBeInTheDocument()
    })

    it('shows org name and role in the invite card', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(existingUserDetails)
      renderWithToken()
      await waitFor(() => screen.getByTestId('existing-user-path'))
      expect(screen.getByText('Acme Corp')).toBeInTheDocument()
      expect(screen.getByText('developer')).toBeInTheDocument()
    })

    it('calls accept API and shows success on click', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(existingUserDetails)
      mockAccept.mockResolvedValueOnce({ role: 'developer', org_id: 'org-1', user_id: 'u-1', token_type: 'bearer' })

      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))

      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('invite-success')).toBeInTheDocument()
      })
      expect(screen.getByText(/Acme Corp/i)).toBeInTheDocument()
    })

    it('shows accept error on API failure', async () => {
      const { ApiError } = await import('@/lib/api')
      mockGetAcceptDetails.mockResolvedValueOnce(existingUserDetails)
      mockAccept.mockRejectedValueOnce(
        new ApiError('ACCEPT_FAILED', 'Failed to join organization.', 500),
      )

      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('accept-error')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // New user path — AC4
  // -------------------------------------------------------------------------

  describe('AC4 — New user path', () => {
    const newUserDetails = {
      org_name: 'Beta Corp',
      role: 'qa-manual',
      email: 'bob@example.com',
      user_exists: false,
      expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    }

    it('renders registration form when user_exists=false', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      renderWithToken()
      await waitFor(() => {
        expect(screen.getByTestId('new-user-path')).toBeInTheDocument()
      })
      expect(screen.getByTestId('invite-email')).toBeInTheDocument()
      expect(screen.getByTestId('invite-full-name')).toBeInTheDocument()
      expect(screen.getByTestId('invite-password')).toBeInTheDocument()
      expect(screen.getByTestId('invite-confirm-password')).toBeInTheDocument()
    })

    it('email field is pre-filled and read-only', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      renderWithToken()
      await waitFor(() => screen.getByTestId('new-user-path'))

      const emailInput = screen.getByTestId('invite-email') as HTMLInputElement
      expect(emailInput.value).toBe('bob@example.com')
      expect(emailInput.readOnly).toBe(true)
    })

    it('validates required fields before submitting', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))

      // Click submit without filling form
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByText(/full name is required/i)).toBeInTheDocument()
      })
      expect(mockAccept).not.toHaveBeenCalled()
    })

    it('validates weak password', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))

      await userEvent.type(screen.getByTestId('invite-full-name'), 'Bob Smith')
      await userEvent.type(screen.getByTestId('invite-password'), 'weak')
      await userEvent.type(screen.getByTestId('invite-confirm-password'), 'weak')
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByText(/at least 8 characters/i)).toBeInTheDocument()
      })
    })

    it('validates mismatched passwords', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))

      await userEvent.type(screen.getByTestId('invite-full-name'), 'Bob Smith')
      await userEvent.type(screen.getByTestId('invite-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('invite-confirm-password'), 'Different123!')
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument()
      })
    })

    it('submits valid form and shows success — AC5', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce(newUserDetails)
      mockAccept.mockResolvedValueOnce({
        role: 'qa-manual',
        org_id: 'org-1',
        user_id: 'u-2',
        access_token: 'tok',
        refresh_token: 'rtok',
        token_type: 'bearer',
      })

      renderWithToken()
      await waitFor(() => screen.getByTestId('new-user-path'))

      await userEvent.type(screen.getByTestId('invite-full-name'), 'Bob Smith')
      await userEvent.type(screen.getByTestId('invite-password'), 'SecurePass123!')
      await userEvent.type(screen.getByTestId('invite-confirm-password'), 'SecurePass123!')
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('invite-success')).toBeInTheDocument()
      })
      expect(mockAccept).toHaveBeenCalledWith(
        expect.objectContaining({
          token: 'valid-token',
          full_name: 'Bob Smith',
          password: 'SecurePass123!',
        }),
      )
    })
  })

  // -------------------------------------------------------------------------
  // Success state — AC5
  // -------------------------------------------------------------------------

  describe('AC5 — Success state', () => {
    it('shows org name in success message', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce({
        org_name: 'Success Corp',
        role: 'viewer',
        email: 'carol@example.com',
        user_exists: true,
        expires_at: new Date(Date.now() + 86400000).toISOString(),
      })
      mockAccept.mockResolvedValueOnce({ role: 'viewer', org_id: 'o', user_id: 'u', token_type: 'bearer' })

      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => screen.getByTestId('invite-success'))
      expect(screen.getByText(/Success Corp/)).toBeInTheDocument()
    })

    it('renders Go to dashboard button', async () => {
      mockGetAcceptDetails.mockResolvedValueOnce({
        org_name: 'Dashboard Corp',
        role: 'viewer',
        email: 'dave@example.com',
        user_exists: true,
        expires_at: new Date(Date.now() + 86400000).toISOString(),
      })
      mockAccept.mockResolvedValueOnce({ role: 'viewer', org_id: 'o', user_id: 'u', token_type: 'bearer' })

      renderWithToken()
      await waitFor(() => screen.getByTestId('accept-btn'))
      await userEvent.click(screen.getByTestId('accept-btn'))

      await waitFor(() => screen.getByTestId('invite-success'))
      expect(screen.getByText(/go to dashboard/i)).toBeInTheDocument()
    })
  })
})
