/**
 * Frontend tests — DeleteOrganization component
 * Story: 1-13-data-export-org-deletion (Task 7.12)
 * AC: #3 — multi-step confirmation: warning → type org name → 2FA/password
 * AC: #6 — post-deletion state
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DeleteOrganization from '../DeleteOrganization'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

const mockDeleteOrg = vi.fn()

vi.mock('@/lib/api', () => ({
  exportApi: {
    deleteOrg: (...args: unknown[]) => mockDeleteOrg(...args),
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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_PROPS = {
  orgId: 'org-123',
  orgName: 'Acme Corp',
  mfaEnabled: false,
  userRole: 'owner',
}

function renderDeleteOrg(props?: Partial<typeof DEFAULT_PROPS> & { onDeleted?: () => void }) {
  return render(<DeleteOrganization {...DEFAULT_PROPS} {...props} />)
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// AC: Owner-only visibility
// ---------------------------------------------------------------------------

describe('Owner-only visibility', () => {
  it('renders nothing for non-owner roles', () => {
    const { container } = renderDeleteOrg({ userRole: 'admin' })
    expect(container.firstChild).toBeNull()
  })

  it('renders danger zone for owner role', () => {
    renderDeleteOrg({ userRole: 'owner' })
    expect(screen.getByTestId('danger-zone')).toBeInTheDocument()
  })

  it('renders Delete Organization button', () => {
    renderDeleteOrg()
    expect(screen.getByTestId('delete-org-btn')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AC3: Step 1 — Warning
// ---------------------------------------------------------------------------

describe('Step 1: Warning dialog', () => {
  it('shows warning step after clicking Delete button', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()

    await user.click(screen.getByTestId('delete-org-btn'))

    expect(screen.getByTestId('step-warning')).toBeInTheDocument()
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
    expect(screen.getByText(/Acme Corp/i)).toBeInTheDocument()
  })

  it('returns to idle when Cancel is clicked in warning step', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()

    await user.click(screen.getByTestId('delete-org-btn'))
    await user.click(screen.getByTestId('warning-cancel-btn'))

    expect(screen.getByTestId('danger-zone')).toBeInTheDocument()
    expect(screen.queryByTestId('step-warning')).not.toBeInTheDocument()
  })

  it('advances to name-confirm step when "I understand" is clicked', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()

    await user.click(screen.getByTestId('delete-org-btn'))
    await user.click(screen.getByTestId('warning-proceed-btn'))

    expect(screen.getByTestId('step-name-confirm')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AC3: Step 2 — Type org name
// ---------------------------------------------------------------------------

describe('Step 2: Name confirmation', () => {
  async function goToNameStep(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByTestId('delete-org-btn'))
    await user.click(screen.getByTestId('warning-proceed-btn'))
  }

  it('shows name input in step 2', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToNameStep(user)
    expect(screen.getByTestId('org-name-input')).toBeInTheDocument()
  })

  it('Continue button is disabled when name does not match', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToNameStep(user)

    await user.type(screen.getByTestId('org-name-input'), 'wrong name')
    expect(screen.getByTestId('name-confirm-btn')).toBeDisabled()
  })

  it('Continue button enables when name matches exactly', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToNameStep(user)

    await user.type(screen.getByTestId('org-name-input'), 'Acme Corp')
    expect(screen.getByTestId('name-confirm-btn')).not.toBeDisabled()
  })

  it('shows error message for wrong name', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToNameStep(user)

    await user.type(screen.getByTestId('org-name-input'), 'wrong')
    expect(screen.getByText(/does not match/i)).toBeInTheDocument()
  })

  it('advances to verification step when correct name entered', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToNameStep(user)

    await user.type(screen.getByTestId('org-name-input'), 'Acme Corp')
    await user.click(screen.getByTestId('name-confirm-btn'))

    expect(screen.getByTestId('step-verification')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AC3: Step 3 — Verification (password or 2FA)
// ---------------------------------------------------------------------------

describe('Step 3: Verification', () => {
  async function goToVerificationStep(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByTestId('delete-org-btn'))
    await user.click(screen.getByTestId('warning-proceed-btn'))
    await user.type(screen.getByTestId('org-name-input'), 'Acme Corp')
    await user.click(screen.getByTestId('name-confirm-btn'))
  }

  it('shows password input when MFA is not enabled', async () => {
    const user = userEvent.setup()
    renderDeleteOrg({ mfaEnabled: false })
    await goToVerificationStep(user)
    expect(screen.getByText(/password/i)).toBeInTheDocument()
    const input = screen.getByTestId('verification-input')
    expect(input).toHaveAttribute('type', 'password')
  })

  it('shows TOTP input when MFA is enabled', async () => {
    const user = userEvent.setup()
    renderDeleteOrg({ mfaEnabled: true })
    await goToVerificationStep(user)
    expect(screen.getByText(/6-digit TOTP/i)).toBeInTheDocument()
    const input = screen.getByTestId('verification-input')
    expect(input).toHaveAttribute('inputMode', 'numeric')
  })

  it('Delete button disabled until verification input is filled', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()
    await goToVerificationStep(user)
    expect(screen.getByTestId('delete-confirm-btn')).toBeDisabled()
  })

  it('shows loading state during deletion', async () => {
    const user = userEvent.setup()
    mockDeleteOrg.mockReturnValue(new Promise(() => {}))  // never resolves
    renderDeleteOrg()
    await goToVerificationStep(user)

    await user.type(screen.getByTestId('verification-input'), 'mypassword')
    await user.click(screen.getByTestId('delete-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('delete-confirm-btn')).toBeDisabled()
    })
  })

  it('shows error when deletion API fails', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/lib/api')
    mockDeleteOrg.mockRejectedValue(
      new ApiError('VERIFICATION_FAILED', 'Incorrect password.', 403),
    )

    renderDeleteOrg()
    await goToVerificationStep(user)

    await user.type(screen.getByTestId('verification-input'), 'wrongpass')
    await user.click(screen.getByTestId('delete-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('delete-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('delete-error')).toHaveTextContent(/incorrect password/i)
  })

  it('shows deletion-initiated state on success', async () => {
    const user = userEvent.setup()
    const onDeleted = vi.fn()
    mockDeleteOrg.mockResolvedValue({ status: 'processing', message: 'Deletion initiated.' })

    renderDeleteOrg({ onDeleted })
    await goToVerificationStep(user)

    await user.type(screen.getByTestId('verification-input'), 'correct-password')
    await user.click(screen.getByTestId('delete-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('deletion-initiated')).toBeInTheDocument()
    })
    expect(onDeleted).toHaveBeenCalledOnce()
  })
})

// ---------------------------------------------------------------------------
// AC3: Cancel at any step returns to idle
// ---------------------------------------------------------------------------

describe('Cancel resets state', () => {
  it('can cancel from verification step', async () => {
    const user = userEvent.setup()
    renderDeleteOrg()

    await user.click(screen.getByTestId('delete-org-btn'))
    await user.click(screen.getByTestId('warning-proceed-btn'))
    await user.type(screen.getByTestId('org-name-input'), 'Acme Corp')
    await user.click(screen.getByTestId('name-confirm-btn'))
    // Now in verification step
    await user.click(screen.getByTestId('verification-cancel-btn'))

    expect(screen.getByTestId('danger-zone')).toBeInTheDocument()
  })
})
