/**
 * Frontend tests — DataExport component
 * Story: 1-13-data-export-org-deletion (Task 7.12)
 * AC: #1, #2, #5 — export button, progress indicator, history, download links
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DataExport from '../DataExport'

// ---------------------------------------------------------------------------
// Mock API
// ---------------------------------------------------------------------------

const mockRequestExport = vi.fn()
const mockListExports = vi.fn()
const mockGetEstimate = vi.fn()

vi.mock('@/lib/api', () => ({
  exportApi: {
    requestExport: (...args: unknown[]) => mockRequestExport(...args),
    listExports: (...args: unknown[]) => mockListExports(...args),
    getEstimate: (...args: unknown[]) => mockGetEstimate(...args),
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

const EMPTY_EXPORTS = { exports: [] }

const COMPLETED_JOB = {
  job_id: 'job-1',
  status: 'completed' as const,
  progress_percent: 100,
  file_size_bytes: 10240,
  error: null,
  created_at: '2026-02-25T10:00:00Z',
  completed_at: '2026-02-25T10:05:00Z',
  download_url: 'https://s3.example.com/presigned',
}

const PROCESSING_JOB = {
  job_id: 'job-2',
  status: 'processing' as const,
  progress_percent: 45,
  file_size_bytes: null,
  error: null,
  created_at: '2026-02-25T11:00:00Z',
  completed_at: null,
  download_url: null,
}

const FAILED_JOB = {
  job_id: 'job-3',
  status: 'failed' as const,
  progress_percent: 0,
  file_size_bytes: null,
  error: 'S3 upload failed',
  created_at: '2026-02-25T09:00:00Z',
  completed_at: null,
  download_url: null,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderDataExport(props?: { orgId?: string; userRole?: string }) {
  return render(
    <DataExport
      orgId={props?.orgId ?? 'org-123'}
      userRole={props?.userRole ?? 'owner'}
    />,
  )
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const EMPTY_ESTIMATE = { tables: {}, total_records: 0, note: '' }

beforeEach(() => {
  vi.clearAllMocks()
  // Default: estimate resolves to empty (non-critical path)
  mockGetEstimate.mockResolvedValue(EMPTY_ESTIMATE)
})

// ---------------------------------------------------------------------------
// AC1: Owner-only gating
// ---------------------------------------------------------------------------

describe('Owner-only visibility', () => {
  it('renders nothing for non-owner roles', () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    const { container } = renderDataExport({ userRole: 'admin' })
    expect(container.firstChild).toBeNull()
  })

  it('renders the export section for owner role', async () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    renderDataExport({ userRole: 'owner' })
    await waitFor(() => {
      expect(screen.getByTestId('data-export-section')).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// AC2: Export button
// ---------------------------------------------------------------------------

describe('Export button', () => {
  it('renders Export All Data button', async () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    renderDataExport()
    await waitFor(() => {
      expect(screen.getByTestId('export-data-btn')).toBeInTheDocument()
    })
  })

  it('shows loading state while exporting', async () => {
    const user = userEvent.setup()
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    // Export never resolves
    mockRequestExport.mockReturnValue(new Promise(() => {}))

    renderDataExport()
    await waitFor(() => screen.getByTestId('export-data-btn'))
    await user.click(screen.getByTestId('export-data-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('export-data-btn')).toBeDisabled()
    })
  })

  it('shows success message after export requested', async () => {
    const user = userEvent.setup()
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    mockRequestExport.mockResolvedValue({ job_id: 'job-new', status: 'processing', estimated_duration: '2-5 min' })

    renderDataExport()
    await waitFor(() => screen.getByTestId('export-data-btn'))
    await user.click(screen.getByTestId('export-data-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('export-success')).toBeInTheDocument()
    })
  })

  it('shows error when export request fails', async () => {
    const user = userEvent.setup()
    const { ApiError } = await import('@/lib/api')
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    mockRequestExport.mockRejectedValue(
      new ApiError('RATE_LIMIT_EXCEEDED', 'Export limited to 1 per org per 24 hours.', 429),
    )

    renderDataExport()
    await waitFor(() => screen.getByTestId('export-data-btn'))
    await user.click(screen.getByTestId('export-data-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('export-error')).toBeInTheDocument()
    })
    expect(screen.getByTestId('export-error')).toHaveTextContent(/24 hours/i)
  })
})

// ---------------------------------------------------------------------------
// AC5: Export history
// ---------------------------------------------------------------------------

describe('Export history', () => {
  it('shows "No exports yet" when history is empty', async () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    renderDataExport()
    await waitFor(() => {
      expect(screen.getByTestId('no-exports')).toBeInTheDocument()
    })
  })

  it('renders export history with completed job', async () => {
    mockListExports.mockResolvedValue({ exports: [COMPLETED_JOB] })
    renderDataExport()
    await waitFor(() => {
      expect(screen.getByTestId('export-history')).toBeInTheDocument()
    })
    expect(screen.getByTestId('export-job-job-1')).toBeInTheDocument()
    expect(screen.getByText(/completed/i)).toBeInTheDocument()
  })

  it('shows download link for completed job', async () => {
    mockListExports.mockResolvedValue({ exports: [COMPLETED_JOB] })
    renderDataExport()
    await waitFor(() => screen.getByTestId('download-job-1'))
    const link = screen.getByTestId('download-job-1')
    expect(link).toHaveAttribute('href', 'https://s3.example.com/presigned')
  })

  it('shows processing status with progress percent', async () => {
    mockListExports.mockResolvedValue({ exports: [PROCESSING_JOB] })
    renderDataExport()
    await waitFor(() => screen.getByTestId('export-job-job-2'))
    expect(screen.getByText(/processing/i)).toBeInTheDocument()
    expect(screen.getByText(/45%/i)).toBeInTheDocument()
  })

  it('shows failed status with error message', async () => {
    mockListExports.mockResolvedValue({ exports: [FAILED_JOB] })
    renderDataExport()
    await waitFor(() => screen.getByTestId('export-job-job-3'))
    expect(screen.getByText(/failed/i)).toBeInTheDocument()
    expect(screen.getByText(/S3 upload failed/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// AC1: Pre-export size estimate
// ---------------------------------------------------------------------------

describe('Pre-export size estimate', () => {
  it('shows data summary when estimate is available', async () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    mockGetEstimate.mockResolvedValue({
      tables: { projects: 5, project_members: 12, audit_logs: 100 },
      total_records: 117,
      note: 'Estimate based on current row counts.',
    })
    renderDataExport()
    await waitFor(() => {
      expect(screen.getByTestId('export-estimate')).toBeInTheDocument()
    })
    expect(screen.getByText(/117/)).toBeInTheDocument()
    expect(screen.getByText('projects')).toBeInTheDocument()
  })

  it('does not show estimate section when estimate fetch fails', async () => {
    mockListExports.mockResolvedValue(EMPTY_EXPORTS)
    mockGetEstimate.mockRejectedValue(new Error('network error'))
    renderDataExport()
    await waitFor(() => screen.getByTestId('data-export-section'))
    expect(screen.queryByTestId('export-estimate')).not.toBeInTheDocument()
  })
})
