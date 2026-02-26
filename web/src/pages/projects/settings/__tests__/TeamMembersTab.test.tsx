/**
 * Frontend Tests — TeamMembersTab
 * Story: 1-10-project-team-assignment (Task 7.12)
 * AC: #1 — members table with profile data, empty state
 * AC: #2 — Add Member button (Owner/Admin only), dialog
 * AC: #4 — Remove confirmation dialog
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TeamMembersTab from '../TeamMembersTab'

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

const mockListMembers = vi.fn()
const mockAddMember = vi.fn()
const mockRemoveMember = vi.fn()

vi.mock('@/lib/api', () => ({
  projectApi: {
    listMembers: (...args: unknown[]) => mockListMembers(...args),
    addMember: (...args: unknown[]) => mockAddMember(...args),
    addMembersBulk: vi.fn(),
    removeMember: (...args: unknown[]) => mockRemoveMember(...args),
  },
  memberApi: {
    list: vi.fn().mockResolvedValue({ members: [], total: 0, page: 1, per_page: 25 }),
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
// Test data
// ---------------------------------------------------------------------------

const PROJECT_ID = 'proj-123'

const MEMBER_1 = {
  id: 'mem-1',
  project_id: PROJECT_ID,
  user_id: 'user-1',
  added_by: null,
  tenant_id: 'tenant-1',
  created_at: '2026-02-01T00:00:00Z',
  full_name: 'Alice Smith',
  email: 'alice@example.com',
  avatar_url: null,
  org_role: 'developer',
}

const MEMBER_2 = {
  id: 'mem-2',
  project_id: PROJECT_ID,
  user_id: 'user-2',
  added_by: 'user-1',
  tenant_id: 'tenant-1',
  created_at: '2026-02-02T00:00:00Z',
  full_name: 'Bob Jones',
  email: 'bob@example.com',
  avatar_url: null,
  org_role: 'pm-csm',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderTab(userOrgRole = 'owner') {
  return render(
    <TeamMembersTab projectId={PROJECT_ID} userOrgRole={userOrgRole} />,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TeamMembersTab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockListMembers.mockResolvedValue({ members: [MEMBER_1, MEMBER_2], count: 2 })
  })

  // -------------------------------------------------------------------------
  // AC#1 — Members table
  // -------------------------------------------------------------------------

  describe('Members table (AC#1)', () => {
    it('shows loading indicator while fetching', () => {
      mockListMembers.mockReturnValueOnce(new Promise(() => {}))
      renderTab()
      expect(screen.getByTestId('members-loading')).toBeInTheDocument()
    })

    it('shows load error when API fails', async () => {
      mockListMembers.mockRejectedValueOnce(new Error('Network error'))
      renderTab()
      await waitFor(() => {
        expect(screen.getByTestId('members-load-error')).toBeInTheDocument()
      })
    })

    it('shows empty state when no members', async () => {
      mockListMembers.mockResolvedValueOnce({ members: [], count: 0 })
      renderTab()
      await waitFor(() => {
        expect(screen.getByTestId('members-empty')).toBeInTheDocument()
      })
      expect(screen.getByText(/No team members assigned/i)).toBeInTheDocument()
    })

    it('renders members table after load', async () => {
      renderTab()
      await waitFor(() => {
        expect(screen.getByTestId('members-table')).toBeInTheDocument()
      })
    })

    it('displays member names', async () => {
      renderTab()
      await waitFor(() => {
        expect(screen.getByText('Alice Smith')).toBeInTheDocument()
        expect(screen.getByText('Bob Jones')).toBeInTheDocument()
      })
    })

    it('displays member emails', async () => {
      renderTab()
      await waitFor(() => {
        expect(screen.getByText('alice@example.com')).toBeInTheDocument()
        expect(screen.getByText('bob@example.com')).toBeInTheDocument()
      })
    })

    it('displays org role labels', async () => {
      renderTab()
      await waitFor(() => {
        expect(screen.getByText('Developer')).toBeInTheDocument()
        expect(screen.getByText('PM / CSM')).toBeInTheDocument()
      })
    })

    it('shows initials when no avatar_url', async () => {
      renderTab()
      await waitFor(() => {
        // Alice Smith → 'AS', Bob Jones → 'BJ'
        expect(screen.getByText('AS')).toBeInTheDocument()
        expect(screen.getByText('BJ')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC#2 — Add Member (Owner/Admin only)
  // -------------------------------------------------------------------------

  describe('Add Member (AC#2)', () => {
    it('shows Add Member button for Owner', async () => {
      renderTab('owner')
      await waitFor(() => {
        expect(screen.getByTestId('add-member-btn')).toBeInTheDocument()
      })
    })

    it('hides Add Member button for non-admin roles', async () => {
      renderTab('viewer')
      await waitFor(() => screen.getByTestId('members-table'))
      expect(screen.queryByTestId('add-member-btn')).not.toBeInTheDocument()
    })

    it('opens add dialog on button click', async () => {
      renderTab('owner')
      await waitFor(() => screen.getByTestId('add-member-btn'))
      await userEvent.click(screen.getByTestId('add-member-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('add-member-dialog')).toBeInTheDocument()
      })
    })

    it('closes dialog on Cancel', async () => {
      renderTab('owner')
      await waitFor(() => screen.getByTestId('add-member-btn'))
      await userEvent.click(screen.getByTestId('add-member-btn'))

      await waitFor(() => screen.getByTestId('add-member-dialog'))
      await userEvent.click(screen.getByTestId('add-member-cancel'))

      await waitFor(() => {
        expect(screen.queryByTestId('add-member-dialog')).not.toBeInTheDocument()
      })
    })

    it('calls addMember API and refreshes list on confirm', async () => {
      const newUser = uuid.v4 ? uuid.v4() : 'new-user-uuid'
      mockAddMember.mockResolvedValueOnce({
        ...MEMBER_1,
        user_id: newUser,
      })

      renderTab('owner')
      await waitFor(() => screen.getByTestId('add-member-btn'))
      await userEvent.click(screen.getByTestId('add-member-btn'))

      await waitFor(() => screen.getByTestId('add-member-user-id-input'))
      await userEvent.type(screen.getByTestId('add-member-user-id-input'), newUser)

      await userEvent.click(screen.getByTestId('add-member-confirm'))

      await waitFor(() => {
        expect(mockAddMember).toHaveBeenCalledWith(PROJECT_ID, { user_id: newUser })
      })
    })

    it('shows error when add fails', async () => {
      const { ApiError } = await import('@/lib/api')
      mockAddMember.mockRejectedValueOnce(
        new ApiError('ALREADY_MEMBER', 'User is already a member of this project.', 409),
      )

      renderTab('owner')
      await waitFor(() => screen.getByTestId('add-member-btn'))
      await userEvent.click(screen.getByTestId('add-member-btn'))

      await waitFor(() => screen.getByTestId('add-member-user-id-input'))
      await userEvent.type(screen.getByTestId('add-member-user-id-input'), 'some-user-id')
      await userEvent.click(screen.getByTestId('add-member-confirm'))

      await waitFor(() => {
        expect(screen.getByTestId('add-member-error')).toBeInTheDocument()
      })
      expect(screen.getByTestId('add-member-error').textContent).toMatch(/already a member/i)
    })
  })

  // -------------------------------------------------------------------------
  // AC#4 — Remove Member
  // -------------------------------------------------------------------------

  describe('Remove Member (AC#4)', () => {
    it('shows remove button for Owner', async () => {
      renderTab('owner')
      await waitFor(() => {
        expect(screen.getByTestId('remove-member-0')).toBeInTheDocument()
      })
    })

    it('hides remove button for non-admin', async () => {
      renderTab('viewer')
      await waitFor(() => screen.getByTestId('members-table'))
      expect(screen.queryByTestId('remove-member-0')).not.toBeInTheDocument()
    })

    it('opens confirmation dialog on remove click', async () => {
      renderTab('owner')
      await waitFor(() => screen.getByTestId('remove-member-0'))
      await userEvent.click(screen.getByTestId('remove-member-0'))

      await waitFor(() => {
        expect(screen.getByTestId('remove-member-dialog')).toBeInTheDocument()
      })
    })

    it('mentions member name in confirmation dialog', async () => {
      renderTab('owner')
      await waitFor(() => screen.getByTestId('remove-member-0'))
      await userEvent.click(screen.getByTestId('remove-member-0'))

      await waitFor(() => {
        expect(screen.getByText(/Alice Smith/)).toBeInTheDocument()
      })
    })

    it('dismisses dialog on Cancel', async () => {
      renderTab('owner')
      await waitFor(() => screen.getByTestId('remove-member-0'))
      await userEvent.click(screen.getByTestId('remove-member-0'))

      await waitFor(() => screen.getByTestId('remove-cancel'))
      await userEvent.click(screen.getByTestId('remove-cancel'))

      await waitFor(() => {
        expect(screen.queryByTestId('remove-member-dialog')).not.toBeInTheDocument()
      })
      expect(mockRemoveMember).not.toHaveBeenCalled()
    })

    it('calls removeMember API on confirm', async () => {
      mockRemoveMember.mockResolvedValueOnce(undefined)

      renderTab('owner')
      await waitFor(() => screen.getByTestId('remove-member-0'))
      await userEvent.click(screen.getByTestId('remove-member-0'))

      await waitFor(() => screen.getByTestId('remove-confirm'))
      await userEvent.click(screen.getByTestId('remove-confirm'))

      await waitFor(() => {
        expect(mockRemoveMember).toHaveBeenCalledWith(PROJECT_ID, MEMBER_1.user_id)
      })
    })

    it('shows error when remove fails', async () => {
      mockRemoveMember.mockRejectedValueOnce(new Error('Network error'))

      renderTab('owner')
      await waitFor(() => screen.getByTestId('remove-member-0'))
      await userEvent.click(screen.getByTestId('remove-member-0'))

      await waitFor(() => screen.getByTestId('remove-confirm'))
      await userEvent.click(screen.getByTestId('remove-confirm'))

      await waitFor(() => {
        expect(screen.getByTestId('remove-member-error')).toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // Read-only view for non-Admin members
  // -------------------------------------------------------------------------

  describe('Read-only view', () => {
    it('developer can view members list (read-only)', async () => {
      renderTab('developer')
      await waitFor(() => {
        expect(screen.getByTestId('members-table')).toBeInTheDocument()
      })
      expect(screen.queryByTestId('add-member-btn')).not.toBeInTheDocument()
      expect(screen.queryByTestId('remove-member-0')).not.toBeInTheDocument()
    })

    it('viewer sees member info but no actions', async () => {
      renderTab('viewer')
      await waitFor(() => {
        expect(screen.getByText('Alice Smith')).toBeInTheDocument()
      })
      expect(screen.queryByTestId('add-member-btn')).not.toBeInTheDocument()
    })
  })
})

// Simple UUID v4 fallback for test data
const uuid = {
  v4: () =>
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    }),
}
