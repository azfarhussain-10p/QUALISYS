/**
 * Frontend Tests — ProjectSettingsPage
 * Story: 1-9-project-creation-configuration (Task 6.8)
 * AC3 — editable general settings, name-change confirmation dialog
 * AC4 — advanced settings section (collapsible): environment, browser, tags
 * AC7 — client-side validation on save
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ProjectSettingsPage from '../ProjectSettingsPage'

// ---------------------------------------------------------------------------
// API mock
// ---------------------------------------------------------------------------

const mockGetSettings = vi.fn()
const mockUpdate = vi.fn()

vi.mock('@/lib/api', () => ({
  projectApi: {
    getSettings: (...args: unknown[]) => mockGetSettings(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
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
// Helpers
// ---------------------------------------------------------------------------

const DEFAULT_SETTINGS = {
  id: 'proj-123',
  name: 'Original Project',
  slug: 'original-project',
  description: 'Project description',
  app_url: 'https://app.example.com',
  github_repo_url: 'https://github.com/owner/repo',
  default_environment: 'staging',
  default_browser: 'chromium',
  tags: ['smoke', 'regression'],
}

function renderPage(projectId = 'proj-123') {
  return render(
    <MemoryRouter initialEntries={[`/projects/${projectId}/settings`]}>
      <Routes>
        <Route path="/projects/:projectId/settings" element={<ProjectSettingsPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ProjectSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetSettings.mockResolvedValue(DEFAULT_SETTINGS)
    mockUpdate.mockResolvedValue({ ...DEFAULT_SETTINGS })
  })

  // -------------------------------------------------------------------------
  // AC3 — General settings render and load
  // -------------------------------------------------------------------------

  describe('Settings load (AC3)', () => {
    it('shows loading spinner while fetching', () => {
      mockGetSettings.mockReturnValueOnce(new Promise(() => {}))
      renderPage()
      expect(screen.getByTestId('loading')).toBeInTheDocument()
    })

    it('shows load error when API fails', async () => {
      mockGetSettings.mockRejectedValueOnce(new Error('Network error'))
      renderPage()

      await waitFor(() => {
        expect(screen.getByTestId('load-error')).toBeInTheDocument()
      })
    })

    it('renders settings form after successful load', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByTestId('settings-form')).toBeInTheDocument()
      })
    })

    it('pre-populates name input from loaded settings', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByTestId('input-name')).toHaveValue('Original Project')
      })
    })

    it('pre-populates description from loaded settings', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByTestId('input-description')).toHaveValue('Project description')
      })
    })

    it('pre-populates application URL from loaded settings', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByTestId('input-app-url')).toHaveValue('https://app.example.com')
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC3 — Name change confirmation dialog
  // -------------------------------------------------------------------------

  describe('Name change confirmation dialog (AC3)', () => {
    it('shows name-change-warning when name is modified', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-name'))

      await userEvent.triple_click(screen.getByTestId('input-name'))
      await userEvent.type(screen.getByTestId('input-name'), 'Updated Project Name')

      await waitFor(() => {
        expect(screen.getByTestId('name-change-warning')).toBeInTheDocument()
      })
    })

    it('shows confirmation dialog when name is changed and save is clicked', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-name'))

      // Clear and type new name
      await userEvent.triple_click(screen.getByTestId('input-name'))
      await userEvent.type(screen.getByTestId('input-name'), 'Completely New Name')

      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('name-change-confirm')).toBeInTheDocument()
      })
    })

    it('dismisses confirmation dialog on Cancel', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-name'))

      await userEvent.triple_click(screen.getByTestId('input-name'))
      await userEvent.type(screen.getByTestId('input-name'), 'New Name Here')
      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => screen.getByTestId('name-change-confirm'))
      await userEvent.click(screen.getByTestId('confirm-cancel'))

      await waitFor(() => {
        expect(screen.queryByTestId('name-change-confirm')).not.toBeInTheDocument()
      })
      expect(mockUpdate).not.toHaveBeenCalled()
    })

    it('calls update API after confirmation', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-name'))

      await userEvent.triple_click(screen.getByTestId('input-name'))
      await userEvent.type(screen.getByTestId('input-name'), 'Confirmed New Name')
      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => screen.getByTestId('name-change-confirm'))
      await userEvent.click(screen.getByTestId('confirm-name-change'))

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalled()
      })
    })

    it('dialog mentions URL update impact (AC3)', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-name'))

      await userEvent.triple_click(screen.getByTestId('input-name'))
      await userEvent.type(screen.getByTestId('input-name'), 'Changed Name')
      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => screen.getByTestId('name-change-confirm'))
      expect(screen.getByText(/update the project url/i)).toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // AC4 — Advanced section (collapsible)
  // -------------------------------------------------------------------------

  describe('Advanced settings section (AC4)', () => {
    it('advanced section is hidden by default', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))

      expect(screen.queryByTestId('advanced-section')).not.toBeInTheDocument()
    })

    it('clicking toggle reveals advanced section', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))

      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => {
        expect(screen.getByTestId('advanced-section')).toBeInTheDocument()
      })
    })

    it('shows environment dropdown in advanced section', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => {
        expect(screen.getByTestId('select-environment')).toBeInTheDocument()
      })
    })

    it('shows browser dropdown in advanced section', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => {
        expect(screen.getByTestId('select-browser')).toBeInTheDocument()
      })
    })

    it('pre-loaded tags are displayed', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => {
        expect(screen.getByTestId('tags-list')).toBeInTheDocument()
      })
      expect(screen.getByText('smoke')).toBeInTheDocument()
      expect(screen.getByText('regression')).toBeInTheDocument()
    })

    it('can add a new tag', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => screen.getByTestId('tag-input'))
      await userEvent.type(screen.getByTestId('tag-input'), 'performance')
      await userEvent.click(screen.getByTestId('add-tag-btn'))

      await waitFor(() => {
        expect(screen.getByText('performance')).toBeInTheDocument()
      })
    })

    it('can remove a tag', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => screen.getByTestId('remove-tag-0'))
      await userEvent.click(screen.getByTestId('remove-tag-0'))

      await waitFor(() => {
        expect(screen.queryByText('smoke')).not.toBeInTheDocument()
      })
    })

    it('shows error when adding more than 10 tags', async () => {
      // Load with 10 tags already
      mockGetSettings.mockResolvedValueOnce({
        ...DEFAULT_SETTINGS,
        tags: ['t1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10'],
      })

      renderPage()
      await waitFor(() => screen.getByTestId('toggle-advanced'))
      await userEvent.click(screen.getByTestId('toggle-advanced'))

      await waitFor(() => screen.getByTestId('tag-input'))
      await userEvent.type(screen.getByTestId('tag-input'), 'eleventh-tag')
      await userEvent.click(screen.getByTestId('add-tag-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('tag-error')).toBeInTheDocument()
      })
      expect(screen.getByTestId('tag-error').textContent).toMatch(/10/i)
    })
  })

  // -------------------------------------------------------------------------
  // AC3 — Save success and error states
  // -------------------------------------------------------------------------

  describe('Save states', () => {
    it('shows success message after save', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-description'))

      // Change description (to make form dirty)
      await userEvent.triple_click(screen.getByTestId('input-description'))
      await userEvent.type(screen.getByTestId('input-description'), 'New description text')

      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('save-success')).toBeInTheDocument()
      })
    })

    it('shows error message when update API fails', async () => {
      mockUpdate.mockRejectedValueOnce(new Error('Network error'))

      renderPage()
      await waitFor(() => screen.getByTestId('input-description'))

      await userEvent.triple_click(screen.getByTestId('input-description'))
      await userEvent.type(screen.getByTestId('input-description'), 'Change to trigger dirty')

      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('save-error')).toBeInTheDocument()
      })
    })

    it('shows ApiError message from server on save failure', async () => {
      const { ApiError } = await import('@/lib/api')
      mockUpdate.mockRejectedValueOnce(
        new ApiError('VALIDATION_ERROR', 'Name already in use.', 400),
      )

      renderPage()
      await waitFor(() => screen.getByTestId('input-description'))

      await userEvent.triple_click(screen.getByTestId('input-description'))
      await userEvent.type(screen.getByTestId('input-description'), 'Any change')

      await userEvent.click(screen.getByTestId('save-btn'))

      await waitFor(() => {
        expect(screen.getByTestId('save-error').textContent).toMatch(/Name already in use/i)
      })
    })
  })

  // -------------------------------------------------------------------------
  // AC7 — Validation on settings form
  // -------------------------------------------------------------------------

  describe('Settings validation (AC7)', () => {
    it('shows error for invalid app_url', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-app-url'))

      await userEvent.triple_click(screen.getByTestId('input-app-url'))
      await userEvent.type(screen.getByTestId('input-app-url'), 'not-a-url')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-app-url')).toBeInTheDocument()
      })
    })

    it('shows error for invalid github_repo_url', async () => {
      renderPage()
      await waitFor(() => screen.getByTestId('input-github-url'))

      await userEvent.triple_click(screen.getByTestId('input-github-url'))
      await userEvent.type(screen.getByTestId('input-github-url'), 'https://gitlab.com/owner/repo')
      await userEvent.tab()

      await waitFor(() => {
        expect(screen.getByTestId('error-github-url')).toBeInTheDocument()
      })
    })
  })
})
