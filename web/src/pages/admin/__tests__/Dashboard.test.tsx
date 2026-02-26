/**
 * Frontend tests — Dashboard
 * Story: 1-12-usage-analytics-audit-logs-basic (Task 7.11)
 * AC1 — MetricCard widgets render with correct values
 * AC1 — Loading state shown while fetching
 * AC1 — Error state shown on API failure
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from '../Dashboard'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

const mockGetMetrics = vi.fn()

vi.mock('@/lib/api', () => ({
  adminApi: {
    getMetrics: (...args: unknown[]) => mockGetMetrics(...args),
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

const METRICS = {
  active_users: 12,
  active_projects: 5,
  test_runs: 0,
  storage_consumed: '—',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
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
// Tests
// ---------------------------------------------------------------------------

describe('Dashboard — loading state', () => {
  it('shows loading spinner while fetching', async () => {
    mockGetMetrics.mockReturnValue(new Promise(() => {})) // never resolves

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('loading-state')).toBeInTheDocument()
    })
  })
})

describe('Dashboard — metrics display (AC1)', () => {
  it('renders all 4 MetricCard widgets with correct values', async () => {
    mockGetMetrics.mockResolvedValue(METRICS)

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('value-active-users')).toBeInTheDocument()
    })

    expect(screen.getByTestId('value-active-users')).toHaveTextContent('12')
    expect(screen.getByTestId('value-active-projects')).toHaveTextContent('5')
    expect(screen.getByTestId('value-test-runs')).toHaveTextContent('0')
    expect(screen.getByTestId('value-storage')).toHaveTextContent('—')
  })

  it('renders neutral trend indicator for each card', async () => {
    mockGetMetrics.mockResolvedValue(METRICS)

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('trend-active-users')).toBeInTheDocument()
    })

    expect(screen.getByTestId('trend-active-projects')).toBeInTheDocument()
    expect(screen.getByTestId('trend-test-runs')).toBeInTheDocument()
    expect(screen.getByTestId('trend-storage')).toBeInTheDocument()
  })

  it('renders metrics grid container', async () => {
    mockGetMetrics.mockResolvedValue(METRICS)

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('metrics-grid')).toBeInTheDocument()
    })
  })
})

describe('Dashboard — error state', () => {
  it('shows error state when API fails', async () => {
    const { ApiError } = await import('@/lib/api')
    mockGetMetrics.mockRejectedValue(
      new ApiError('UNAUTHORIZED', 'Not authenticated.', 401),
    )

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
  })

  it('shows generic error message on non-ApiError', async () => {
    mockGetMetrics.mockRejectedValue(new Error('network error'))

    renderDashboard()

    await waitFor(() => {
      expect(screen.getByTestId('error-state')).toBeInTheDocument()
    })
  })
})
