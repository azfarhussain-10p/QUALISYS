/**
 * Frontend Tests — ActiveMembersList
 * Story: 1-4-user-management-remove-change-roles (Task 7.9)
 * AC1, AC2, AC3, AC6 — member list, role-change dialog, remove dialog, RBAC, last-admin guard
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ActiveMembersList from '../ActiveMembersList'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  memberApi: {
    list: vi.fn(),
    changeRole: vi.fn(),
    removeMember: vi.fn(),
  },
  ApiError: class ApiError extends Error {
    constructor(public code: string, message: string, public status?: number) {
      super(message)
      this.name = 'ApiError'
    }
  },
}))

const mockMemberApi = api.memberApi as {
  list: ReturnType<typeof vi.fn>
  changeRole: ReturnType<typeof vi.fn>
  removeMember: ReturnType<typeof vi.fn>
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const OWNER_ID = 'owner-uuid-001'
const MEMBER_ID = 'member-uuid-002'
const ADMIN_ID = 'admin-uuid-003'
const ORG_ID = 'org-uuid-111'
const ORG_NAME = 'Test Org'

function makeMember(overrides: Partial<api.MemberResponse> = {}): api.MemberResponse {
  return {
    user_id: MEMBER_ID,
    email: 'member@example.com',
    full_name: 'Test Member',
    role: 'developer',
    joined_at: '2026-01-01T00:00:00Z',
    is_active: true,
    ...overrides,
  }
}

function makeOwner(): api.MemberResponse {
  return {
    user_id: OWNER_ID,
    email: 'owner@example.com',
    full_name: 'Owner User',
    role: 'owner',
    joined_at: '2026-01-01T00:00:00Z',
    is_active: true,
  }
}

const defaultPaginatedResponse: api.PaginatedMembersResponse = {
  members: [makeOwner(), makeMember()],
  total: 2,
  page: 1,
  per_page: 25,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderList(
  props: Partial<{
    orgId: string
    orgName: string
    currentUserId: string
    currentUserRole: string
  }> = {},
) {
  return render(
    <ActiveMembersList
      orgId={props.orgId ?? ORG_ID}
      orgName={props.orgName ?? ORG_NAME}
      currentUserId={props.currentUserId ?? OWNER_ID}
      currentUserRole={props.currentUserRole ?? 'owner'}
    />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ActiveMembersList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockMemberApi.list.mockResolvedValue(defaultPaginatedResponse)
  })

  // -----------------------------------------------------------------------
  // AC1 — Member list rendering
  // -----------------------------------------------------------------------

  it('renders member list with name, email, role, joined date', async () => {
    renderList()
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    expect(screen.getByText('Test Member')).toBeTruthy()
    expect(screen.getByText('member@example.com')).toBeTruthy()
    expect(screen.getByText(/Developer/i)).toBeTruthy()
  })

  it('shows loading spinner while fetching', () => {
    mockMemberApi.list.mockReturnValue(new Promise(() => {})) // never resolves
    renderList()
    expect(screen.getByTestId('members-loading')).toBeTruthy()
  })

  it('shows error message on fetch failure', async () => {
    mockMemberApi.list.mockRejectedValue(
      new api.ApiError('SERVER_ERROR', 'Failed to load members.')
    )
    renderList()
    await waitFor(() => expect(screen.getByTestId('members-error')).toBeTruthy())
    expect(screen.getByText('Failed to load members.')).toBeTruthy()
  })

  it('shows empty state when no members', async () => {
    mockMemberApi.list.mockResolvedValue({ members: [], total: 0, page: 1, per_page: 25 })
    renderList()
    await waitFor(() => expect(screen.getByTestId('no-members')).toBeTruthy())
  })

  // -----------------------------------------------------------------------
  // AC1 — RBAC: action buttons hidden for non-Owner/Admin (read-only list)
  // -----------------------------------------------------------------------

  it('hides action buttons for non-admin roles (read-only list)', async () => {
    renderList({ currentUserRole: 'viewer', currentUserId: 'viewer-id' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())
    // No Change Role or Remove buttons visible
    expect(screen.queryByText('Change Role')).toBeNull()
    expect(screen.queryByText('Remove')).toBeNull()
  })

  it('shows action buttons for Owner role', async () => {
    renderList({ currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())
    // At least one Change Role button visible (for the non-self member)
    const changeBtns = screen.getAllByTestId(`change-role-btn-${MEMBER_ID}`)
    expect(changeBtns.length).toBeGreaterThan(0)
  })

  // -----------------------------------------------------------------------
  // AC2 — Self-action prevention: own row has disabled action buttons
  // -----------------------------------------------------------------------

  it('disables Change Role and Remove for current user own row', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    const ownChangeBtn = screen.getByTestId(`change-role-btn-${OWNER_ID}`)
    const ownRemoveBtn = screen.getByTestId(`remove-btn-${OWNER_ID}`)
    expect(ownChangeBtn).toBeDisabled()
    expect(ownRemoveBtn).toBeDisabled()
  })

  it('enables Change Role and Remove for other members', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    const changeBtn = screen.getByTestId(`change-role-btn-${MEMBER_ID}`)
    const removeBtn = screen.getByTestId(`remove-btn-${MEMBER_ID}`)
    expect(changeBtn).not.toBeDisabled()
    expect(removeBtn).not.toBeDisabled()
  })

  // -----------------------------------------------------------------------
  // AC6 — Last-admin guard: disabled if only one owner/admin
  // -----------------------------------------------------------------------

  it('disables actions for last Owner/Admin member', async () => {
    // Only one owner (OWNER_ID), render as a different admin
    mockMemberApi.list.mockResolvedValue({
      members: [makeOwner()],
      total: 1,
      page: 1,
      per_page: 25,
    })
    renderList({ currentUserId: ADMIN_ID, currentUserRole: 'admin' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    const changeBtn = screen.getByTestId(`change-role-btn-${OWNER_ID}`)
    const removeBtn = screen.getByTestId(`remove-btn-${OWNER_ID}`)
    expect(changeBtn).toBeDisabled()
    expect(removeBtn).toBeDisabled()
  })

  // -----------------------------------------------------------------------
  // AC2 — Role-change dialog
  // -----------------------------------------------------------------------

  it('opens role-change dialog on button click', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`change-role-btn-${MEMBER_ID}`))
    expect(screen.getByTestId('change-role-dialog')).toBeTruthy()
  })

  it('cancels role-change dialog without API call', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`change-role-btn-${MEMBER_ID}`))
    fireEvent.click(screen.getByTestId('cancel-role-change-btn'))
    expect(screen.queryByTestId('change-role-dialog')).toBeNull()
    expect(mockMemberApi.changeRole).not.toHaveBeenCalled()
  })

  it('calls changeRole API and updates list on confirm', async () => {
    const updatedMember: api.MemberResponse = { ...makeMember(), role: 'viewer' }
    mockMemberApi.changeRole.mockResolvedValue(updatedMember)

    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`change-role-btn-${MEMBER_ID}`))
    const select = screen.getByTestId('new-role-select') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'viewer' } })
    fireEvent.click(screen.getByTestId('confirm-role-change-btn'))

    await waitFor(() => expect(mockMemberApi.changeRole).toHaveBeenCalledWith(
      ORG_ID,
      MEMBER_ID,
      { role: 'viewer' },
    ))
    expect(screen.queryByTestId('change-role-dialog')).toBeNull()
  })

  it('shows error on role-change API failure', async () => {
    mockMemberApi.changeRole.mockRejectedValue(
      new api.ApiError('LAST_ADMIN', 'Cannot change role: last Owner/Admin.')
    )

    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`change-role-btn-${MEMBER_ID}`))
    const select = screen.getByTestId('new-role-select') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'viewer' } })
    fireEvent.click(screen.getByTestId('confirm-role-change-btn'))

    await waitFor(() => screen.getByTestId('member-action-error'))
    expect(screen.getByText('Cannot change role: last Owner/Admin.')).toBeTruthy()
  })

  // -----------------------------------------------------------------------
  // AC3 — Remove dialog
  // -----------------------------------------------------------------------

  it('opens remove confirmation dialog on button click', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`remove-btn-${MEMBER_ID}`))
    expect(screen.getByTestId('remove-member-dialog')).toBeTruthy()
    expect(screen.getByText(ORG_NAME)).toBeTruthy()
  })

  it('cancels remove dialog without API call', async () => {
    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`remove-btn-${MEMBER_ID}`))
    fireEvent.click(screen.getByTestId('cancel-remove-btn'))
    expect(screen.queryByTestId('remove-member-dialog')).toBeNull()
    expect(mockMemberApi.removeMember).not.toHaveBeenCalled()
  })

  it('calls removeMember and removes row from list on confirm', async () => {
    mockMemberApi.removeMember.mockResolvedValue({
      message: 'Member removed successfully.',
      removed_at: new Date().toISOString(),
    })

    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`remove-btn-${MEMBER_ID}`))
    fireEvent.click(screen.getByTestId('confirm-remove-btn'))

    await waitFor(() => expect(mockMemberApi.removeMember).toHaveBeenCalledWith(ORG_ID, MEMBER_ID))
    expect(screen.queryByTestId(`member-row-${MEMBER_ID}`)).toBeNull()
  })

  it('shows error on remove API failure', async () => {
    mockMemberApi.removeMember.mockRejectedValue(
      new api.ApiError('LAST_ADMIN', 'Cannot remove: last Owner/Admin.')
    )

    renderList({ currentUserId: OWNER_ID, currentUserRole: 'owner' })
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    fireEvent.click(screen.getByTestId(`remove-btn-${MEMBER_ID}`))
    fireEvent.click(screen.getByTestId('confirm-remove-btn'))

    await waitFor(() => screen.getByTestId('member-action-error'))
    expect(screen.getByText('Cannot remove: last Owner/Admin.')).toBeTruthy()
  })

  // -----------------------------------------------------------------------
  // AC1 — Pagination
  // -----------------------------------------------------------------------

  it('renders pagination controls when more than one page', async () => {
    mockMemberApi.list.mockResolvedValue({
      members: [makeMember()],
      total: 50,
      page: 1,
      per_page: 25,
    })
    renderList()
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())
    expect(screen.getByTestId('next-page-btn')).toBeTruthy()
    expect(screen.getByTestId('prev-page-btn')).toBeTruthy()
  })

  it('does not render pagination for single page', async () => {
    renderList()
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())
    expect(screen.queryByTestId('next-page-btn')).toBeNull()
  })

  // -----------------------------------------------------------------------
  // AC1 — Search
  // -----------------------------------------------------------------------

  it('calls list API with search query on Enter', async () => {
    renderList()
    await waitFor(() => expect(screen.queryByTestId('members-loading')).toBeNull())

    const searchInput = screen.getByTestId('member-search-input')
    fireEvent.change(searchInput, { target: { value: 'alice' } })
    fireEvent.keyDown(searchInput, { key: 'Enter' })

    await waitFor(() =>
      expect(mockMemberApi.list).toHaveBeenCalledWith(
        ORG_ID,
        expect.objectContaining({ q: 'alice' }),
      )
    )
  })
})
