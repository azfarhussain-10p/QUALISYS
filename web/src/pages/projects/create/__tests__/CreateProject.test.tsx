/**
 * Frontend Tests — CreateProjectPage
 * Story: 1-9-project-creation-configuration (Task 6.8)
 * AC1 — form renders with required fields (name) and optional fields
 * AC6 — duplicate name error displayed from server response
 * AC7 — client-side validation: name (3-100), URL formats, GitHub URL pattern
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import CreateProjectPage from '../CreateProjectPage'

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

const mockCreate = vi.fn()
const mockNavigate = vi.fn()

vi.mock('@/lib/api', () => ({
  projectApi: {
    create: (...args: unknown[]) => mockCreate(...args),
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
// Render helper
// ---------------------------------------------------------------------------

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/projects/new']}>
      <Routes>
        <Route path="/projects/new" element={<CreateProjectPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CreateProjectPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -------------------------------------------------------------------------
  // AC1 — Form render
  // -------------------------------------------------------------------------

  describe('Form render (AC1)', () => {
    it('renders the create project form', () => {
      renderPage()
      expect(screen.getByTestId('create-project-form')).toBeInTheDocument()
    })

    it('renders project name input (required)', () => {
      renderPage()
      expect(screen.getByTestId('input-project-name')).toBeInTheDocument()
    })

    it('renders description textarea (optional)', () => {
      renderPage()
      expect(screen.getByTestId('input-description')).toBeInTheDocument()
    })

    it('renders application URL input (optional)', () => {
      renderPage()
      expect(screen.getByTestId('input-app-url')).toBeInTheDocument()
    })

    it('renders GitHub repo URL input (optional)', () => {
      renderPage()
      expect(screen.getByTestId('input-github-url')).toBeInTheDocument()
    })

    it('renders submit button', () => {
      renderPage()
      expect(screen.getByTestId('submit-btn')).toBeInTheDocument()
    })

    it('submit button is disabled when form is empty (onChange mode)', () => {
      renderPage()
      // With mode: onChange, submit is disabled when form is not yet valid
      expect(screen.getByTestId('submit-btn')).toBeDisabled()
    })
  })

  // -------------------------------------------------------------------------
  // AC7 — Client-side validation: name
  // -------------------------------------------------------------------------

  describe('Name validation (AC7)', () => {
    it('shows error when name is too short (< 3 chars)', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'AB')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-name')).toBeInTheDocument()
      })
      expect(screen.getByTestId('error-name').textContent).toMatch(/3/)
    })

    it('enables submit button when name is valid (≥3 chars)', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Project Name')

      await waitFor(() => {
        expect(screen.getByTestId('submit-btn')).not.toBeDisabled()
      })
    })

    it('shows no error for valid name', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'My Test Project')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.queryByTestId('error-name')).not.toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC7 — Client-side validation: Application URL
  // -------------------------------------------------------------------------

  describe('Application URL validation (AC7)', () => {
    it('shows error for non-HTTP URL', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(screen.getByTestId('input-app-url'), 'not-a-url')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-app-url')).toBeInTheDocument()
      })
    })

    it('shows error for javascript: scheme', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(screen.getByTestId('input-app-url'), 'javascript:alert(1)')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-app-url')).toBeInTheDocument()
      })
    })

    it('accepts valid HTTPS URL', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(screen.getByTestId('input-app-url'), 'https://app.example.com')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.queryByTestId('error-app-url')).not.toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC7 — Client-side validation: GitHub URL
  // -------------------------------------------------------------------------

  describe('GitHub URL validation (AC7)', () => {
    it('shows error for non-GitHub URL', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(screen.getByTestId('input-github-url'), 'https://gitlab.com/owner/repo')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-github-url')).toBeInTheDocument()
      })
    })

    it('shows error for GitHub URL missing repo path', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(screen.getByTestId('input-github-url'), 'https://github.com/owner')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-github-url')).toBeInTheDocument()
      })
    })

    it('accepts valid GitHub URL', async () => {
      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Valid Name')
      await userEvent.type(
        screen.getByTestId('input-github-url'),
        'https://github.com/owner/repo',
      )
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.queryByTestId('error-github-url')).not.toBeInTheDocument()
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC1 — Successful submission → navigate to project
  // -------------------------------------------------------------------------

  describe('Successful submission (AC1)', () => {
    it('calls projectApi.create with trimmed name and navigates on success', async () => {
      mockCreate.mockResolvedValueOnce({
        id: 'proj-123',
        name: 'My Project',
        slug: 'my-project',
        tenant_id: 'tenant-1',
      })

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'My Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'My Project' }),
        )
        expect(mockNavigate).toHaveBeenCalledWith('/projects/my-project', { replace: true })
      })
    })

    it('trims whitespace from name before submitting', async () => {
      mockCreate.mockResolvedValueOnce({
        id: 'proj-123',
        name: 'My Project',
        slug: 'my-project',
        tenant_id: 'tenant-1',
      })

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), '  My Project  ')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'My Project' }),
        )
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC6 — Duplicate project name error
  // -------------------------------------------------------------------------

  describe('Duplicate name error (AC6)', () => {
    it('shows duplicate name server error when API returns DUPLICATE_SLUG', async () => {
      const { ApiError } = await import('@/lib/api')
      mockCreate.mockRejectedValueOnce(
        new ApiError('DUPLICATE_SLUG', 'A project with this slug already exists.', 400),
      )

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Existing Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error')).toBeInTheDocument()
      })
      expect(screen.getByTestId('server-error').textContent).toMatch(/already exists/i)
    })

    it('shows "already exists" message when API error message contains "already exists"', async () => {
      const { ApiError } = await import('@/lib/api')
      mockCreate.mockRejectedValueOnce(
        new ApiError('CONFLICT', 'A project with this name already exists.', 400),
      )

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'Duplicate Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error').textContent).toMatch(/already exists/i)
      })
    })
  })

  // -------------------------------------------------------------------------
  // Error handling
  // -------------------------------------------------------------------------

  describe('Generic error handling', () => {
    it('shows generic error message for non-ApiError exceptions', async () => {
      mockCreate.mockRejectedValueOnce(new Error('Network failure'))

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'My Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('server-error')).toBeInTheDocument()
      })
      expect(screen.getByTestId('server-error').textContent).toMatch(/something went wrong/i)
    })
  })

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('Loading state', () => {
    it('shows "Creating project…" text while submitting', async () => {
      mockCreate.mockReturnValueOnce(new Promise(() => {}))  // never resolves

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'My Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByText(/Creating project/i)).toBeInTheDocument()
      })
    })

    it('disables submit button while submitting', async () => {
      mockCreate.mockReturnValueOnce(new Promise(() => {}))

      renderPage()
      await userEvent.type(screen.getByTestId('input-project-name'), 'My Project')
      await userEvent.click(screen.getByTestId('submit-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('submit-btn')).toBeDisabled()
      })
    })
  })
})
