/**
 * Frontend Tests — ProjectListPage
 * Story: 1-11-project-management-archive-delete-list (Task 6.10)
 * AC1  — table renders with correct columns, loading state, empty state
 * AC2  — status filter (active/archived/all) persisted in URL; defaults to active
 * AC3  — archive dialog shown on Archive action; confirms and calls API
 * AC4  — restore action visible only on archived projects; confirms and calls API
 * AC5  — delete dialog: name input required (case-sensitive); Delete disabled until match
 * AC6  — health indicator placeholder '—' always shown
 * AC7  — error toast shown on API failure
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProjectListPage from '../ProjectListPage'

// ---------------------------------------------------------------------------
// API mocks
// ---------------------------------------------------------------------------

const mockList = vi.fn()
const mockArchive = vi.fn()
const mockRestore = vi.fn()
const mockDelete = vi.fn()
const mockNavigate = vi.fn()

vi.mock('@/lib/api', () => ({
  projectApi: {
    list: (...args: unknown[]) => mockList(...args),
    archive: (...args: unknown[]) => mockArchive(...args),
    restore: (...args: unknown[]) => mockRestore(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
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

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const ACTIVE_PROJECT = {
  id: 'proj-active-1',
  name: 'Active Project',
  slug: 'active-project',
  description: 'An active test project',
  app_url: null,
  github_repo_url: null,
  status: 'active',
  is_active: true,
  settings: {},
  created_by: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: null,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-01T00:00:00+00:00',
  member_count: 3,
  health: '—',
}

const ARCHIVED_PROJECT = {
  id: 'proj-archived-1',
  name: 'Archived Project',
  slug: 'archived-project',
  description: 'An archived test project',
  app_url: null,
  github_repo_url: null,
  status: 'archived',
  is_active: false,
  settings: {},
  created_by: 'user-1',
  tenant_id: 'tenant-1',
  organization_id: null,
  created_at: '2026-01-01T00:00:00+00:00',
  updated_at: '2026-01-02T00:00:00+00:00',
  member_count: 2,
  health: '—',
}

function _makePaginatedResponse(projects: typeof ACTIVE_PROJECT[]) {
  return {
    data: projects,
    pagination: {
      page: 1,
      per_page: 20,
      total: projects.length,
      total_pages: 1,
    },
  }
}

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderPage(initialPath = '/projects') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/projects" element={<ProjectListPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// AC1: Table renders correctly
// ---------------------------------------------------------------------------

describe('Project list table', () => {
  it('shows loading state while fetching', async () => {
    mockList.mockReturnValue(new Promise(() => {})) // never resolves
    renderPage()
    // Loading spinner should appear
    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toBeInTheDocument()
    })
  })

  it('renders project rows with correct columns after load', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Active Project')).toBeInTheDocument()
    })

    // Status badge — active project shows "Active"
    expect(screen.getByTestId('badge-active')).toBeInTheDocument()
    // Health indicator placeholder
    expect(screen.getAllByTestId('health-indicator')[0]).toHaveTextContent('—')
    // Member count column
    expect(screen.getByTestId(`member-count-${ACTIVE_PROJECT.id}`)).toHaveTextContent('3')
  })

  it('renders archived project with Archived badge', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([ARCHIVED_PROJECT]))

    renderPage('/projects?status=archived')

    await waitFor(() => {
      expect(screen.getByText('Archived Project')).toBeInTheDocument()
    })

    expect(screen.getByTestId('badge-archived')).toBeInTheDocument()
  })

  it('shows empty state when no projects', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([]))

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// AC2: Status filter
// ---------------------------------------------------------------------------

describe('Status filter (AC2)', () => {
  it('defaults to active status filter', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'active' }),
      )
    })
  })

  it('reads status from URL param', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([ARCHIVED_PROJECT]))

    renderPage('/projects?status=archived')

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'archived' }),
      )
    })
  })

  it('reads all status from URL param', async () => {
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT, ARCHIVED_PROJECT]))

    renderPage('/projects?status=all')

    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'all' }),
      )
    })
  })
})

// ---------------------------------------------------------------------------
// AC6: Health indicator placeholder
// ---------------------------------------------------------------------------

describe('Health indicator (AC6)', () => {
  it('always shows "—" for all projects', async () => {
    mockList.mockResolvedValue(
      _makePaginatedResponse([ACTIVE_PROJECT, ARCHIVED_PROJECT]),
    )

    renderPage('/projects?status=all')

    await waitFor(() => {
      const indicators = screen.getAllByTestId('health-indicator')
      expect(indicators.length).toBe(2)
      indicators.forEach((el) => expect(el).toHaveTextContent('—'))
    })
  })
})

// ---------------------------------------------------------------------------
// AC3: Archive dialog
// ---------------------------------------------------------------------------

describe('Archive dialog (AC3)', () => {
  it('shows archive dialog when Archive is clicked', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    // Open actions dropdown
    const moreBtn = screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`)
    await user.click(moreBtn)

    // Click Archive
    const archiveBtn = screen.getByTestId(`archive-btn-${ACTIVE_PROJECT.id}`)
    await user.click(archiveBtn)

    expect(screen.getByTestId('archive-dialog')).toBeInTheDocument()
    expect(screen.getByText(/all data will be retained/i)).toBeInTheDocument()
  })

  it('calls projectApi.archive on confirm and closes dialog', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))
    mockArchive.mockResolvedValue({ ...ACTIVE_PROJECT, is_active: false, status: 'archived' })

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`archive-btn-${ACTIVE_PROJECT.id}`))

    const confirmBtn = screen.getByTestId('archive-confirm-btn')
    await user.click(confirmBtn)

    await waitFor(() => {
      expect(mockArchive).toHaveBeenCalledWith(ACTIVE_PROJECT.id)
    })

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByTestId('archive-dialog')).not.toBeInTheDocument()
    })
  })

  it('closes archive dialog on Cancel', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`archive-btn-${ACTIVE_PROJECT.id}`))

    await user.click(screen.getByTestId('archive-cancel-btn'))

    await waitFor(() => {
      expect(screen.queryByTestId('archive-dialog')).not.toBeInTheDocument()
    })
    expect(mockArchive).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// AC4: Restore action (archived only)
// ---------------------------------------------------------------------------

describe('Restore action (AC4)', () => {
  it('shows Restore only for archived projects', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ARCHIVED_PROJECT]))

    renderPage('/projects?status=archived')

    await waitFor(() => screen.getByText('Archived Project'))

    await user.click(screen.getByTestId(`actions-btn-${ARCHIVED_PROJECT.id}`))

    expect(screen.getByTestId(`restore-btn-${ARCHIVED_PROJECT.id}`)).toBeInTheDocument()
    // Archive should not appear for an archived project
    expect(screen.queryByTestId(`archive-btn-${ARCHIVED_PROJECT.id}`)).not.toBeInTheDocument()
  })

  it('calls projectApi.restore directly when Restore clicked (no dialog)', async () => {
    // AC4: restore has no heavy confirmation — clicking Restore immediately calls API
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ARCHIVED_PROJECT]))
    mockRestore.mockResolvedValue({ ...ARCHIVED_PROJECT, is_active: true, status: 'active' })

    renderPage('/projects?status=archived')

    await waitFor(() => screen.getByText('Archived Project'))

    await user.click(screen.getByTestId(`actions-btn-${ARCHIVED_PROJECT.id}`))
    await user.click(screen.getByTestId(`restore-btn-${ARCHIVED_PROJECT.id}`))

    await waitFor(() => {
      expect(mockRestore).toHaveBeenCalledWith(ARCHIVED_PROJECT.id)
    })
    // No dialog shown for restore (AC4: no heavy confirmation)
    expect(screen.queryByTestId('delete-dialog')).not.toBeInTheDocument()
    expect(screen.queryByTestId('archive-dialog')).not.toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AC5: Delete dialog (high-friction)
// ---------------------------------------------------------------------------

describe('Delete dialog (AC5)', () => {
  it('shows delete dialog when Delete is clicked', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`delete-btn-${ACTIVE_PROJECT.id}`))

    expect(screen.getByTestId('delete-dialog')).toBeInTheDocument()
    expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument()
  })

  it('Delete button is disabled until project name is typed correctly', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`delete-btn-${ACTIVE_PROJECT.id}`))

    const deleteBtn = screen.getByTestId('delete-confirm-btn')
    const nameInput = screen.getByTestId('delete-confirm-input')

    // Initially disabled
    expect(deleteBtn).toBeDisabled()

    // Partial match — still disabled
    await user.type(nameInput, 'Active')
    expect(deleteBtn).toBeDisabled()

    // Wrong case — still disabled (AC5: case-sensitive)
    await user.clear(nameInput)
    await user.type(nameInput, 'active project')
    expect(deleteBtn).toBeDisabled()

    // Exact match — enabled
    await user.clear(nameInput)
    await user.type(nameInput, 'Active Project')
    expect(deleteBtn).not.toBeDisabled()
  })

  it('calls projectApi.delete with correct id on confirm', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))
    mockDelete.mockResolvedValue(undefined)

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`delete-btn-${ACTIVE_PROJECT.id}`))

    const nameInput = screen.getByTestId('delete-confirm-input')
    await user.type(nameInput, 'Active Project')

    await user.click(screen.getByTestId('delete-confirm-btn'))

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith(ACTIVE_PROJECT.id)
    })

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByTestId('delete-dialog')).not.toBeInTheDocument()
    })
  })

  it('closes delete dialog on Cancel without calling API', async () => {
    const user = userEvent.setup()
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`delete-btn-${ACTIVE_PROJECT.id}`))

    await user.click(screen.getByTestId('delete-cancel-btn'))

    await waitFor(() => {
      expect(screen.queryByTestId('delete-dialog')).not.toBeInTheDocument()
    })
    expect(mockDelete).not.toHaveBeenCalled()
  })
})

// ---------------------------------------------------------------------------
// AC7: Error handling — toast on API failure
// ---------------------------------------------------------------------------

describe('Error handling (AC7)', () => {
  it('shows error toast when archive API fails', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/lib/api')
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))
    mockArchive.mockRejectedValue(
      new ApiError('PROJECT_ALREADY_ARCHIVED', 'Project is already archived.', 400),
    )

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`archive-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId('archive-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toBeInTheDocument()
    })
  })

  it('shows error toast when delete API fails', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/lib/api')
    mockList.mockResolvedValue(_makePaginatedResponse([ACTIVE_PROJECT]))
    mockDelete.mockRejectedValue(
      new ApiError('PROJECT_NOT_FOUND', 'Project not found.', 404),
    )

    renderPage()

    await waitFor(() => screen.getByText('Active Project'))

    await user.click(screen.getByTestId(`actions-btn-${ACTIVE_PROJECT.id}`))
    await user.click(screen.getByTestId(`delete-btn-${ACTIVE_PROJECT.id}`))

    const nameInput = screen.getByTestId('delete-confirm-input')
    await user.type(nameInput, 'Active Project')
    await user.click(screen.getByTestId('delete-confirm-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toBeInTheDocument()
    })
  })

  it('shows error state when list API fails', async () => {
    // list() errors go to `error` state shown as data-testid="error-state"
    const { ApiError } = await import('@/lib/api')
    mockList.mockRejectedValue(
      new ApiError('UNAUTHORIZED', 'Not authenticated.', 401),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
  })
})
