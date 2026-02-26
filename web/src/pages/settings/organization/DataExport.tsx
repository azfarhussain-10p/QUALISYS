/**
 * Data Export Section — /settings/organization
 * Story: 1-13-data-export-org-deletion
 * AC: #1, #2, #5 — export button, background job, history, download links
 * Owner only.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { Download, Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { exportApi, ExportJob, ExportEstimate, ApiError } from '@/lib/api'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DataExportProps {
  orgId: string
  /** Current user's role — section only renders for 'owner' */
  userRole: string
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function StatusBadge({ status }: { status: ExportJob['status'] }) {
  if (status === 'completed') {
    return (
      <span className="inline-flex items-center gap-1 text-green-700 text-sm">
        <CheckCircle2 size={14} /> Completed
      </span>
    )
  }
  if (status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-red-600 text-sm">
        <XCircle size={14} /> Failed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-blue-600 text-sm">
      <Clock size={14} /> Processing
    </span>
  )
}

// ---------------------------------------------------------------------------
// DataExport Component
// ---------------------------------------------------------------------------

export default function DataExport({ orgId, userRole }: DataExportProps) {
  const [exports, setExports] = useState<ExportJob[]>([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)
  const [estimate, setEstimate] = useState<ExportEstimate | null>(null)

  // Ref to track current exports inside the polling interval without stale closure.
  // Updated synchronously after each fetch so the interval callback always reads
  // the latest value without being listed as an effect dependency (M3 fix).
  const exportsRef = useRef<ExportJob[]>(exports)

  // AC1: Fetch pre-export size estimate (Owner only, best-effort).
  const fetchEstimate = useCallback(async () => {
    try {
      const data = await exportApi.getEstimate(orgId)
      setEstimate(data)
    } catch {
      // Non-critical — estimate is informational only
    }
  }, [orgId])

  // AC5: Fetch the list of past export jobs.
  const fetchExports = useCallback(async () => {
    try {
      const data = await exportApi.listExports(orgId)
      exportsRef.current = data.exports   // keep ref in sync (M3 fix)
      setExports(data.exports)
    } catch {
      // Silently ignore list errors — not critical
    } finally {
      setLoading(false)
    }
  }, [orgId])

  // H1 fix: ALL hooks are declared unconditionally above this point.
  // The early-return for non-owners is placed AFTER all hook calls, which
  // satisfies React's Rules of Hooks — hooks are always called in the same order.
  // M3 fix: `exports` is NOT in the dependency array; the ref is used instead
  // so the interval is created once per orgId change and never recreated on fetch.
  useEffect(() => {
    fetchExports()
    fetchEstimate()

    // Poll every 5 s; use the ref to check for in-progress jobs without
    // creating a stale-closure or forcing the effect to re-run on each fetch.
    const interval = setInterval(() => {
      const hasProcessing = exportsRef.current.some((j) => j.status === 'processing')
      if (hasProcessing) fetchExports()
    }, 5000)

    return () => clearInterval(interval)
  }, [fetchExports, fetchEstimate]) // no `exports` — ref handles the check

  // Owner only — early return is SAFE here because all hooks were already called above.
  if (userRole !== 'owner') return null

  const handleExport = async () => {
    setExporting(true)
    setError(null)
    setSuccessMsg(null)
    try {
      await exportApi.requestExport(orgId)
      setSuccessMsg(
        'Export started! You will receive an email when it is ready. Check the history below.',
      )
      fetchExports()
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Failed to start export. Please try again.'
      setError(msg)
    } finally {
      setExporting(false)
    }
  }

  return (
    <section data-testid="data-export-section" className="space-y-6">
      <div>
        <h3 className="text-base font-semibold text-foreground">Data Export</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Export all organization data as a ZIP archive (JSON files per table).
          Limited to 1 export per 24 hours.
        </p>
      </div>

      {/* AC1: Pre-export size estimate */}
      {estimate && (
        <div
          data-testid="export-estimate"
          className="text-sm text-muted-foreground bg-muted/40 border border-border rounded-md px-4 py-3 space-y-1"
        >
          <p className="font-medium text-foreground">Data summary</p>
          <ul className="space-y-0.5">
            {Object.entries(estimate.tables).map(([table, count]) => (
              <li key={table} className="flex justify-between">
                <span className="text-muted-foreground">{table}</span>
                <span className="tabular-nums">{count.toLocaleString()} rows</span>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground pt-1">
            Total: {estimate.total_records.toLocaleString()} records
          </p>
        </div>
      )}

      {/* Export button */}
      <div className="flex items-center gap-4">
        <Button
          data-testid="export-data-btn"
          onClick={handleExport}
          disabled={exporting}
          variant="outline"
        >
          {exporting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Requesting…
            </>
          ) : (
            <>
              <Download className="mr-2 h-4 w-4" />
              Export All Data
            </>
          )}
        </Button>
      </div>

      {/* Success / Error feedback */}
      {successMsg && (
        <div
          data-testid="export-success"
          className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-md px-4 py-3"
        >
          {successMsg}
        </div>
      )}
      {error && (
        <div
          data-testid="export-error"
          className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-4 py-3"
        >
          {error}
        </div>
      )}

      {/* Export history */}
      <div>
        <h4 className="text-sm font-medium text-foreground mb-3">Export History</h4>
        {loading ? (
          <div className="flex items-center gap-2 text-muted-foreground text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading…
          </div>
        ) : exports.length === 0 ? (
          <p
            data-testid="no-exports"
            className="text-sm text-muted-foreground"
          >
            No exports yet.
          </p>
        ) : (
          <div
            data-testid="export-history"
            className="divide-y divide-border border border-border rounded-md"
          >
            {exports.map((job) => (
              <div
                key={job.job_id}
                data-testid={`export-job-${job.job_id}`}
                className="flex items-center justify-between px-4 py-3"
              >
                <div className="space-y-0.5">
                  <StatusBadge status={job.status} />
                  <p className="text-xs text-muted-foreground">
                    {formatDate(job.created_at)} · {formatBytes(job.file_size_bytes)}
                  </p>
                  {job.status === 'processing' && (
                    <p className="text-xs text-blue-600">
                      {job.progress_percent}% complete
                    </p>
                  )}
                  {job.error && (
                    <p className="text-xs text-red-600">{job.error}</p>
                  )}
                </div>
                {job.status === 'completed' && job.download_url && (
                  <a
                    href={job.download_url}
                    data-testid={`download-${job.job_id}`}
                    className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Download size={14} />
                    Download
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
