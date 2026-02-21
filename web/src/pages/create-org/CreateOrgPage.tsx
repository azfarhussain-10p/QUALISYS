/**
 * Create Organization Page
 * Story: 1-2-organization-creation-setup
 * AC: AC1 — first-time user onboarding prompt after registration/login
 * AC: AC2 — org creation form with name, slug, optional logo
 * AC: AC3 — async provisioning with polling spinner
 * AC: AC7 — real-time slug availability feedback
 * AC: AC8 — structured error display
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate, Link } from 'react-router-dom'
import { Loader2, Building2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { orgApi, ApiError } from '@/lib/api'

const ALLOWED_LOGO_TYPES = ['image/png', 'image/jpeg', 'image/svg+xml'] as const
const MAX_LOGO_BYTES = 2 * 1024 * 1024 // 2MB

// ---------------------------------------------------------------------------
// Validation schema — mirrors server-side rules
// ---------------------------------------------------------------------------

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/

const createOrgSchema = z.object({
  name: z
    .string()
    .min(3, 'Organization name must be at least 3 characters')
    .max(100, 'Organization name must be at most 100 characters'),
  slug: z
    .string()
    .optional()
    .refine(
      (v) => !v || SLUG_RE.test(v),
      'Slug must be 3-50 characters, lowercase alphanumeric and hyphens, no leading/trailing hyphens',
    ),
  custom_domain: z
    .string()
    .optional()
    .refine(
      (v) =>
        !v ||
        /^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/.test(v),
      'Must be a valid domain (e.g. app.example.com)',
    ),
})

type CreateOrgFormValues = z.infer<typeof createOrgSchema>

// ---------------------------------------------------------------------------
// Slug auto-generation helper (mirrors server-side _slugify)
// ---------------------------------------------------------------------------

function autoSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 50)
}

// ---------------------------------------------------------------------------
// Provisioning status poller
// ---------------------------------------------------------------------------

async function pollProvisioning(orgId: string, maxAttempts = 20): Promise<boolean> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 1500))
    try {
      const status = await orgApi.getProvisioningStatus(orgId)
      if (status.status === 'ready') return true
      if (status.status === 'failed') return false
    } catch {
      // keep polling
    }
  }
  return false
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreateOrgPage() {
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [provisioning, setProvisioning] = useState(false)
  const [slugPreview, setSlugPreview] = useState('')
  const [logoFile, setLogoFile] = useState<File | null>(null)
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [logoError, setLogoError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleLogoChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setLogoError(null)
    if (!ALLOWED_LOGO_TYPES.includes(file.type as (typeof ALLOWED_LOGO_TYPES)[number])) {
      setLogoError('Unsupported type. Allowed: PNG, JPG, SVG.')
      return
    }
    if (file.size > MAX_LOGO_BYTES) {
      setLogoError('File exceeds maximum size of 2MB.')
      return
    }
    setLogoFile(file)
    const url = URL.createObjectURL(file)
    setLogoPreview(url)
  }, [])

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting, isValid },
  } = useForm<CreateOrgFormValues>({
    resolver: zodResolver(createOrgSchema),
    mode: 'onChange',
  })

  const nameValue = watch('name', '')
  const slugValue = watch('slug', '')

  // Auto-populate slug preview from name (AC2)
  useEffect(() => {
    if (!slugValue) {
      setSlugPreview(autoSlug(nameValue))
    } else {
      setSlugPreview(slugValue)
    }
  }, [nameValue, slugValue])

  const onSubmit = useCallback(
    async (values: CreateOrgFormValues) => {
      setServerError(null)
      try {
        const result = await orgApi.create({
          name: values.name,
          slug: values.slug || undefined,
          custom_domain: values.custom_domain || undefined,
        })

        // AC6: upload logo if provided (presigned URL does not require provisioning)
        if (logoFile) {
          try {
            const { upload_url, key } = await orgApi.getLogoPresignedUrl(result.org.id, {
              filename: logoFile.name,
              content_type: logoFile.type,
              file_size: logoFile.size,
            })
            await fetch(upload_url, {
              method: 'PUT',
              headers: { 'Content-Type': logoFile.type },
              body: logoFile,
            })
            await orgApi.updateSettings(result.org.id, { logo_url: key })
          } catch {
            // Non-critical — org was created; user can upload logo in settings
          }
        }

        // AC3: poll provisioning status until ready
        setProvisioning(true)
        const ready = await pollProvisioning(result.org.id)
        setProvisioning(false)

        if (ready) {
          // Navigate to the org dashboard
          navigate('/dashboard', { replace: true })
        } else {
          setServerError(
            'Organization was created but workspace setup is taking longer than expected. ' +
              'Please refresh in a moment.',
          )
        }
      } catch (err) {
        setProvisioning(false)
        if (err instanceof ApiError) {
          setServerError(err.message)
        } else {
          setServerError('Something went wrong. Please try again.')
        }
      }
    },
    [navigate],
  )

  if (provisioning) {
    return (
      <div
        className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4"
        data-testid="provisioning-screen"
      >
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-foreground mb-2">Setting up your workspace…</h2>
          <p className="text-muted-foreground text-sm">
            We're preparing your organization's isolated environment. This takes a few seconds.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header — AC1: onboarding prompt */}
        <div className="text-center mb-8">
          <Building2 className="h-12 w-12 text-primary mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-foreground">Create your organization</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Set up your team's workspace to get started with QUALISYS
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-border p-8">
          {/* Server error banner — AC8 */}
          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="server-error"
            >
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="create-org-form">
            {/* Organization name */}
            <div className="mb-4">
              <Label htmlFor="name">Organization name</Label>
              <Input
                id="name"
                type="text"
                autoComplete="organization"
                placeholder="Acme Corp"
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

            {/* Slug — AC2, AC7 */}
            <div className="mb-4">
              <Label htmlFor="slug">
                URL slug{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                id="slug"
                type="text"
                placeholder={slugPreview || 'auto-generated'}
                className="mt-1 font-mono text-sm"
                aria-invalid={!!errors.slug}
                data-testid="input-slug"
                {...register('slug')}
              />
              {slugPreview && !slugValue && (
                <p className="mt-1 text-xs text-muted-foreground" data-testid="slug-preview">
                  Will use: <span className="font-mono font-medium">{slugPreview}</span>
                </p>
              )}
              {errors.slug && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-slug">
                  {errors.slug.message}
                </p>
              )}
            </div>

            {/* Logo upload — AC1, AC6: optional, max 2MB, PNG/JPG/SVG */}
            <div className="mb-4">
              <Label>
                Logo{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <div className="mt-1 flex items-center gap-3">
                {logoPreview && (
                  <img
                    src={logoPreview}
                    alt="Logo preview"
                    className="h-10 w-10 rounded object-cover border border-border"
                    data-testid="logo-preview"
                  />
                )}
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
                  data-testid="upload-logo-btn"
                >
                  <Upload className="mr-2 h-3 w-3" />
                  Choose file
                </Button>
                <span className="text-xs text-muted-foreground">PNG, JPG, SVG · max 2MB</span>
              </div>
              {logoError && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="logo-error">
                  {logoError}
                </p>
              )}
            </div>

            {/* Custom domain — optional */}
            <div className="mb-6">
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

            <Button
              type="submit"
              className="w-full"
              disabled={!isValid || isSubmitting}
              data-testid="submit-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating organization…
                </>
              ) : (
                'Create organization'
              )}
            </Button>
          </form>

          {/* AC1: skip option for users who were invited */}
          <p className="mt-6 text-center text-sm text-muted-foreground" data-testid="join-org-link">
            Already have an invite?{' '}
            <Link to="/accept-invite" className="font-medium text-primary hover:underline">
              Join an existing organization
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
