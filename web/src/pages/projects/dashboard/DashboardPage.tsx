/**
 * QUALISYS — PM/CSM Project Health Dashboard
 * Story: 2-12-pm-csm-dashboard-project-health-overview
 *        2-13-pm-dashboard-test-coverage-metrics
 * AC-30: Health indicator dot, coverage %, recent activity
 * AC-31: Coverage trend LineChart (Recharts) with configurable target line
 * AC-32: SSE auto-refresh via EventSource (dashboard_refresh event every 30s)
 * AC-33: Placeholder widgets — Execution Velocity + Defect Leakage (Coming Soon)
 * AC-1:  Week-over-week trend badge
 * AC-2:  Coverage matrix drill-down panel
 */

import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  BarChart,
  Bar,
  ResponsiveContainer,
} from 'recharts'
import { dashboardApi, DashboardOverview } from '@/lib/api'
import { HealthDot, formatRelative } from '@/components/dashboard/health'
import { CoverageMatrixPanel } from './CoverageMatrixPanel'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function computeHealthLabel(status: DashboardOverview['health_status']): string {
  return (
    { green: 'Healthy', yellow: 'At Risk', red: 'Critical', no_data: 'No Data' }[status] ??
    'Unknown'
  )
}

// AC-1 — Week-over-week trend badge
function TrendBadge({ direction, pct }: { direction: string; pct: number | null }) {
  if (direction === 'no_data') {
    return <span className="text-xs text-gray-400">No trend data yet</span>
  }
  if (direction === 'flat') {
    return <span className="text-xs text-gray-500">→ No change from last week</span>
  }
  const isUp = direction === 'up'
  const arrow = isUp ? '↑' : '↓'
  const colour = isUp ? 'text-green-600' : 'text-red-600'
  return (
    <span className={`text-xs font-medium ${colour}`}>
      {arrow} {Math.abs(pct ?? 0).toFixed(1)}% from last week
    </span>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const queryClient = useQueryClient()

  // Target line — persisted in localStorage per project
  const [target, setTarget] = useState<number>(() =>
    Number(localStorage.getItem(`dashboard_target_${projectId}`) ?? '80'),
  )

  // Overview query (AC-30)
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
  } = useQuery({
    queryKey: ['dashboard-overview', projectId],
    queryFn: () => dashboardApi.getOverview(projectId!),
    staleTime: 30_000,
    enabled: !!projectId,
  })

  // Coverage trend query (AC-31 + AC-1)
  const { data: coverage, isLoading: coverageLoading } = useQuery({
    queryKey: ['dashboard-coverage', projectId],
    queryFn: () => dashboardApi.getCoverage(projectId!),
    staleTime: 30_000,
    enabled: !!projectId,
  })

  // AC-2 — Coverage matrix drill-down (lazy: only fires when user clicks "View Details")
  const [showMatrix, setShowMatrix] = useState(false)
  const { data: matrixData } = useQuery({
    queryKey: ['coverage-matrix', projectId],
    queryFn: () => dashboardApi.getCoverageMatrix(projectId!),
    enabled: showMatrix && !!projectId,
  })

  // SSE auto-refresh (AC-32)
  useEffect(() => {
    if (!projectId) return
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const es = new EventSource(`${baseUrl}/api/v1/events/dashboard/${projectId}`, {
      withCredentials: true,
    })
    es.addEventListener('dashboard_refresh', () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-overview', projectId] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-coverage', projectId] })
    })
    return () => es.close()
  }, [projectId, queryClient])

  const handleTargetChange = (v: number) => {
    localStorage.setItem(`dashboard_target_${projectId}`, String(v))
    setTarget(v)
  }

  // Placeholder dummy data (AC-33) — no API calls
  const velocityData = [
    { w: 'W1', v: 3 },
    { w: 'W2', v: 5 },
    { w: 'W3', v: 8 },
  ]
  const leakageData = [
    { w: 'W1', v: 0 },
    { w: 'W2', v: 1 },
    { w: 'W3', v: 0 },
  ]

  if (overviewLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-500">
        Loading dashboard…
      </div>
    )
  }

  if (overviewError) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          Failed to load dashboard data. Please try again.
        </div>
      </div>
    )
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="p-6 space-y-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900">Project Health Dashboard</h1>

      {/* AC-30 — Overview card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <h2 className="text-lg font-medium text-gray-800">Overview</h2>

        <div className="flex items-center gap-3">
          {overview && <HealthDot status={overview.health_status} />}
          <span className="font-semibold text-gray-700">
            {overview ? computeHealthLabel(overview.health_status) : '—'}
          </span>
        </div>

        <div className="text-3xl font-bold text-gray-900">
          {overview?.coverage_pct != null ? `${overview.coverage_pct}% coverage` : 'No coverage data'}
        </div>

        <div className="text-sm text-gray-500">
          {overview?.last_run_at
            ? `${overview.artifact_count} artifact${overview.artifact_count === 1 ? '' : 's'} generated ${formatRelative(overview.last_run_at)}`
            : 'No agent runs yet'}
        </div>
      </div>

      {/* AC-31 — Coverage trend card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-800">Coverage Trend</h2>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <label htmlFor="target-input">Target (%)</label>
            <input
              id="target-input"
              type="number"
              min="0"
              max="100"
              value={target}
              onChange={(e) => handleTargetChange(Number(e.target.value))}
              className="w-16 border rounded px-1 text-sm"
            />
          </div>
        </div>

        {coverageLoading ? (
          <div className="h-[220px] flex items-center justify-center text-gray-400">
            Loading trend data…
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 flex-wrap">
              <p className="text-sm text-gray-600">
                {coverage
                  ? `${coverage.requirements_covered} of ${coverage.total_requirements} requirements covered` +
                    (coverage.coverage_pct != null ? ` (${coverage.coverage_pct}%)` : '')
                  : 'No requirements data'}
              </p>
              {/* AC-2 — drill-down toggle */}
              <button
                onClick={() => setShowMatrix((v) => !v)}
                className="text-xs text-indigo-600 underline"
              >
                {showMatrix ? 'Hide Details' : 'View Details →'}
              </button>
            </div>

            {/* AC-1 — week-over-week badge */}
            {coverage && (
              <TrendBadge
                direction={coverage.week_over_week_direction ?? 'no_data'}
                pct={coverage.week_over_week_pct ?? null}
              />
            )}

            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={coverage?.trend ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} />
                <YAxis domain={[0, 100]} unit="%" />
                <Tooltip formatter={(v: number) => `${v}%`} />
                <ReferenceLine
                  y={target}
                  stroke="#6366f1"
                  strokeDasharray="4 4"
                  label={`Target ${target}%`}
                />
                <Line
                  type="monotone"
                  dataKey="coverage_pct"
                  stroke="#22c55e"
                  dot={false}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>

            {/* AC-2 — coverage matrix panel */}
            {showMatrix && (
              <CoverageMatrixPanel data={matrixData} projectId={projectId!} />
            )}
          </>
        )}
      </div>

      {/* AC-33 — Placeholder widgets */}
      <div className="grid grid-cols-2 gap-4">
        {/* Execution Velocity placeholder */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-2 opacity-40 pointer-events-none">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-medium text-gray-800">Execution Velocity</h3>
              <p className="text-xs text-gray-500">Available in Epic 3</p>
            </div>
            <span className="text-xs font-medium bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
              Coming Soon
            </span>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={velocityData}>
              <Bar dataKey="v" fill="#94a3b8" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Defect Leakage placeholder */}
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-2 opacity-40 pointer-events-none">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-medium text-gray-800">Defect Leakage</h3>
              <p className="text-xs text-gray-500">Available in Epic 4</p>
            </div>
            <span className="text-xs font-medium bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
              Coming Soon
            </span>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={leakageData}>
              <Line type="monotone" dataKey="v" stroke="#94a3b8" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
