/**
 * QUALISYS — Shared Dashboard Health Helpers
 * Story: 2-13-pm-dashboard-test-coverage-metrics (O2 fix)
 * Extracted from DashboardPage.tsx / ProjectsGridPage.tsx to eliminate duplication.
 */

import { DashboardOverview } from '@/lib/api'

export function HealthDot({ status }: { status: DashboardOverview['health_status'] }) {
  const colours: Record<DashboardOverview['health_status'], string> = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-400',
    red: 'bg-red-500',
    no_data: 'bg-gray-300',
  }
  return <span className={`inline-block w-3 h-3 rounded-full ${colours[status]}`} />
}

export function formatRelative(isoStr: string): string {
  const diffMs = Date.now() - new Date(isoStr).getTime()
  const diffMin = Math.floor(diffMs / 60_000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? '' : 's'} ago`
  const diffDay = Math.floor(diffHr / 24)
  return `${diffDay} day${diffDay === 1 ? '' : 's'} ago`
}
