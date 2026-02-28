/**
 * Project Settings Page
 * Story: 1-9-project-creation-configuration
 * AC: AC3 — /projects/{slug}/settings accessible to Owner/Admin; editable name, description, URLs
 * AC: AC4 — Advanced section (collapsible): default environment, browser, project tags
 * AC: AC3 — Name change triggers slug regeneration confirmation dialog
 */

import { useState, useEffect, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useParams } from 'react-router-dom'
import { ChevronDown, ChevronUp, Loader2, Settings2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, ProjectSettingsResponse, projectApi } from '@/lib/api'
import TeamMembersTab from './TeamMembersTab'
import DocumentsTab from '../documents/DocumentsTab'
import AgentsTab from '../agents/AgentsTab'

// ---------------------------------------------------------------------------
// Validation schema — AC3, AC4, AC7
// ---------------------------------------------------------------------------

const GITHUB_URL_RE = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/
const HTTP_URL_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i
const DANGEROUS_SCHEME_RE = /^(javascript|data|vbscript|file):/i

const settingsSchema = z.object({
  name: z
    .string()
    .min(3, 'Project name must be at least 3 characters')
    .max(100, 'Project name must be at most 100 characters')
    .refine((v) => v.trim().length >= 3, 'Must be at least 3 characters after trimming'),
  description: z.string().max(2000, 'Description must be at most 2000 characters').optional(),
  app_url: z
    .string()
    .optional()
    .refine(
      (v) => !v || (!DANGEROUS_SCHEME_RE.test(v) && HTTP_URL_RE.test(v)),
      'Must be a valid HTTP or HTTPS URL',
    ),
  github_repo_url: z
    .string()
    .optional()
    .refine(
      (v) => !v || GITHUB_URL_RE.test(v),
      'Must be a valid GitHub URL: https://github.com/{owner}/{repo}',
    ),
  default_environment: z.enum(['development', 'staging', 'production', 'custom', '']).optional(),
  default_browser: z.enum(['chromium', 'firefox', 'webkit', '']).optional(),
})

type SettingsFormValues = z.infer<typeof settingsSchema>

// ---------------------------------------------------------------------------
// Tag input helper
// ---------------------------------------------------------------------------

interface TagInputProps {
  tags: string[]
  onChange: (tags: string[]) => void
}

function TagInput({ tags, onChange }: TagInputProps) {
  const [inputValue, setInputValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const addTag = useCallback(() => {
    const tag = inputValue.trim()
    if (!tag) return
    if (tags.length >= 10) {
      setError('Maximum 10 tags allowed')
      return
    }
    if (tag.length > 50) {
      setError('Tag must be at most 50 characters')
      return
    }
    if (tags.includes(tag)) {
      setError('Tag already added')
      return
    }
    setError(null)
    onChange([...tags, tag])
    setInputValue('')
  }, [inputValue, tags, onChange])

  const removeTag = useCallback(
    (index: number) => {
      onChange(tags.filter((_, i) => i !== index))
    },
    [tags, onChange],
  )

  return (
    <div>
      <div className="flex flex-wrap gap-1 mb-2" data-testid="tags-list">
        {tags.map((tag, i) => (
          <span
            key={i}
            className="inline-flex items-center gap-1 rounded-full bg-primary/10 text-primary text-xs px-2 py-0.5"
          >
            {tag}
            <button
              type="button"
              onClick={() => removeTag(i)}
              className="hover:text-destructive"
              aria-label={`Remove tag ${tag}`}
              data-testid={`remove-tag-${i}`}
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          type="text"
          placeholder="Add tag (max 50 chars)"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addTag()
            }
          }}
          disabled={tags.length >= 10}
          data-testid="tag-input"
          className="flex-1 text-sm"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addTag}
          disabled={!inputValue.trim() || tags.length >= 10}
          data-testid="add-tag-btn"
        >
          Add
        </Button>
      </div>
      {error && (
        <p role="alert" className="mt-1 text-xs text-destructive" data-testid="tag-error">
          {error}
        </p>
      )}
      <p className="mt-1 text-xs text-muted-foreground">{tags.length}/10 tags</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [tags, setTags] = useState<string[]>([])
  // AC3: name change confirmation state
  const [showNameConfirm, setShowNameConfirm] = useState(false)
  const [pendingSubmitValues, setPendingSubmitValues] = useState<SettingsFormValues | null>(null)
  const [originalName, setOriginalName] = useState('')
  // AC#1 (Story 1.10): tab navigation; Story 2.1 adds 'documents'; Story 2.6 adds 'agents'
  const [activeTab, setActiveTab] = useState<'general' | 'team' | 'documents' | 'agents'>('general')
  // Story 1.10: user's org role (owner/admin controls Team Members write actions)
  const [userOrgRole, setUserOrgRole] = useState<string>('viewer')

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    mode: 'onChange',
  })

  const watchedName = watch('name', '')

  // Load current settings
  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    projectApi
      .getSettings(projectId)
      .then((data: ProjectSettingsResponse) => {
        reset({
          name: data.name,
          description: data.description ?? '',
          app_url: data.app_url ?? '',
          github_repo_url: data.github_repo_url ?? '',
          default_environment: (data.default_environment as SettingsFormValues['default_environment']) ?? '',
          default_browser: (data.default_browser as SettingsFormValues['default_browser']) ?? '',
        })
        setTags(data.tags ?? [])
        setOriginalName(data.name)
        setLoading(false)
      })
      .catch(() => {
        setLoadError('Failed to load project settings.')
        setLoading(false)
      })
  }, [projectId, reset])

  const doSave = useCallback(
    async (values: SettingsFormValues) => {
      setSaveError(null)
      setSaveSuccess(false)

      const payload: Record<string, unknown> = {}
      if (values.name !== undefined) payload.name = values.name.trim()
      if (values.description !== undefined) payload.description = values.description || null
      if (values.app_url !== undefined) payload.app_url = values.app_url || null
      if (values.github_repo_url !== undefined) payload.github_repo_url = values.github_repo_url || null

      // AC4: build settings JSONB
      const settings: Record<string, unknown> = {}
      if (values.default_environment) settings.default_environment = values.default_environment
      if (values.default_browser) settings.default_browser = values.default_browser
      if (tags.length > 0) settings.tags = tags
      if (Object.keys(settings).length > 0) payload.settings = settings

      try {
        if (!projectId) return
        await projectApi.update(projectId, payload)
        setSaveSuccess(true)
        setOriginalName(typeof payload.name === 'string' ? payload.name : originalName)
        setTimeout(() => setSaveSuccess(false), 3000)
      } catch (err) {
        if (err instanceof ApiError) {
          setSaveError(err.message)
        } else {
          setSaveError('Failed to save settings. Please try again.')
        }
      }
    },
    [projectId, tags, originalName],
  )

  const onSubmit = useCallback(
    async (values: SettingsFormValues) => {
      // AC3: confirm if name changed (slug will update)
      if (values.name?.trim() !== originalName) {
        setPendingSubmitValues(values)
        setShowNameConfirm(true)
        return
      }
      await doSave(values)
    },
    [originalName, doSave],
  )

  const handleConfirmNameChange = useCallback(async () => {
    setShowNameConfirm(false)
    if (pendingSubmitValues) {
      await doSave(pendingSubmitValues)
      setPendingSubmitValues(null)
    }
  }, [pendingSubmitValues, doSave])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-64" data-testid="loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div
        role="alert"
        className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
        data-testid="load-error"
      >
        {loadError}
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-6">
        <Settings2 className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold text-foreground">Project Settings</h1>
      </div>

      {/* Tab navigation — AC#1 (Story 1.10) */}
      <div className="flex gap-1 mb-6 border-b" data-testid="settings-tabs">
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
            activeTab === 'general'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('general')}
          data-testid="tab-general"
        >
          General
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
            activeTab === 'team'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('team')}
          data-testid="tab-team-members"
        >
          Team Members
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
            activeTab === 'documents'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('documents')}
          data-testid="tab-documents"
        >
          Documents
        </button>
        <button
          type="button"
          className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
            activeTab === 'agents'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          onClick={() => setActiveTab('agents')}
          data-testid="tab-agents"
        >
          Agents
        </button>
      </div>

      {/* Team Members tab — AC#1 (Story 1.10) */}
      {activeTab === 'team' && projectId && (
        <TeamMembersTab projectId={projectId} userOrgRole={userOrgRole} />
      )}

      {/* Documents tab — Story 2.1 */}
      {activeTab === 'documents' && projectId && (
        <DocumentsTab projectId={projectId} projectRole={userOrgRole} />
      )}

      {/* Agents tab — Story 2.6 */}
      {activeTab === 'agents' && projectId && (
        <AgentsTab projectId={projectId} projectRole={userOrgRole} />
      )}

      {/* General / Advanced settings form */}
      {activeTab === 'general' && (
      <>

      {/* Name change confirmation dialog — AC3 */}
      {showNameConfirm && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
          data-testid="name-change-confirm"
        >
          <div className="bg-white rounded-lg shadow-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-lg font-semibold mb-2">Update project URL?</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Changing the project name will update the project URL (slug). Any existing
              links to this project may break.
            </p>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setShowNameConfirm(false)}
                data-testid="confirm-cancel"
              >
                Cancel
              </Button>
              <Button onClick={handleConfirmNameChange} data-testid="confirm-name-change">
                Update name and URL
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg shadow-sm border border-border p-6">
        {saveError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="save-error"
          >
            {saveError}
          </div>
        )}
        {saveSuccess && (
          <div
            role="status"
            className="mb-4 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800"
            data-testid="save-success"
          >
            Settings saved successfully.
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="settings-form">
          {/* General section — AC3 */}
          <section className="mb-6">
            <h2 className="text-sm font-semibold text-foreground mb-4 pb-1 border-b">
              General
            </h2>

            <div className="mb-4">
              <Label htmlFor="name">Project name</Label>
              <Input
                id="name"
                type="text"
                className="mt-1"
                aria-invalid={!!errors.name}
                data-testid="input-name"
                {...register('name')}
              />
              {watchedName && watchedName.trim() !== originalName && (
                <p className="mt-1 text-xs text-amber-600" data-testid="name-change-warning">
                  Saving will update the project URL.
                </p>
              )}
              {errors.name && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-name">
                  {errors.name.message}
                </p>
              )}
            </div>

            <div className="mb-4">
              <Label htmlFor="description">Description</Label>
              <textarea
                id="description"
                rows={3}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                data-testid="input-description"
                {...register('description')}
              />
              {errors.description && (
                <p role="alert" className="mt-1 text-xs text-destructive">
                  {errors.description.message}
                </p>
              )}
            </div>

            <div className="mb-4">
              <Label htmlFor="app_url">Application URL</Label>
              <Input
                id="app_url"
                type="url"
                placeholder="https://app.example.com"
                className="mt-1"
                aria-invalid={!!errors.app_url}
                data-testid="input-app-url"
                {...register('app_url')}
              />
              {errors.app_url && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-app-url">
                  {errors.app_url.message}
                </p>
              )}
            </div>

            <div className="mb-4">
              <Label htmlFor="github_repo_url">GitHub repository URL</Label>
              <Input
                id="github_repo_url"
                type="url"
                placeholder="https://github.com/owner/repo"
                className="mt-1"
                aria-invalid={!!errors.github_repo_url}
                data-testid="input-github-url"
                {...register('github_repo_url')}
              />
              {errors.github_repo_url && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-github-url">
                  {errors.github_repo_url.message}
                </p>
              )}
            </div>
          </section>

          {/* Advanced section (collapsible) — AC4 */}
          <section className="mb-6">
            <button
              type="button"
              className="flex items-center gap-2 text-sm font-semibold text-foreground mb-2 w-full text-left pb-1 border-b"
              onClick={() => setShowAdvanced((v) => !v)}
              data-testid="toggle-advanced"
              aria-expanded={showAdvanced}
            >
              Advanced
              {showAdvanced ? (
                <ChevronUp className="h-4 w-4 ml-auto" />
              ) : (
                <ChevronDown className="h-4 w-4 ml-auto" />
              )}
            </button>

            {showAdvanced && (
              <div className="space-y-4 pt-2" data-testid="advanced-section">
                {/* Default environment — AC4 */}
                <div>
                  <Label htmlFor="default_environment">Default test environment</Label>
                  <select
                    id="default_environment"
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    data-testid="select-environment"
                    {...register('default_environment')}
                  >
                    <option value="">— None —</option>
                    <option value="development">Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>

                {/* Default browser — AC4 */}
                <div>
                  <Label htmlFor="default_browser">Default browser</Label>
                  <select
                    id="default_browser"
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    data-testid="select-browser"
                    {...register('default_browser')}
                  >
                    <option value="">— None —</option>
                    <option value="chromium">Chromium</option>
                    <option value="firefox">Firefox</option>
                    <option value="webkit">WebKit (Safari)</option>
                  </select>
                </div>

                {/* Project tags — AC4 */}
                <div>
                  <Label>Project tags</Label>
                  <p className="text-xs text-muted-foreground mb-2">
                    Up to 10 tags for filtering and grouping projects.
                  </p>
                  <TagInput tags={tags} onChange={setTags} />
                </div>
              </div>
            )}
          </section>

          <Button
            type="submit"
            disabled={(!isDirty && tags.length === 0) || isSubmitting}
            data-testid="save-btn"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              'Save changes'
            )}
          </Button>
        </form>
      </div>

      </> /* end activeTab === 'general' */
      )}
    </div>
  )
}
