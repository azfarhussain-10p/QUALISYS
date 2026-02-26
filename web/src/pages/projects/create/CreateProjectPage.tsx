/**
 * Create Project Page
 * Story: 1-9-project-creation-configuration
 * AC: AC1 — Create Project form accessible from projects list/dashboard (Owner/Admin only)
 * AC: AC6 — Duplicate project name error displayed
 * AC: AC7 — Client-side validation: name (required, 3-100), URL formats, GitHub URL pattern
 */

import { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useNavigate } from 'react-router-dom'
import { Loader2, FolderPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ApiError, projectApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Validation schema — mirrors server-side rules (AC7)
// ---------------------------------------------------------------------------

const GITHUB_URL_RE = /^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/
const HTTP_URL_RE = /^https?:\/\/[^\s/$.?#].[^\s]*$/i
const DANGEROUS_SCHEME_RE = /^(javascript|data|vbscript|file):/i

const createProjectSchema = z.object({
  name: z
    .string()
    .min(3, 'Project name must be at least 3 characters')
    .max(100, 'Project name must be at most 100 characters')
    .refine((v) => v.trim().length >= 3, 'Project name must be at least 3 characters after trimming'),
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
})

type CreateProjectFormValues = z.infer<typeof createProjectSchema>

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreateProjectPage() {
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isValid },
  } = useForm<CreateProjectFormValues>({
    resolver: zodResolver(createProjectSchema),
    mode: 'onChange',
  })

  const onSubmit = useCallback(
    async (values: CreateProjectFormValues) => {
      setServerError(null)
      try {
        const project = await projectApi.create({
          name: values.name.trim(),
          description: values.description || undefined,
          app_url: values.app_url || undefined,
          github_repo_url: values.github_repo_url || undefined,
        })
        // AC1: redirect to new project on success
        navigate(`/projects/${project.slug}`, { replace: true })
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.code === 'DUPLICATE_SLUG' || err.message.includes('already exists')) {
            setServerError('A project with this name already exists. Please choose a different name.')
          } else {
            setServerError(err.message)
          }
        } else {
          setServerError('Something went wrong. Please try again.')
        }
      }
    },
    [navigate],
  )

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <FolderPlus className="h-12 w-12 text-primary mx-auto mb-3" />
          <h1 className="text-2xl font-bold text-foreground">Create a project</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Organize your testing efforts with a dedicated project
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-border p-8">
          {/* Server error banner */}
          {serverError && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="server-error"
            >
              {serverError}
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} noValidate data-testid="create-project-form">
            {/* Project name — AC1, AC7 */}
            <div className="mb-4">
              <Label htmlFor="name">
                Project name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                type="text"
                placeholder="My Test Project"
                className="mt-1"
                aria-invalid={!!errors.name}
                data-testid="input-project-name"
                {...register('name')}
              />
              {errors.name && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-name">
                  {errors.name.message}
                </p>
              )}
            </div>

            {/* Description — optional */}
            <div className="mb-4">
              <Label htmlFor="description">
                Description{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <textarea
                id="description"
                rows={3}
                placeholder="Briefly describe what this project tests"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="input-description"
                {...register('description')}
              />
              {errors.description && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-description">
                  {errors.description.message}
                </p>
              )}
            </div>

            {/* Application URL — optional, validated */}
            <div className="mb-4">
              <Label htmlFor="app_url">
                Application URL{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Input
                id="app_url"
                type="url"
                placeholder="https://app.example.com"
                className="mt-1"
                aria-invalid={!!errors.app_url}
                data-testid="input-app-url"
                {...register('app_url')}
              />
              <p className="mt-0.5 text-xs text-muted-foreground">
                The application under test
              </p>
              {errors.app_url && (
                <p role="alert" className="mt-1 text-xs text-destructive" data-testid="error-app-url">
                  {errors.app_url.message}
                </p>
              )}
            </div>

            {/* GitHub Repo URL — optional, validated */}
            <div className="mb-6">
              <Label htmlFor="github_repo_url">
                GitHub repository URL{' '}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
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

            <Button
              type="submit"
              className="w-full"
              disabled={!isValid || isSubmitting}
              data-testid="submit-btn"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating project…
                </>
              ) : (
                'Create project'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
