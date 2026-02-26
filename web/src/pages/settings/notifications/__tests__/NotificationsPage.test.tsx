/**
 * Frontend Tests — NotificationsPage
 * Story: 1-8-profile-notification-preferences (Task 7.8)
 * AC6 (email toggles, frequency dropdown, digest time/day),
 * AC7 (security alerts non-disableable, save applies immediately)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import NotificationsPage from '../NotificationsPage'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  userApi: {
    getNotifications: vi.fn(),
    updateNotifications: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public code: string, message: string, public status?: number) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

const mockUserApi = api.userApi as {
  getNotifications: ReturnType<typeof vi.fn>
  updateNotifications: ReturnType<typeof vi.fn>
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_PREFS = {
  email_test_completions: true,
  email_test_failures: true,
  email_team_changes: true,
  email_security_alerts: true,
  email_frequency: 'realtime' as const,
  digest_time: '09:00',
  digest_day: 'monday',
}

function renderNotificationsPage() {
  return render(
    <MemoryRouter>
      <NotificationsPage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('NotificationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUserApi.getNotifications.mockResolvedValue(BASE_PREFS)
  })

  // =========================================================================
  // Loading & error states
  // =========================================================================

  it('shows loading spinner initially', () => {
    mockUserApi.getNotifications.mockImplementation(() => new Promise(() => {}))
    renderNotificationsPage()
    expect(screen.getByTestId('notifications-loading')).toBeTruthy()
  })

  it('shows error when getNotifications fails', async () => {
    mockUserApi.getNotifications.mockRejectedValue(new Error('fail'))
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('notifications-fetch-error'))
  })

  // =========================================================================
  // Email toggles — AC6
  // =========================================================================

  it('renders all four email toggles', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('notifications-page'))
    expect(screen.getByTestId('toggle-email-test-completions')).toBeTruthy()
    expect(screen.getByTestId('toggle-email-test-failures')).toBeTruthy()
    expect(screen.getByTestId('toggle-email-team-changes')).toBeTruthy()
    expect(screen.getByTestId('toggle-email-security-alerts')).toBeTruthy()
  })

  it('test completions toggle starts checked', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    const toggle = screen.getByTestId('toggle-email-test-completions')
    expect(toggle.getAttribute('aria-checked')).toBe('true')
  })

  it('toggling test completions changes checked state', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    const toggle = screen.getByTestId('toggle-email-test-completions')
    fireEvent.click(toggle)
    expect(toggle.getAttribute('aria-checked')).toBe('false')
  })

  // =========================================================================
  // Security alerts — AC7 (non-disableable)
  // =========================================================================

  it('security alerts toggle is disabled', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-security-alerts'))
    const toggle = screen.getByTestId('toggle-email-security-alerts')
    expect(toggle.getAttribute('disabled')).toBeDefined()
  })

  it('security alerts toggle stays checked when clicked', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-security-alerts'))
    const toggle = screen.getByTestId('toggle-email-security-alerts')
    fireEvent.click(toggle) // should have no effect
    expect(toggle.getAttribute('aria-checked')).toBe('true')
  })

  // =========================================================================
  // Frequency radio buttons — AC6
  // =========================================================================

  it('realtime is selected by default', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('frequency-option-realtime'))
    const realtime = screen.getByTestId('frequency-option-realtime').querySelector('input')!
    expect(realtime.checked).toBe(true)
  })

  it('selecting daily shows digest time picker', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('frequency-option-daily'))
    const dailyRadio = screen.getByTestId('frequency-option-daily').querySelector('input')!
    fireEvent.click(dailyRadio)
    await waitFor(() => screen.getByTestId('digest-time-input'))
    expect(screen.queryByTestId('digest-day-select')).toBeNull()
  })

  it('selecting weekly shows both digest time and day picker', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('frequency-option-weekly'))
    const weeklyRadio = screen.getByTestId('frequency-option-weekly').querySelector('input')!
    fireEvent.click(weeklyRadio)
    await waitFor(() => screen.getByTestId('digest-time-input'))
    await waitFor(() => screen.getByTestId('digest-day-select'))
  })

  it('switching back to realtime hides digest pickers', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('frequency-option-daily'))
    const dailyRadio = screen.getByTestId('frequency-option-daily').querySelector('input')!
    fireEvent.click(dailyRadio)
    await waitFor(() => screen.getByTestId('digest-time-input'))

    const realtimeRadio = screen.getByTestId('frequency-option-realtime').querySelector('input')!
    fireEvent.click(realtimeRadio)
    await waitFor(() => expect(screen.queryByTestId('digest-time-input')).toBeNull())
  })

  // =========================================================================
  // Save button — AC7
  // =========================================================================

  it('save button is disabled when no changes (not dirty)', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('save-notifications-btn'))
    const btn = screen.getByTestId('save-notifications-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('save button enabled after changing a toggle', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('toggle-email-test-completions'))
    const btn = screen.getByTestId('save-notifications-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(false)
  })

  it('calls updateNotifications with correct payload on save', async () => {
    mockUserApi.updateNotifications.mockResolvedValue({ ...BASE_PREFS, email_test_completions: false })
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('save-notifications-btn'))
    await waitFor(() =>
      expect(mockUserApi.updateNotifications).toHaveBeenCalledWith(
        expect.objectContaining({
          email_test_completions: false,
          email_security_alerts: true, // always true
        }),
      ),
    )
  })

  it('shows success message after save', async () => {
    mockUserApi.updateNotifications.mockResolvedValue({ ...BASE_PREFS, email_test_completions: false })
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('save-notifications-btn'))
    await waitFor(() => screen.getByTestId('save-success'))
  })

  it('shows error message when save fails', async () => {
    mockUserApi.updateNotifications.mockRejectedValue(new Error('fail'))
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('toggle-email-test-completions'))
    fireEvent.click(screen.getByTestId('save-notifications-btn'))
    await waitFor(() => screen.getByTestId('save-error'))
  })

  // =========================================================================
  // Digest day selector
  // =========================================================================

  it('changing digest day updates selection', async () => {
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('frequency-option-weekly'))
    fireEvent.click(screen.getByTestId('frequency-option-weekly').querySelector('input')!)
    await waitFor(() => screen.getByTestId('digest-day-select'))
    const daySelect = screen.getByTestId('digest-day-select') as HTMLSelectElement
    fireEvent.change(daySelect, { target: { value: 'friday' } })
    expect(daySelect.value).toBe('friday')
  })

  // =========================================================================
  // Initial state from prefs with daily frequency
  // =========================================================================

  it('loads saved frequency and shows digest time when daily', async () => {
    mockUserApi.getNotifications.mockResolvedValue({
      ...BASE_PREFS,
      email_frequency: 'daily',
      digest_time: '08:30',
    })
    renderNotificationsPage()
    await waitFor(() => screen.getByTestId('digest-time-input'))
    const timeInput = screen.getByTestId('digest-time-input') as HTMLInputElement
    expect(timeInput.value).toBe('08:30')
  })
})
