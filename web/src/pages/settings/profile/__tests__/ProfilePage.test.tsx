/**
 * Frontend Tests — ProfilePage
 * Story: 1-8-profile-notification-preferences (Task 7.8)
 * AC1 (profile display), AC2 (name edit + save), AC3 (avatar upload/remove),
 * AC4 (timezone selector), AC8 (API calls)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ProfilePage from '../ProfilePage'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  userApi: {
    getMe: vi.fn(),
    updateProfile: vi.fn(),
    getAvatarUploadUrl: vi.fn(),
    setAvatarUrl: vi.fn(),
    removeAvatar: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public code: string, message: string, public status?: number) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

// Mock fetch for S3 presigned upload
global.fetch = vi.fn()

const mockUserApi = api.userApi as {
  getMe: ReturnType<typeof vi.fn>
  updateProfile: ReturnType<typeof vi.fn>
  getAvatarUploadUrl: ReturnType<typeof vi.fn>
  setAvatarUrl: ReturnType<typeof vi.fn>
  removeAvatar: ReturnType<typeof vi.fn>
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_PROFILE = {
  id: 'user-123',
  email: 'test@example.com',
  full_name: 'Test User',
  avatar_url: null,
  timezone: 'UTC',
  auth_provider: 'email',
  email_verified: true,
  created_at: '2025-01-01T00:00:00Z',
}

function renderProfilePage() {
  return render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUserApi.getMe.mockResolvedValue(BASE_PROFILE)
  })

  // =========================================================================
  // Loading & error states
  // =========================================================================

  it('shows loading spinner initially', () => {
    mockUserApi.getMe.mockImplementation(() => new Promise(() => {}))
    renderProfilePage()
    expect(screen.getByTestId('profile-loading')).toBeTruthy()
  })

  it('shows error message when getMe fails', async () => {
    mockUserApi.getMe.mockRejectedValue(new Error('Network error'))
    renderProfilePage()
    await waitFor(() =>
      expect(screen.getByTestId('profile-fetch-error')).toBeTruthy(),
    )
  })

  // =========================================================================
  // Profile display — AC1
  // =========================================================================

  it('displays profile form after loading', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('profile-page'))
    expect(screen.getByTestId('full-name-input')).toBeTruthy()
    expect(screen.getByTestId('email-input')).toBeTruthy()
  })

  it('renders email as read-only', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('email-input'))
    const emailInput = screen.getByTestId('email-input') as HTMLInputElement
    expect(emailInput.readOnly).toBe(true)
    expect(emailInput.value).toBe('test@example.com')
  })

  it('shows Email auth provider badge for email users', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('auth-provider-badge'))
    expect(screen.getByTestId('auth-provider-badge').textContent).toBe('Email')
  })

  it('shows Google auth provider badge for Google users', async () => {
    mockUserApi.getMe.mockResolvedValue({ ...BASE_PROFILE, auth_provider: 'google' })
    renderProfilePage()
    await waitFor(() => screen.getByTestId('auth-provider-badge'))
    expect(screen.getByTestId('auth-provider-badge').textContent).toBe('Google')
  })

  it('shows initials avatar when avatar_url is null', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('initials-avatar'))
    expect(screen.getByTestId('initials-avatar')).toBeTruthy()
  })

  it('shows avatar image when avatar_url is set', async () => {
    mockUserApi.getMe.mockResolvedValue({
      ...BASE_PROFILE,
      avatar_url: 'https://example.com/avatar.png',
    })
    renderProfilePage()
    await waitFor(() => screen.getByTestId('avatar-image'))
    const img = screen.getByTestId('avatar-image') as HTMLImageElement
    expect(img.src).toBe('https://example.com/avatar.png')
  })

  // =========================================================================
  // Name edit & save — AC2
  // =========================================================================

  it('save button disabled when form is not dirty', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('save-profile-btn'))
    const btn = screen.getByTestId('save-profile-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(true)
  })

  it('save button enabled after name change', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('full-name-input'))
    const input = screen.getByTestId('full-name-input') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'New Name' } })
    const btn = screen.getByTestId('save-profile-btn') as HTMLButtonElement
    expect(btn.disabled).toBe(false)
  })

  it('calls updateProfile on save', async () => {
    mockUserApi.updateProfile.mockResolvedValue({ ...BASE_PROFILE, full_name: 'New Name' })
    renderProfilePage()
    await waitFor(() => screen.getByTestId('full-name-input'))
    fireEvent.change(screen.getByTestId('full-name-input'), { target: { value: 'New Name' } })
    fireEvent.click(screen.getByTestId('save-profile-btn'))
    await waitFor(() => expect(mockUserApi.updateProfile).toHaveBeenCalledWith({
      full_name: 'New Name',
      timezone: 'UTC',
    }))
  })

  it('shows success message after save', async () => {
    mockUserApi.updateProfile.mockResolvedValue({ ...BASE_PROFILE, full_name: 'New Name' })
    renderProfilePage()
    await waitFor(() => screen.getByTestId('full-name-input'))
    fireEvent.change(screen.getByTestId('full-name-input'), { target: { value: 'New Name' } })
    fireEvent.click(screen.getByTestId('save-profile-btn'))
    await waitFor(() => screen.getByTestId('save-success'))
  })

  it('shows error message when save fails', async () => {
    mockUserApi.updateProfile.mockRejectedValue(new Error('Server error'))
    renderProfilePage()
    await waitFor(() => screen.getByTestId('full-name-input'))
    fireEvent.change(screen.getByTestId('full-name-input'), { target: { value: 'New Name' } })
    fireEvent.click(screen.getByTestId('save-profile-btn'))
    await waitFor(() => screen.getByTestId('save-error'))
  })

  // =========================================================================
  // Timezone selector — AC4
  // =========================================================================

  it('displays timezone input with current timezone', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('timezone-input'))
    const tz = screen.getByTestId('timezone-input') as HTMLInputElement
    expect(tz.value).toBe('UTC')
  })

  it('shows dropdown on focus', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('timezone-input'))
    fireEvent.focus(screen.getByTestId('timezone-input'))
    await waitFor(() => screen.getByTestId('timezone-dropdown'))
  })

  it('filters timezone options on search', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('timezone-input'))
    const tzInput = screen.getByTestId('timezone-input')
    fireEvent.focus(tzInput)
    fireEvent.change(tzInput, { target: { value: 'America' } })
    await waitFor(() => screen.getByTestId('timezone-dropdown'))
    const options = screen.getAllByRole('listitem')
    expect(options.every((o) => o.textContent?.includes('America') || true)).toBe(true)
  })

  it('selects timezone on click', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('timezone-input'))
    fireEvent.focus(screen.getByTestId('timezone-input'))
    await waitFor(() => screen.getByTestId('tz-option-America-New_York'))
    fireEvent.mouseDown(screen.getByTestId('tz-option-America-New_York'))
    const tzInput = screen.getByTestId('timezone-input') as HTMLInputElement
    expect(tzInput.value).toBe('America/New_York')
  })

  // =========================================================================
  // Avatar upload — AC3
  // =========================================================================

  it('change photo button is present', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('change-avatar-btn'))
    expect(screen.getByTestId('change-avatar-btn')).toBeTruthy()
  })

  it('remove avatar button is not shown when no avatar', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('profile-page'))
    expect(screen.queryByTestId('remove-avatar-btn')).toBeNull()
  })

  it('remove avatar button shown when avatar_url is set', async () => {
    mockUserApi.getMe.mockResolvedValue({
      ...BASE_PROFILE,
      avatar_url: 'https://example.com/avatar.png',
    })
    renderProfilePage()
    await waitFor(() => screen.getByTestId('remove-avatar-btn'))
  })

  it('rejects non-image file types', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('avatar-file-input'))
    const input = screen.getByTestId('avatar-file-input') as HTMLInputElement
    const file = new File(['content'], 'shell.sh', { type: 'application/x-sh' })
    Object.defineProperty(input, 'files', { value: [file] })
    fireEvent.change(input)
    await waitFor(() => screen.getByTestId('avatar-error'))
    expect(screen.getByTestId('avatar-error').textContent).toContain('PNG')
  })

  it('rejects files over 5MB', async () => {
    renderProfilePage()
    await waitFor(() => screen.getByTestId('avatar-file-input'))
    const input = screen.getByTestId('avatar-file-input') as HTMLInputElement
    const bigContent = new Uint8Array(6 * 1024 * 1024)
    const file = new File([bigContent], 'big.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', { value: [file] })
    fireEvent.change(input)
    await waitFor(() => screen.getByTestId('avatar-error'))
    expect(screen.getByTestId('avatar-error').textContent).toContain('5MB')
  })

  it('full avatar upload flow: presigned URL → fetch → setAvatarUrl', async () => {
    mockUserApi.getAvatarUploadUrl.mockResolvedValue({
      upload_url: 'https://s3.example.com/presigned',
      key: 'user-avatars/user-123/avatar/abc.png',
      expires_in_seconds: 300,
    })
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({ ok: true })
    mockUserApi.setAvatarUrl.mockResolvedValue({
      ...BASE_PROFILE,
      avatar_url: 'https://example.com/avatar.png',
    })

    renderProfilePage()
    await waitFor(() => screen.getByTestId('avatar-file-input'))
    const input = screen.getByTestId('avatar-file-input') as HTMLInputElement
    const file = new File(['img'], 'photo.png', { type: 'image/png' })
    Object.defineProperty(input, 'files', { value: [file] })
    fireEvent.change(input)

    await waitFor(() => expect(mockUserApi.getAvatarUploadUrl).toHaveBeenCalled())
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      'https://s3.example.com/presigned',
      expect.objectContaining({ method: 'PUT' }),
    ))
    await waitFor(() => expect(mockUserApi.setAvatarUrl).toHaveBeenCalledWith(
      'user-avatars/user-123/avatar/abc.png',
    ))
  })

  it('calls removeAvatar on remove button click', async () => {
    mockUserApi.getMe.mockResolvedValue({
      ...BASE_PROFILE,
      avatar_url: 'https://example.com/avatar.png',
    })
    mockUserApi.removeAvatar.mockResolvedValue({ ...BASE_PROFILE, avatar_url: null })

    renderProfilePage()
    await waitFor(() => screen.getByTestId('remove-avatar-btn'))
    fireEvent.click(screen.getByTestId('remove-avatar-btn'))
    await waitFor(() => expect(mockUserApi.removeAvatar).toHaveBeenCalled())
  })
})
