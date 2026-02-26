/**
 * Frontend Tests — SecurityPage (MFA section)
 * Story: 1-7-two-factor-authentication-totp (Task 8.10)
 * AC1 (status badge), AC2 (QR code display), AC3 (code input, auto-submit),
 * AC4 (backup codes modal), AC7 (disable dialog), AC8 (regen dialog + warning)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SecurityPage from '../SecurityPage'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('qrcode.react', () => ({
  QRCodeSVG: ({ value }: { value: string }) => (
    <svg data-testid="qr-code-svg" data-value={value} />
  ),
}))

vi.mock('@/lib/api', () => ({
  authApi: {
    getSessions: vi.fn(),
    revokeSession: vi.fn(),
    logoutAll: vi.fn(),
    mfaStatus: vi.fn(),
    mfaSetup: vi.fn(),
    mfaSetupConfirm: vi.fn(),
    mfaDisable: vi.fn(),
    mfaRegenerateCodes: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public code: string, message: string, public status?: number) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

const mockAuthApi = api.authApi as {
  getSessions: ReturnType<typeof vi.fn>
  revokeSession: ReturnType<typeof vi.fn>
  logoutAll: ReturnType<typeof vi.fn>
  mfaStatus: ReturnType<typeof vi.fn>
  mfaSetup: ReturnType<typeof vi.fn>
  mfaSetupConfirm: ReturnType<typeof vi.fn>
  mfaDisable: ReturnType<typeof vi.fn>
  mfaRegenerateCodes: ReturnType<typeof vi.fn>
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const DISABLED_MFA_STATUS = {
  enabled: false,
  enabled_at: null,
  backup_codes_remaining: 0,
}

const ENABLED_MFA_STATUS = {
  enabled: true,
  enabled_at: '2026-02-20T10:00:00Z',
  backup_codes_remaining: 10,
}

const ENABLED_MFA_LOW_CODES = {
  enabled: true,
  enabled_at: '2026-02-20T10:00:00Z',
  backup_codes_remaining: 2,
}

const SETUP_RESPONSE = {
  qr_uri: 'otpauth://totp/QUALISYS:test@example.com?secret=JBSWY3DPEHPK3PXP&issuer=QUALISYS&algorithm=SHA1&digits=6&period=30',
  secret: 'JBSWY3DPEHPK3PXP',
  setup_token: 'user-uuid-123',
}

const BACKUP_CODES = ['ABCD1234', 'EFGH5678', 'IJKL9012', 'MNOP3456', 'QRST7890', 'UVWX2345', 'YZ016789', 'ABEF0123', 'CDGH4567', 'EFIJ8901']

function renderPage() {
  return render(
    <MemoryRouter>
      <SecurityPage />
    </MemoryRouter>
  )
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
  mockAuthApi.getSessions.mockResolvedValue({ sessions: [] })
})

// ---------------------------------------------------------------------------
// Task 8.10: MFA status display (AC1)
// ---------------------------------------------------------------------------

describe('MFA status display', () => {
  it('shows Disabled badge when MFA is off', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('mfa-status-badge')).toHaveTextContent('Disabled')
    })
  })

  it('shows Enabled badge when MFA is on', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('mfa-status-badge')).toHaveTextContent('Enabled')
    })
  })

  it('shows enabled date when MFA is enabled', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('mfa-enabled-at')).toBeInTheDocument()
    })
  })

  it('shows backup codes remaining count', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('mfa-backup-count')).toHaveTextContent('10')
    })
  })

  it('shows warning when < 3 backup codes remain (AC6)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_LOW_CODES)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('mfa-backup-count')).toHaveTextContent('2')
      expect(screen.getByTestId('mfa-backup-count')).toHaveTextContent('consider regenerating')
    })
  })

  it('shows Enable 2FA button when disabled', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument()
    })
  })

  it('shows Disable 2FA and Regenerate buttons when enabled', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('disable-2fa-btn')).toBeInTheDocument()
      expect(screen.getByTestId('regen-codes-btn')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Task 8.10: QR code setup flow (AC2)
// ---------------------------------------------------------------------------

describe('MFA setup flow', () => {
  it('shows QR code after clicking Enable 2FA (AC2)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('qr-code-svg')).toBeInTheDocument()
    })
  })

  it('QR code SVG has correct otpauth URI value (AC2)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => {
      const qr = screen.getByTestId('qr-code-svg')
      expect(qr.getAttribute('data-value')).toContain('otpauth://totp/')
      expect(qr.getAttribute('data-value')).toContain('QUALISYS')
    })
  })

  it('shows manual secret when toggle clicked (AC2)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('toggle-manual-secret')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('toggle-manual-secret'))

    await waitFor(() => {
      expect(screen.getByTestId('mfa-manual-secret')).toHaveTextContent('JBSWY3DPEHPK3PXP')
    })
  })

  it('confirm button disabled until 6 digits entered (AC3)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('setup-confirm-btn')).toBeDisabled())

    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '12345' } })
    expect(screen.getByTestId('setup-confirm-btn')).toBeDisabled()
  })

  it('confirm button enabled when 6 digits entered (AC3)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '123456' } })

    await waitFor(() => {
      expect(screen.getByTestId('setup-confirm-btn')).not.toBeDisabled()
    })
  })

  it('non-numeric input filtered from TOTP input', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    const input = screen.getByTestId('setup-totp-input') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'ABCDEF' } })
    expect(input.value).toBe('')
  })

  it('cancel button resets setup flow', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-cancel-btn')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('setup-cancel-btn'))
    await waitFor(() => {
      expect(screen.queryByTestId('mfa-setup-flow')).not.toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Task 8.10: Backup codes modal (AC4)
// ---------------------------------------------------------------------------

describe('Backup codes modal', () => {
  it('displays 10 backup codes after successful confirm (AC4)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    mockAuthApi.mfaSetupConfirm.mockResolvedValue({ backup_codes: BACKUP_CODES })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())

    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '123456' } })
    fireEvent.click(screen.getByTestId('setup-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('backup-codes-modal')).toBeInTheDocument()
      expect(screen.getByTestId('backup-codes-list')).toBeInTheDocument()
    })

    const codeItems = screen.getByTestId('backup-codes-list').querySelectorAll('span')
    expect(codeItems.length).toBe(10)
  })

  it('Done button disabled until checkbox checked (AC4)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    mockAuthApi.mfaSetupConfirm.mockResolvedValue({ backup_codes: BACKUP_CODES })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '123456' } })
    fireEvent.click(screen.getByTestId('setup-confirm-btn'))

    await waitFor(() => expect(screen.getByTestId('backup-codes-done-btn')).toBeInTheDocument())
    expect(screen.getByTestId('backup-codes-done-btn')).toBeDisabled()
  })

  it('Done button enabled after checking checkbox (AC4)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    mockAuthApi.mfaSetupConfirm.mockResolvedValue({ backup_codes: BACKUP_CODES })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '123456' } })
    fireEvent.click(screen.getByTestId('setup-confirm-btn'))

    await waitFor(() => expect(screen.getByTestId('codes-saved-checkbox')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('codes-saved-checkbox'))

    await waitFor(() => {
      expect(screen.getByTestId('backup-codes-done-btn')).not.toBeDisabled()
    })
  })

  it('shows Download and Copy buttons (AC4)', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    mockAuthApi.mfaSetupConfirm.mockResolvedValue({ backup_codes: BACKUP_CODES })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '123456' } })
    fireEvent.click(screen.getByTestId('setup-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('download-codes-btn')).toBeInTheDocument()
      expect(screen.getByTestId('copy-codes-btn')).toBeInTheDocument()
    })
  })

  it('shows error message on invalid confirm code', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaSetup.mockResolvedValue(SETUP_RESPONSE)
    mockAuthApi.mfaSetupConfirm.mockRejectedValue(
      new (api.ApiError as any)('INVALID_TOTP_CODE', 'Invalid code. Please try again.')
    )
    renderPage()

    await waitFor(() => expect(screen.getByTestId('enable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('enable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('setup-totp-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('setup-totp-input'), { target: { value: '000000' } })
    fireEvent.click(screen.getByTestId('setup-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('setup-confirm-error')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Task 8.10: Disable 2FA dialog (AC7)
// ---------------------------------------------------------------------------

describe('Disable 2FA dialog', () => {
  it('shows disable dialog when Disable 2FA clicked', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('disable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('disable-2fa-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('disable-2fa-dialog')).toBeInTheDocument()
    })
  })

  it('confirm button disabled without password', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('disable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('disable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('disable-2fa-confirm-btn')).toBeInTheDocument())
    expect(screen.getByTestId('disable-2fa-confirm-btn')).toBeDisabled()
  })

  it('calls mfaDisable with password on confirm', async () => {
    mockAuthApi.mfaStatus
      .mockResolvedValueOnce(ENABLED_MFA_STATUS)
      .mockResolvedValue(DISABLED_MFA_STATUS)
    mockAuthApi.mfaDisable.mockResolvedValue({ success: true, message: 'Disabled' })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('disable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('disable-2fa-btn'))

    await waitFor(() => expect(screen.getByTestId('disable-2fa-pw-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('disable-2fa-pw-input'), {
      target: { value: 'SecurePass123!' },
    })
    fireEvent.click(screen.getByTestId('disable-2fa-confirm-btn'))

    await waitFor(() => {
      expect(mockAuthApi.mfaDisable).toHaveBeenCalledWith('SecurePass123!')
    })
  })

  it('cancel closes dialog without calling API', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('disable-2fa-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('disable-2fa-btn'))
    await waitFor(() => expect(screen.getByTestId('disable-2fa-dialog')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('disable-2fa-cancel-btn'))
    await waitFor(() => {
      expect(screen.queryByTestId('disable-2fa-dialog')).not.toBeInTheDocument()
    })
    expect(mockAuthApi.mfaDisable).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// Task 8.10: Regenerate backup codes (AC8)
// ---------------------------------------------------------------------------

describe('Regenerate backup codes', () => {
  it('shows regen dialog when button clicked', async () => {
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    renderPage()

    await waitFor(() => expect(screen.getByTestId('regen-codes-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('regen-codes-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('regen-codes-dialog')).toBeInTheDocument()
    })
  })

  it('calls mfaRegenerateCodes with password and shows new codes', async () => {
    const newCodes = BACKUP_CODES.map(c => c.split('').reverse().join(''))
    mockAuthApi.mfaStatus.mockResolvedValue(ENABLED_MFA_STATUS)
    mockAuthApi.mfaRegenerateCodes.mockResolvedValue({ backup_codes: newCodes, message: 'Regenerated' })
    renderPage()

    await waitFor(() => expect(screen.getByTestId('regen-codes-btn')).toBeInTheDocument())
    fireEvent.click(screen.getByTestId('regen-codes-btn'))

    await waitFor(() => expect(screen.getByTestId('regen-codes-pw-input')).toBeInTheDocument())
    fireEvent.change(screen.getByTestId('regen-codes-pw-input'), {
      target: { value: 'SecurePass123!' },
    })
    fireEvent.click(screen.getByTestId('regen-codes-confirm-btn'))

    await waitFor(() => {
      expect(mockAuthApi.mfaRegenerateCodes).toHaveBeenCalledWith('SecurePass123!')
      // New codes modal should show
      expect(screen.getByTestId('backup-codes-modal')).toBeInTheDocument()
    })
  })
})
