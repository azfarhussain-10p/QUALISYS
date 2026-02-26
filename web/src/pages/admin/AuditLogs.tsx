/**
 * Audit Log Viewer — /admin/audit-logs
 * Story: 1-12-usage-analytics-audit-logs-basic
 * AC: #4 — Table with columns: timestamp, actor, action, resource, details, IP
 * AC: #5 — Filter bar: date range (presets), action type, actor UUID; active chips; URL persistence
 * AC: #6 — "Export CSV" button (streaming download, rate-limited)
 * AC: #8 — Empty state, error handling, 400/403 handling
 */

import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Loader2, Download, X, FileText, Filter } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { adminApi, ApiError, AuditLogEntry, AuditLogFilters } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DatePreset = '7d' | '30d' | '90d' | 'custom'

const DATE_PRESETS: { label: string; value: DatePreset; days: number }[] = [
  { label: 'Last 7 days', value: '7d', days: 7 },
  { label: 'Last 30 days', value: '30d', days: 30 },
  { label: 'Last 90 days', value: '90d', days: 90 },
]

const ACTION_OPTIONS = [
  { label: 'All Actions', value: '' },
  { label: 'User Actions', value: 'user_actions' },
  { label: 'Project Actions', value: 'project_actions' },
  { label: 'Organization Actions', value: 'org_actions' },
  // Granular
  { label: 'project.created', value: 'project.created' },
  { label: 'project.archived', value: 'project.archived' },
  { label: 'project.deleted', value: 'project.deleted' },
  { label: 'user.invited', value: 'user.invited' },
  { label: 'user.role_changed', value: 'user.role_changed' },
  { label: 'user.login', value: 'user.login' },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function _isoFromNow(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString()
}

function _formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function _humanizeAction(action: string): string {
  return action.replace('.', ': ').replace(/_/g, ' ')
}

// ---------------------------------------------------------------------------
// Expandable details cell
// ---------------------------------------------------------------------------

function DetailsCell({ details }: { details: Record<string, unknown> | null }) {
  const [expanded, setExpanded] = useState(false)
  if (!details) return <span className="text-muted-foreground text-xs">—</span>
  const summary = Object.keys(details).slice(0, 2).join(', ')
  return (
    <div className="max-w-xs">
      {expanded ? (
        <div>
          <pre
            className="text-xs bg-muted rounded p-2 overflow-auto max-h-32"
            data-testid="details-expanded"
          >
            {JSON.stringify(details, null, 2)}
          </pre>
          <button
            className="text-xs text-muted-foreground underline mt-1"
            onClick={() => setExpanded(false)}
          >
            collapse
          </button>
        </div>
      ) : (
        <button
          className="text-xs text-muted-foreground underline truncate block max-w-[160px]"
          onClick={() => setExpanded(true)}
          data-testid="details-summary"
        >
          {summary || 'expand'}
        </button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Active filter chips — AC5
// ---------------------------------------------------------------------------

interface ActiveChipsProps {
  datePreset: DatePreset | null
  actionFilter: string
  actorFilter: string
  onRemoveDatePreset: () => void
  onRemoveAction: () => void
  onRemoveActor: () => void
}

function ActiveChips({
  datePreset,
  actionFilter,
  actorFilter,
  onRemoveDatePreset,
  onRemoveAction,
  onRemoveActor,
}: ActiveChipsProps) {
  const chips: { label: string; onRemove: () => void; testId: string }[] = []
  if (datePreset) {
    const preset = DATE_PRESETS.find((p) => p.value === datePreset)
    chips.push({
      label: preset?.label ?? datePreset,
      onRemove: onRemoveDatePreset,
      testId: 'chip-date',
    })
  }
  if (actionFilter) {
    const opt = ACTION_OPTIONS.find((o) => o.value === actionFilter)
    chips.push({
      label: opt?.label ?? actionFilter,
      onRemove: onRemoveAction,
      testId: 'chip-action',
    })
  }
  if (actorFilter) {
    chips.push({
      label: `Actor: ${actorFilter.slice(0, 8)}…`,
      onRemove: onRemoveActor,
      testId: 'chip-actor',
    })
  }

  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2" data-testid="active-filters">
      {chips.map((chip) => (
        <span
          key={chip.testId}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-secondary text-xs font-medium"
          data-testid={chip.testId}
        >
          {chip.label}
          <button
            onClick={chip.onRemove}
            aria-label={`Remove ${chip.label} filter`}
            className="hover:text-destructive"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AuditLogs Page
// ---------------------------------------------------------------------------

const PER_PAGE = 50

export default function AuditLogs() {
  const [searchParams, setSearchParams] = useSearchParams()

  // --- Filter state (from URL params — AC5 persistence) ---
  const [datePreset, setDatePreset] = useState<DatePreset | null>(
    (searchParams.get('preset') as DatePreset) || null,
  )
  const [actionFilter, setActionFilter] = useState(searchParams.get('action') ?? '')
  const [actorFilter, setActorFilter] = useState(searchParams.get('actor') ?? '')
  const [page, setPage] = useState(Number(searchParams.get('page') ?? '1'))

  // --- Data state ---
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // --- Export state ---
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  // --- Toast state ---
  const [toastError, setToastError] = useState<string | null>(null)

  // ---------------------------------------------------------------------------
  // Persist filters in URL (AC5)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const params: Record<string, string> = {}
    if (datePreset) params['preset'] = datePreset
    if (actionFilter) params['action'] = actionFilter
    if (actorFilter) params['actor'] = actorFilter
    if (page > 1) params['page'] = String(page)
    setSearchParams(params, { replace: true })
  }, [datePreset, actionFilter, actorFilter, page, setSearchParams])

  // ---------------------------------------------------------------------------
  // Fetch audit logs
  // ---------------------------------------------------------------------------

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError(null)

    const filters: AuditLogFilters = { page, per_page: PER_PAGE }

    if (datePreset && datePreset !== 'custom') {
      const preset = DATE_PRESETS.find((p) => p.value === datePreset)
      if (preset) {
        filters.date_from = _isoFromNow(preset.days)
      }
    }
    if (actionFilter) filters.action = actionFilter
    if (actorFilter) filters.actor_user_id = actorFilter

    try {
      const data = await adminApi.getAuditLogs(filters)
      setEntries(data.data)
      setTotalPages(data.pagination.total_pages)
      setTotal(data.pagination.total)
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to load audit logs.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [datePreset, actionFilter, actorFilter, page])

  useEffect(() => {
    fetchLogs()
  }, [fetchLogs])

  // ---------------------------------------------------------------------------
  // CSV Export — AC6
  // ---------------------------------------------------------------------------

  async function handleExport() {
    setExporting(true)
    setExportError(null)
    try {
      const filters: Omit<AuditLogFilters, 'page' | 'per_page'> = {}
      if (datePreset && datePreset !== 'custom') {
        const preset = DATE_PRESETS.find((p) => p.value === datePreset)
        if (preset) filters.date_from = _isoFromNow(preset.days)
      }
      if (actionFilter) filters.action = actionFilter
      if (actorFilter) filters.actor_user_id = actorFilter

      const blob = await adminApi.exportAuditLogs(filters)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'audit-logs.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Export failed. Please try again.'
      setExportError(msg)
      setToastError(msg)
      setTimeout(() => setToastError(null), 5000)
    } finally {
      setExporting(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-4">
      {/* Toast error overlay */}
      {toastError && (
        <div
          className="fixed bottom-4 right-4 z-50 max-w-sm rounded-md border border-destructive bg-destructive/10 p-4 text-destructive text-sm shadow-lg"
          data-testid="toast-error"
        >
          {toastError}
        </div>
      )}

      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold tracking-tight">Audit Logs</h1>
          {total > 0 && (
            <span className="text-sm text-muted-foreground">({total.toLocaleString()} entries)</span>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleExport}
          disabled={exporting}
          data-testid="export-btn"
        >
          {exporting ? (
            <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
          ) : (
            <Download className="h-4 w-4 mr-1.5" />
          )}
          Export CSV
        </Button>
      </div>

      {/* Filter bar — AC5 */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-card p-4" data-testid="filter-bar">
        <div className="flex items-center gap-1.5">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">Filters</span>
        </div>

        {/* Date preset */}
        <div className="flex gap-1">
          {DATE_PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => { setDatePreset(datePreset === p.value ? null : p.value); setPage(1) }}
              className={`px-2 py-1 text-xs rounded border transition-colors ${
                datePreset === p.value
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-background text-muted-foreground border-border hover:bg-muted'
              }`}
              data-testid={`preset-${p.value}`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Action type */}
        <select
          className="h-8 rounded border border-border bg-background px-2 text-sm"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
          data-testid="action-filter"
        >
          {ACTION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* Actor UUID */}
        <Input
          placeholder="Actor UUID"
          className="h-8 w-52 text-sm"
          value={actorFilter}
          onChange={(e) => { setActorFilter(e.target.value); setPage(1) }}
          data-testid="actor-filter"
        />
      </div>

      {/* Active filter chips — AC5 */}
      <ActiveChips
        datePreset={datePreset}
        actionFilter={actionFilter}
        actorFilter={actorFilter}
        onRemoveDatePreset={() => { setDatePreset(null); setPage(1) }}
        onRemoveAction={() => { setActionFilter(''); setPage(1) }}
        onRemoveActor={() => { setActorFilter(''); setPage(1) }}
      />

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-48" data-testid="loading-state">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-destructive text-sm"
          data-testid="error-state"
        >
          {error}
        </div>
      ) : entries.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center rounded-lg border bg-muted/20 py-16 text-center"
          data-testid="empty-state"
        >
          <FileText className="h-10 w-10 text-muted-foreground mb-3" />
          <p className="text-muted-foreground text-sm">No audit entries match your filters.</p>
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-44">Timestamp</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-36">Actor</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-40">Action</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">Resource</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground">Details</th>
                  <th className="text-left px-4 py-3 font-medium text-muted-foreground w-32">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y" data-testid="audit-log-table">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-muted/20" data-testid={`log-row-${entry.id}`}>
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {_formatTimestamp(entry.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-mono text-muted-foreground"
                        title={entry.actor_user_id}
                        data-testid={`actor-${entry.id}`}
                      >
                        {entry.actor_user_id.slice(0, 8)}…
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-secondary"
                        data-testid={`action-${entry.id}`}
                      >
                        {_humanizeAction(entry.action)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <span data-testid={`resource-type-${entry.id}`}>{entry.resource_type}</span>
                    </td>
                    <td className="px-4 py-3">
                      <DetailsCell details={entry.details} />
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {entry.ip_address ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination — AC4: 50 per page */}
      {!loading && !error && totalPages > 1 && (
        <div className="flex items-center justify-between text-sm" data-testid="pagination">
          <span className="text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p - 1)}
              disabled={page <= 1}
              data-testid="prev-page"
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages}
              data-testid="next-page"
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
