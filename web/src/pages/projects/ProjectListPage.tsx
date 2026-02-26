/**
 * Project List Page
 * Story: 1-11-project-management-archive-delete-list
 * AC: AC1 — Projects list (/projects) with table, search, sort, pagination
 * AC: AC2 — Show Archived toggle / status filter persisted in URL params
 * AC: AC3 — Archive confirmation dialog with data retention reassurance
 * AC: AC4 — Restore action (archived projects only)
 * AC: AC5 — High-friction delete confirmation (type project name to confirm)
 * AC: AC6 — Health indicator placeholder column ('—')
 * AC: AC7 — Client-side validation, error handling
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { Loader2, FolderPlus, Search, ChevronUp, ChevronDown, MoreHorizontal, Archive, RotateCcw, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, projectApi, userApi, ProjectListItem, PaginationMeta } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StatusFilter = 'active' | 'archived' | 'all'
type SortField = 'name' | 'created_at' | 'status'

// ---------------------------------------------------------------------------
// HealthIndicator — AC6: placeholder '—' for Epic 1
// ---------------------------------------------------------------------------

function HealthIndicator({ health }: { health: string }) {
  return (
    <span
      className="inline-flex items-center justify-center text-muted-foreground text-sm"
      aria-label="Health indicator (not yet available)"
      data-testid="health-indicator"
    >
      {health}
    </span>
  )
}

// ---------------------------------------------------------------------------
// StatusBadge — AC1, AC2: Active (green) / Archived (gray)
// ---------------------------------------------------------------------------

function StatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800"
      data-testid="badge-active"
    >
      Active
    </span>
  ) : (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600"
      data-testid="badge-archived"
    >
      Archived
    </span>
  )
}

// ---------------------------------------------------------------------------
// ArchiveDialog — AC3: confirmation with data retention reassurance
// ---------------------------------------------------------------------------

interface ArchiveDialogProps {
  project: ProjectListItem
  onConfirm: () => void
  onCancel: () => void
  loading: boolean
}

function ArchiveDialog({ project, onConfirm, onCancel, loading }: ArchiveDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="archive-dialog-title"
      data-testid="archive-dialog"
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
        <h2 id="archive-dialog-title" className="text-lg font-semibold text-foreground mb-2">
          Archive &ldquo;{project.name}&rdquo;?
        </h2>
        <p className="text-sm text-muted-foreground mb-6">
          The project will be hidden from the active list but <strong>all data will be retained</strong>.
          You can restore it later at any time.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={loading} data-testid="archive-cancel-btn">
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading}
            className="bg-yellow-600 hover:bg-yellow-700 text-white"
            data-testid="archive-confirm-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Archive project'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DeleteDialog — AC5: high-friction, type project name to confirm
// ---------------------------------------------------------------------------

interface DeleteDialogProps {
  project: ProjectListItem
  onConfirm: () => void
  onCancel: () => void
  loading: boolean
}

function DeleteDialog({ project, onConfirm, onCancel, loading }: DeleteDialogProps) {
  const [typedName, setTypedName] = useState('')
  const nameMatches = typedName === project.name

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      data-testid="delete-dialog"
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6 border-l-4 border-destructive">
        <h2 id="delete-dialog-title" className="text-lg font-semibold text-destructive mb-2">
          Permanently delete &ldquo;{project.name}&rdquo;?
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          <strong>This action cannot be undone.</strong> All project data including test cases,
          test executions, and team assignments will be permanently removed.
        </p>
        <div className="mb-4">
          <label htmlFor="confirm-name" className="block text-sm font-medium text-foreground mb-1">
            Type <strong>{project.name}</strong> to confirm:
          </label>
          <Input
            id="confirm-name"
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            placeholder={project.name}
            className="border-destructive/30 focus-visible:ring-destructive"
            data-testid="delete-confirm-input"
            autoComplete="off"
          />
        </div>
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={loading} data-testid="delete-cancel-btn">
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!nameMatches || loading}
            variant="destructive"
            data-testid="delete-confirm-btn"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Delete permanently'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ActionsDropdown — AC3, AC4, AC5: Archive/Restore/Delete per row
// ---------------------------------------------------------------------------

interface ActionsDropdownProps {
  project: ProjectListItem
  isAdminOrOwner: boolean
  onArchive: (project: ProjectListItem) => void
  onRestore: (project: ProjectListItem) => void
  onDelete: (project: ProjectListItem) => void
}

function ActionsDropdown({ project, isAdminOrOwner, onArchive, onRestore, onDelete }: ActionsDropdownProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div className="relative" ref={ref}>
      <button
        className="p-1 rounded hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
        onClick={() => setOpen(!open)}
        aria-label="Project actions"
        data-testid={`actions-btn-${project.id}`}
      >
        <MoreHorizontal className="h-4 w-4 text-muted-foreground" />
      </button>
      {open && (
        <div
          className="absolute right-0 top-7 z-20 bg-white border border-border rounded-md shadow-md min-w-36 py-1"
          data-testid={`actions-menu-${project.id}`}
        >
          <Link
            to={`/projects/${project.id}/settings`}
            className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted w-full text-left"
            onClick={() => setOpen(false)}
          >
            Settings
          </Link>
          {isAdminOrOwner && (
            <>
              {project.is_active ? (
                /* AC3: Archive — only on active projects */
                <button
                  className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted w-full text-left text-yellow-700"
                  onClick={() => { setOpen(false); onArchive(project) }}
                  data-testid={`archive-btn-${project.id}`}
                >
                  <Archive className="h-3.5 w-3.5" />
                  Archive project
                </button>
              ) : (
                /* AC4: Restore — only on archived projects */
                <button
                  className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted w-full text-left text-green-700"
                  onClick={() => { setOpen(false); onRestore(project) }}
                  data-testid={`restore-btn-${project.id}`}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Restore project
                </button>
              )}
              {/* AC5: Delete — always visible to Owner/Admin */}
              <button
                className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted w-full text-left text-destructive"
                onClick={() => { setOpen(false); onDelete(project) }}
                data-testid={`delete-btn-${project.id}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Delete project
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Toast — success/error notifications (AC5, AC3, AC4)
// ---------------------------------------------------------------------------

interface ToastMessage {
  id: number
  type: 'success' | 'error'
  text: string
}

function Toast({ messages, onDismiss }: { messages: ToastMessage[], onDismiss: (id: number) => void }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2" data-testid="toast-container">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`flex items-center gap-3 px-4 py-3 rounded-md shadow-md text-sm text-white max-w-sm
            ${m.type === 'success' ? 'bg-green-600' : 'bg-destructive'}`}
          data-testid={`toast-${m.type}`}
        >
          <span className="flex-1">{m.text}</span>
          <button
            className="text-white/70 hover:text-white"
            onClick={() => onDismiss(m.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// SortHeader — AC1: sortable table column headers
// ---------------------------------------------------------------------------

function SortHeader({
  label,
  field,
  currentSort,
  onClick,
}: {
  label: string
  field: SortField
  currentSort: SortField
  onClick: (field: SortField) => void
}) {
  const isActive = currentSort === field
  return (
    <button
      className="flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground"
      onClick={() => onClick(field)}
      aria-sort={isActive ? 'descending' : undefined}
      data-testid={`sort-${field}`}
    >
      {label}
      {isActive ? (
        <ChevronDown className="h-3 w-3" />
      ) : (
        <ChevronUp className="h-3 w-3 opacity-30" />
      )}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Pagination — AC1
// ---------------------------------------------------------------------------

function Pagination({
  meta,
  onPageChange,
}: {
  meta: PaginationMeta
  onPageChange: (page: number) => void
}) {
  if (meta.total_pages <= 1) return null

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-border" data-testid="pagination">
      <p className="text-sm text-muted-foreground">
        Showing {(meta.page - 1) * meta.per_page + 1}–{Math.min(meta.page * meta.per_page, meta.total)} of{' '}
        {meta.total} projects
      </p>
      <div className="flex items-center gap-1">
        <button
          className="p-1.5 rounded hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={() => onPageChange(meta.page - 1)}
          disabled={meta.page === 1}
          aria-label="Previous page"
          data-testid="page-prev"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-sm px-2" data-testid="page-indicator">
          {meta.page} / {meta.total_pages}
        </span>
        <button
          className="p-1.5 rounded hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={() => onPageChange(meta.page + 1)}
          disabled={meta.page === meta.total_pages}
          aria-label="Next page"
          data-testid="page-next"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main — ProjectListPage
// ---------------------------------------------------------------------------

export default function ProjectListPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // URL-persisted state (AC2, C12)
  const statusFilter = (searchParams.get('status') as StatusFilter) || 'active'
  const sortField = (searchParams.get('sort') as SortField) || 'created_at'
  const currentPage = parseInt(searchParams.get('page') || '1', 10)
  const searchValue = searchParams.get('search') || ''

  const [searchInput, setSearchInput] = useState(searchValue)
  const [currentUserRole, setCurrentUserRole] = useState<string | null>(null)
  const [projects, setProjects] = useState<ProjectListItem[]>([])
  const [pagination, setPagination] = useState<PaginationMeta | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Dialog state
  const [archiveTarget, setArchiveTarget] = useState<ProjectListItem | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ProjectListItem | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  // Toast state
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const toastCounter = useRef(0)

  // Fetch current user's org role from /api/v1/users/me (includes org_role from JWT)
  useEffect(() => {
    userApi.getMe().then((data) => setCurrentUserRole(data.org_role)).catch(() => {})
  }, [])

  const isAdminOrOwner = currentUserRole === 'owner' || currentUserRole === 'admin'

  const addToast = useCallback((type: 'success' | 'error', text: string) => {
    const id = ++toastCounter.current
    setToasts((prev) => [...prev, { id, type, text }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  // Fetch projects whenever URL params change
  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await projectApi.list({
        status: statusFilter,
        search: searchValue || undefined,
        sort: sortField,
        page: currentPage,
        per_page: 20,
      })
      setProjects(result.data)
      setPagination(result.pagination)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to load projects.')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, searchValue, sortField, currentPage])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  // URL helpers
  const updateParams = useCallback((updates: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    for (const [k, v] of Object.entries(updates)) {
      if (v === undefined || v === '') {
        next.delete(k)
      } else {
        next.set(k, v)
      }
    }
    // Reset to page 1 when filters change
    if (!('page' in updates)) next.set('page', '1')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const handleStatusChange = (s: StatusFilter) => updateParams({ status: s })
  const handleSortChange = (field: SortField) => updateParams({ sort: field })
  const handlePageChange = (page: number) => updateParams({ page: String(page) })

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateParams({ search: searchInput || undefined })
  }

  // Archive
  const handleArchiveConfirm = async () => {
    if (!archiveTarget) return
    setActionLoading(true)
    try {
      await projectApi.archive(archiveTarget.id)
      addToast('success', `"${archiveTarget.name}" has been archived.`)
      setArchiveTarget(null)
      fetchProjects()
    } catch (err) {
      addToast('error', err instanceof ApiError ? err.message : 'Archive failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  // Restore
  const handleRestore = async (project: ProjectListItem) => {
    try {
      await projectApi.restore(project.id)
      addToast('success', `"${project.name}" has been restored.`)
      fetchProjects()
    } catch (err) {
      addToast('error', err instanceof ApiError ? err.message : 'Restore failed. Please try again.')
    }
  }

  // Delete
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setActionLoading(true)
    try {
      await projectApi.delete(deleteTarget.id)
      addToast('success', `"${deleteTarget.name}" has been permanently deleted.`)
      setDeleteTarget(null)
      fetchProjects()
    } catch (err) {
      addToast('error', err instanceof ApiError ? err.message : 'Delete failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const isEmpty = !loading && projects.length === 0

  return (
    <div className="min-h-screen bg-slate-50" data-testid="project-list-page">
      {/* Header */}
      <div className="bg-white border-b border-border px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Projects</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your testing projects
          </p>
        </div>
        {isAdminOrOwner && (
          <Button onClick={() => navigate('/projects/new')} data-testid="new-project-btn">
            <FolderPlus className="h-4 w-4 mr-2" />
            New project
          </Button>
        )}
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Toolbar: search + status filter + sort */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          {/* Search — AC1 */}
          <form onSubmit={handleSearchSubmit} className="flex gap-2 flex-1">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search projects…"
                className="pl-8"
                data-testid="search-input"
              />
            </div>
            <Button type="submit" variant="outline" size="sm" data-testid="search-btn">
              Search
            </Button>
          </form>

          {/* Status filter — AC2: persisted in URL */}
          <div className="flex items-center gap-1" role="group" aria-label="Status filter">
            {(['active', 'archived', 'all'] as StatusFilter[]).map((s) => (
              <button
                key={s}
                onClick={() => handleStatusChange(s)}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors
                  ${statusFilter === s
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-white text-foreground border-border hover:bg-muted'
                  }`}
                aria-pressed={statusFilter === s}
                data-testid={`filter-${s}`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg border border-border overflow-hidden shadow-sm">
          {loading ? (
            <div className="flex items-center justify-center py-16" data-testid="loading-state">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-16" data-testid="error-state">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          ) : isEmpty ? (
            /* AC1: Empty state */
            <div className="flex flex-col items-center justify-center py-16 text-center px-4" data-testid="empty-state">
              <FolderPlus className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h3 className="text-base font-medium text-foreground mb-1">No projects yet</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {statusFilter === 'archived'
                  ? 'No archived projects found.'
                  : 'Create your first project to get started.'}
              </p>
              {isAdminOrOwner && statusFilter !== 'archived' && (
                <Button onClick={() => navigate('/projects/new')} data-testid="empty-new-project-btn">
                  <FolderPlus className="h-4 w-4 mr-2" />
                  New project
                </Button>
              )}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm" data-testid="projects-table">
                  <thead>
                    <tr className="border-b border-border bg-slate-50/60">
                      <th className="text-left px-4 py-3">
                        <SortHeader label="Name" field="name" currentSort={sortField} onClick={handleSortChange} />
                      </th>
                      <th className="text-left px-4 py-3">
                        <SortHeader label="Status" field="status" currentSort={sortField} onClick={handleSortChange} />
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Health
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wide hidden md:table-cell">
                        Description
                      </th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Team
                      </th>
                      <th className="text-left px-4 py-3">
                        <SortHeader label="Created" field="created_at" currentSort={sortField} onClick={handleSortChange} />
                      </th>
                      <th className="px-4 py-3" aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {projects.map((project) => (
                      <tr
                        key={project.id}
                        className={`hover:bg-slate-50/60 ${!project.is_active ? 'opacity-70' : ''}`}
                        data-testid={`project-row-${project.id}`}
                      >
                        {/* Name — link to project (placeholder until project dashboard exists) */}
                        <td className="px-4 py-3 font-medium">
                          <Link
                            to={`/projects/${project.id}/settings`}
                            className="text-primary hover:underline"
                            data-testid={`project-link-${project.id}`}
                          >
                            {project.name}
                          </Link>
                        </td>

                        {/* Status badge — AC2 */}
                        <td className="px-4 py-3">
                          <StatusBadge isActive={project.is_active} />
                        </td>

                        {/* Health — AC6: placeholder */}
                        <td className="px-4 py-3">
                          <HealthIndicator health={project.health} />
                        </td>

                        {/* Description — truncated */}
                        <td className="px-4 py-3 text-muted-foreground hidden md:table-cell max-w-48">
                          {project.description ? (
                            <span className="line-clamp-1 text-xs" title={project.description}>
                              {project.description}
                            </span>
                          ) : (
                            <span className="text-muted-foreground/40 text-xs">—</span>
                          )}
                        </td>

                        {/* Team size — AC1: member_count */}
                        <td className="px-4 py-3 text-muted-foreground" data-testid={`member-count-${project.id}`}>
                          {project.member_count}
                        </td>

                        {/* Created date */}
                        <td className="px-4 py-3 text-muted-foreground text-xs whitespace-nowrap">
                          {new Date(project.created_at).toLocaleDateString()}
                        </td>

                        {/* Actions dropdown */}
                        <td className="px-4 py-3">
                          <ActionsDropdown
                            project={project}
                            isAdminOrOwner={isAdminOrOwner}
                            onArchive={setArchiveTarget}
                            onRestore={handleRestore}
                            onDelete={setDeleteTarget}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination — AC1 */}
              {pagination && (
                <Pagination meta={pagination} onPageChange={handlePageChange} />
              )}
            </>
          )}
        </div>
      </div>

      {/* Archive dialog — AC3 */}
      {archiveTarget && (
        <ArchiveDialog
          project={archiveTarget}
          onConfirm={handleArchiveConfirm}
          onCancel={() => setArchiveTarget(null)}
          loading={actionLoading}
        />
      )}

      {/* Delete dialog — AC5 */}
      {deleteTarget && (
        <DeleteDialog
          project={deleteTarget}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          loading={actionLoading}
        />
      )}

      {/* Toast notifications — AC3, AC4, AC5 */}
      <Toast messages={toasts} onDismiss={dismissToast} />
    </div>
  )
}
