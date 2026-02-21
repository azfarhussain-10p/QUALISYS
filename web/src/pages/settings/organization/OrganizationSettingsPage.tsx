/**
 * Organization Settings Page
 * Story: 1-2-organization-creation-setup
 * AC: AC5 — PATCH /orgs/{id}/settings for owner/admin (RBAC enforced server-side)
 * AC: AC6 — logo upload via pre-signed S3 URL
 * AC: AC8 — structured error display
 * Story: 1-3-team-member-invitation
 * AC: AC1, AC6 — Team Members tab with invite dialog + pending invitations list
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Loader2, Upload, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { orgApi, OrgResponse, ApiError } from '@/lib/api'
import TeamMembersTab from '@/pages/settings/team/TeamMembersTab'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OrganizationSettingsPageProps {
  orgId: string
  /** Current user's role — used for RBAC gating in Team Members tab (Story 1.3 AC1). */
  userRole: string
}

type SettingsTab = 'general' | 'team'

// ---------------------------------------------------------------------------
// Validation schema
// ---------------------------------------------------------------------------

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/
const RETENTION_OPTIONS = [30, 90, 180, 365] as const

const settingsSchema = z.object({
  name: z
    .string()
    .min(3, 'Name must be at least 3 characters')
    .max(100, 'Name must be at most 100 characters'),
  slug: z
    .string()
    .refine((v) => SLUG_RE.test(v), 'Slug must be 3-50 chars, lowercase alphanumeric + hyphens'),
  custom_domain: z
    .string()
    .optional()
    .refine(
      (v) =>
        !v ||
        /^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/.test(v),
      'Must be a valid domain (e.g. app.example.com)',
    ),
  data_retention_days: z.coerce
    .number()
    .refine((v) => (RETENTION_OPTIONS as readonly number[]).includes(v), {
      message: 'Must be one of: 30, 90, 180, 365',
    }),
})

type SettingsFormValues = z.infer<typeof settingsSchema>

// ---------------------------------------------------------------------------
// Logo upload helper — AC6
// ---------------------------------------------------------------------------

const ALLOWED_LOGO_TYPES = ['image/png', 'image/jpeg', 'image/svg+xml'] as const
const MAX_LOGO_BYTES = 2 * 1024 * 1024 // 2MB

async function uploadLogo(orgId: string, file: File): Promise<string> {
  if (!ALLOWED_LOGO_TYPES.includes(file.type as (typeof ALLOWED_LOGO_TYPES)[number])) {
    throw new Error('Unsupported file type. Allowed: PNG, JPG, SVG.')
  }
  if (file.size > MAX_LOGO_BYTES) {
    throw new Error('File exceeds maximum size of 2MB.')
  }

  // Get pre-signed URL from API
  const { upload_url, key, fields } = await orgApi.getLogoPresignedUrl(orgId, {
    filename: file.name,
    content_type: file.type,
    file_size: file.size,
  })

  // Build FormData if server returned fields (POST presign), else use PUT
  if (Object.keys(fields).length > 0) {
    const form = new FormData()
    for (const [k, v] of Object.entries(fields)) form.append(k, v)
    form.append('file', file)
    await fetch(upload_url, { method: 'POST', body: form })
  } else {
    await fetch(upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': file.type },
      body: file,
    })
  }

  // Return the public S3 key/URL to store on the org record
  return key
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrganizationSettingsPage({ orgId, userRole }: OrganizationSettingsPageProps) {
  const [org, setOrg] = useState<OrgResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const [logoUploading, setLogoUploading] = useState(false)
  const [logoError, setLogoError] = useState<string | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting, isDirty },
  } = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    mode: 'onChange',
  })

  // Load org settings on mount
  useEffect(() => {
    orgApi
      .getSettings(orgId)
      .then((data) => {
        setOrg(data)
        setLogoPreview(data.logo_url)
        reset({
          name: data.name,
          slug: data.slug,
          custom_domain: data.custom_domain ?? '',
          data_retention_days: data.data_retention_days,
        })
      })
      .catch((err) => {
        setServerError(err instanceof ApiError ? err.message : 'Failed to load settings.')
      })
      .finally(() => setLoading(false))
  }, [orgId, reset])

  const onSubmit = useCallback(
    async (values: SettingsFormValues) => {
      setServerError(null)
      setSaveSuccess(false)

      // AC5: confirm slug change before submitting
      if (org && values.slug !== org.slug) {
        const confirmed = window.confirm(
          'Changing the slug will update your organization\u2019s URL and may break existing bookmarks or integrations.\n\nAre you sure you want to continue?',
        )
        if (!confirmed) return
      }

      try {
        const updated = await orgApi.updateSettings(orgId, {
          name: values.name,
          slug: values.slug,
          custom_domain: values.custom_domain || undefined,
          data_retention_days: values.data_retention_days,
        })
        setOrg(updated)
        reset({
          name: updated.name,
          slug: updated.slug,
          custom_domain: updated.custom_domain ?? '',
          data_retention_days: updated.data_retention_days,
        })
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      } catch (err) {
        setServerError(err instanceof ApiError ? err.message : 'Failed to save settings.')
      }
    },
    [orgId, reset],
  )

  // Logo file picker handler — AC6
  const handleLogoChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return

      setLogoError(null)
      setLogoUploading(true)

      // Preview
      const objectUrl = URL.createObjectURL(file)
      setLogoPreview(objectUrl)

      try {
        const key = await uploadLogo(orgId, file)
        // Save logo_url to org settings
        const updated = await orgApi.updateSettings(orgId, { logo_url: key })
        setOrg(updated)
      } catch (err) {
        setLogoPreview(org?.logo_url ?? null)
        setLogoError(err instanceof Error ? err.message : 'Logo upload failed.')
      } finally {
        setLogoUploading(false)
        URL.revokeObjectURL(objectUrl)
        if (fileInputRef.current) fileInputRef.current.value = ''
      }
    },
    [orgId, org?.logo_url],
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]" data-testid="settings-loading">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6" data-testid="org-settings-page">
      {/* Page header */}
      <div className="flex items-center gap-3 mb-6">
        <Building2 className="h-7 w-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold text-foreground">Organization Settings</h1>
          <p className="text-muted-foreground text-sm">Manage your organization's configuration</p>
        </div>
      </div>

      {/* Tab navigation — Story 1.3 AC1 */}
      <div className="border-b border-border mb-6" data-testid="settings-tabs">
        <nav className="-mb-px flex gap-6" aria-label="Settings tabs">
          <button
            type="button"
            onClick={() => setActiveTab('general')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'general'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            }`}
            data-testid="tab-general"
            aria-selected={activeTab === 'general'}
          >
            General
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('team')}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'team'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
            }`}
            data-testid="tab-team"
            aria-selected={activeTab === 'team'}
          >
            Team Members
          </button>
        </nav>
      </div>

      {/* Team Members tab — Story 1.3 */}
      {activeTab === 'team' && (
        <TeamMembersTab orgId={orgId} userRole={userRole} />
      )}

      {/* General tab content */}
      {activeTab === 'general' && (
      <div data-testid="general-tab-content">

      {/* Logo section — AC6 */}
      <div className="bg-white rounded-lg shadow-sm border border-border p-6 mb-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Organization Logo</h2>
        <div className="flex items-center gap-6">
          {/* Logo preview */}
          <div
            className="h-20 w-20 rounded-lg border border-border bg-muted flex items-center justify-center overflow-hidden flex-shrink-0"
            data-testid="logo-preview"
          >
            {logoPreview ? (
              <img
                src={logoPreview}
                alt="Organization logo"
                className="h-full w-full object-cover"
              />
            ) : (
              <Building2 className="h-8 w-8 text-muted-foreground" />
            )}
          </div>

          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/svg+xml"
              className="hidden"
              onChange={handleLogoChange}
              data-testid="logo-file-input"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={logoUploading}
              data-testid="upload-logo-btn"
            >
              {logoUploading ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  Uploading…
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-3 w-3" />
                  Upload logo
                </>
              )}
            </Button>
            <p className="mt-2 text-xs text-muted-foreground">PNG, JPG, or SVG · Max 2MB</p>
            {logoError && (
              <p role="alert" className="mt-1 text-xs text-destructive" data-testid="logo-error">
                {logoError}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Settings form — AC5 */}
      <div className="bg-white rounded-lg shadow-sm border border-border p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">General Settings</h2>

        {serverError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="server-error"
          >
            {serverError}
          </div>
        )}

        {saveSuccess && (
          <div
            role="status"
            className="mb-4 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700"
            data-testid="save-success"
          >
            Settings saved successfully.
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="settings-form">
          {/* Organization name */}
          <div className="mb-4">
            <Label htmlFor="name">Organization name</Label>
            <Input
              id="name"
              type="text"
              className="mt-1"
              aria-invalid={!!errors.name}
              data-testid="input-org-name"
              {...register('name')}
            />
            {errors.name && (
              <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-name">
                {errors.name.message}
              </p>
            )}
          </div>

          {/* Slug */}
          <div className="mb-4">
            <Label htmlFor="slug">URL slug</Label>
            <Input
              id="slug"
              type="text"
              className="mt-1 font-mono text-sm"
              aria-invalid={!!errors.slug}
              data-testid="input-slug"
              {...register('slug')}
            />
            {errors.slug && (
              <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-slug">
                {errors.slug.message}
              </p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              Changing the slug will update your organization's URL.
            </p>
          </div>

          {/* Custom domain */}
          <div className="mb-4">
            <Label htmlFor="custom_domain">
              Custom domain{' '}
              <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="custom_domain"
              type="text"
              placeholder="app.yourcompany.com"
              className="mt-1"
              aria-invalid={!!errors.custom_domain}
              data-testid="input-custom-domain"
              {...register('custom_domain')}
            />
            {errors.custom_domain && (
              <p
                role="alert"
                className="mt-1 text-xs text-destructive"
                data-testid="error-custom-domain"
              >
                {errors.custom_domain.message}
              </p>
            )}
          </div>

          {/* Data retention */}
          <div className="mb-6">
            <Label htmlFor="data_retention_days">Data retention period</Label>
            <select
              id="data_retention_days"
              className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              data-testid="select-retention"
              {...register('data_retention_days')}
            >
              <option value={30}>30 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
              <option value={365}>365 days (1 year)</option>
            </select>
            {errors.data_retention_days && (
              <p
                role="alert"
                className="mt-1 text-xs text-destructive"
                data-testid="error-retention"
              >
                {errors.data_retention_days.message}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between">
            {org && (
              <p className="text-xs text-muted-foreground">
                Plan: <span className="font-medium capitalize">{org.plan}</span>
                {org.provisioning_status && org.provisioning_status !== 'ready' && (
                  <span className="ml-2 text-yellow-600">
                    · Workspace: {org.provisioning_status}
                  </span>
                )}
              </p>
            )}
            <Button
              type="submit"
              disabled={!isDirty || isSubmitting}
              data-testid="save-settings-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving…
                </>
              ) : (
                'Save settings'
              )}
            </Button>
          </div>
        </form>
      </div>
      </div> {/* end general-tab-content */}
      )} {/* end activeTab === 'general' */}
    </div>
  )
}
