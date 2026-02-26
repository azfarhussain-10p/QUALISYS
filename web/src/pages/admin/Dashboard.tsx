/**
 * Admin Dashboard Page — /admin/dashboard
 * Story: 1-12-usage-analytics-audit-logs-basic
 * AC: #1 — MetricCard widgets: active users, active projects, test runs (placeholder), storage (placeholder)
 * AC: #1 — Owner/Admin only (redirects non-admin to /projects)
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, BarChart3, FileText } from 'lucide-react'
import { MetricCard } from '@/components/admin/MetricCard'
import { adminApi, ApiError, DashboardMetrics } from '@/lib/api'

// ---------------------------------------------------------------------------
// Dashboard Page
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchMetrics() {
      setLoading(true)
      setError(null)
      try {
        const data = await adminApi.getMetrics()
        if (!cancelled) setMetrics(data)
      } catch (err) {
        if (!cancelled) {
          const message =
            err instanceof ApiError ? err.message : 'Failed to load analytics.'
          setError(message)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchMetrics()
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="loading-state">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-destructive text-sm"
        data-testid="error-state"
      >
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        </div>
        <Link
          to="/admin/audit-logs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <FileText className="h-4 w-4" />
          View audit logs
        </Link>
      </div>

      {/* Metric cards grid — AC1 */}
      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        data-testid="metrics-grid"
      >
        <MetricCard
          title="Active Users"
          value={metrics?.active_users ?? 0}
          description="Members in your organization"
          testId="active-users"
        />
        <MetricCard
          title="Active Projects"
          value={metrics?.active_projects ?? 0}
          description="Projects currently active"
          testId="active-projects"
        />
        <MetricCard
          title="Test Runs"
          value={metrics?.test_runs ?? '—'}
          description="Available in Epic 2-4"
          testId="test-runs"
        />
        <MetricCard
          title="Storage Consumed"
          value={metrics?.storage_consumed ?? '—'}
          description="Available in Epic 2"
          testId="storage"
        />
      </div>
    </div>
  )
}
