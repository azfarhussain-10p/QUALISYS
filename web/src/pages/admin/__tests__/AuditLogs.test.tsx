/**
 * Frontend tests — AuditLogs
 * Story: 1-12-usage-analytics-audit-logs-basic (Task 7.11)
 * AC4 — table renders with correct columns, pagination
 * AC5 — filter bar: date presets, action type, actor UUID; chips; URL persistence
 * AC6 — Export CSV button, loading state, error toast
 * AC8 — empty state, error state
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import AuditLogs from '../AuditLogs'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

const mockGetAuditLogs = vi.fn()
const mockExportAuditLogs = vi.fn()

vi.mock('@/lib/api', () => ({
  adminApi: {
    getAuditLogs: (...args: unknown[]) => mockGetAuditLogs(...args),
    exportAuditLogs: (...args: unknown[]) => mockExportAuditLogs(...args),
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
// Fixtures
// ---------------------------------------------------------------------------

const ENTRY_1 = {
  id: 'entry-1',
  tenant_id: 'tenant-1',
  actor_user_id: 'aaaa-bbbb-cccc-dddd-eeee',
  action: 'project.archived',
  resource_type: 'project',
  resource_id: 'proj-1',
  details: { project_name: 'Alpha' },
  ip_address: '1.2.3.4',
  user_agent: 'pytest',
  created_at: '2026-01-15T10:00:00+00:00',
}

const ENTRY_2 = {
  id: 'entry-2',
  tenant_id: 'tenant-1',
  actor_user_id: 'ffff-1111-2222-3333-4444',
  action: 'user.invited',
  resource_type: 'invitation',
  resource_id: null,
  details: { email: 'user@example.com' },
  ip_address: null,
  user_agent: null,
  created_at: '2026-01-14T09:00:00+00:00',
}

function _makePaginatedResponse(entries: typeof ENTRY_1[]) {
  return {
    data: entries,
    pagination: {
      page: 1,
      per_page: 50,
      total: entries.length,
      total_pages: 1,
    },
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderPage(initialPath = '/admin/audit-logs') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/admin/audit-logs" element={<AuditLogs />} />
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
// AC4: Table renders
// ---------------------------------------------------------------------------

describe('Audit log table (AC4)', () => {
  it('shows loading state while fetching', async () => {
    mockGetAuditLogs.mockReturnValue(new Promise(() => {}))
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toBeInTheDocument()
    })
  })

  it('renders rows with action and resource type after load', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([ENTRY_1, ENTRY_2]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('audit-log-table')).toBeInTheDocument()
    })

    expect(screen.getByTestId(`action-${ENTRY_1.id}`)).toBeInTheDocument()
    expect(screen.getByTestId(`resource-type-${ENTRY_1.id}`)).toHaveTextContent('project')
    expect(screen.getByTestId(`action-${ENTRY_2.id}`)).toBeInTheDocument()
  })

  it('shows empty state when no entries', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    })

    expect(screen.getByText(/no audit entries match/i)).toBeInTheDocument()
  })

  it('shows error state when API fails', async () => {
    const { ApiError } = await import('@/lib/api')
    mockGetAuditLogs.mockRejectedValue(new ApiError('UNAUTHORIZED', 'Not authenticated.', 401))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// AC5: Filter bar
// ---------------------------------------------------------------------------

describe('Filter bar (AC5)', () => {
  it('renders date preset buttons', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('preset-7d')).toBeInTheDocument()
    })

    expect(screen.getByTestId('preset-30d')).toBeInTheDocument()
    expect(screen.getByTestId('preset-90d')).toBeInTheDocument()
  })

  it('renders action type dropdown', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('action-filter')).toBeInTheDocument()
    })
  })

  it('renders actor UUID input', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('actor-filter')).toBeInTheDocument()
    })
  })

  it('shows active chip when date preset is selected', async () => {
    const user = userEvent.setup()
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => screen.getByTestId('preset-7d'))

    await user.click(screen.getByTestId('preset-7d'))

    await waitFor(() => {
      expect(screen.getByTestId('chip-date')).toBeInTheDocument()
    })
  })

  it('removes chip when X is clicked', async () => {
    const user = userEvent.setup()
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => screen.getByTestId('preset-7d'))
    await user.click(screen.getByTestId('preset-7d'))
    await waitFor(() => screen.getByTestId('chip-date'))

    // Click the remove button on the chip
    const chip = screen.getByTestId('chip-date')
    const removeBtn = within(chip).getByRole('button')
    await user.click(removeBtn)

    await waitFor(() => {
      expect(screen.queryByTestId('chip-date')).not.toBeInTheDocument()
    })
  })

  it('reads action filter from URL param', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([ENTRY_1]))
    renderPage('/admin/audit-logs?action=project_actions')

    await waitFor(() => {
      expect(mockGetAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({ action: 'project_actions' }),
      )
    })
  })
})

// ---------------------------------------------------------------------------
// AC6: Export CSV
// ---------------------------------------------------------------------------

describe('Export CSV (AC6)', () => {
  it('shows Export CSV button', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('export-btn')).toBeInTheDocument()
    })
  })

  it('shows loading on export button while exporting', async () => {
    const user = userEvent.setup()
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    // Export never resolves
    mockExportAuditLogs.mockReturnValue(new Promise(() => {}))

    renderPage()

    await waitFor(() => screen.getByTestId('export-btn'))
    await user.click(screen.getByTestId('export-btn'))

    // Button should be in disabled/loading state
    await waitFor(() => {
      expect(screen.getByTestId('export-btn')).toBeDisabled()
    })
  })

  it('shows error toast when export API fails', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/lib/api')
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([]))
    mockExportAuditLogs.mockRejectedValue(
      new ApiError('RATE_LIMIT_EXCEEDED', 'Export limit reached.', 429),
    )

    renderPage()

    await waitFor(() => screen.getByTestId('export-btn'))
    await user.click(screen.getByTestId('export-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('toast-error')).toBeInTheDocument()
    })

    expect(screen.getByTestId('toast-error')).toHaveTextContent(/export limit/i)
  })
})

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

describe('Pagination', () => {
  it('shows pagination when total_pages > 1', async () => {
    mockGetAuditLogs.mockResolvedValue({
      data: [ENTRY_1],
      pagination: { page: 1, per_page: 50, total: 120, total_pages: 3 },
    })

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('pagination')).toBeInTheDocument()
    })

    expect(screen.getByTestId('next-page')).toBeInTheDocument()
    expect(screen.getByTestId('prev-page')).toBeDisabled() // page 1 → prev disabled
  })

  it('hides pagination when only 1 page', async () => {
    mockGetAuditLogs.mockResolvedValue(_makePaginatedResponse([ENTRY_1]))
    renderPage()

    await waitFor(() => screen.getByTestId('audit-log-table'))
    expect(screen.queryByTestId('pagination')).not.toBeInTheDocument()
  })
})
