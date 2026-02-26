/**
 * MetricCard component — Story 1.12, AC1
 * Displays a single admin dashboard metric with title, value, and neutral trend indicator.
 * Used on /admin/dashboard. Based on shadcn/ui Card pattern.
 */

import { TrendingRight } from 'lucide-react'

interface MetricCardProps {
  title: string
  value: string | number
  description?: string
  /** data-testid suffix for testing (e.g., 'active-users' → data-testid='metric-active-users') */
  testId?: string
}

export function MetricCard({ title, value, description, testId }: MetricCardProps) {
  return (
    <div
      className="rounded-lg border bg-card text-card-foreground shadow-sm p-6"
      data-testid={testId ? `metric-${testId}` : undefined}
    >
      <div className="flex items-center justify-between mb-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        {/* Neutral trend indicator placeholder (AC1) */}
        <span
          className="inline-flex items-center text-muted-foreground"
          aria-label="Trend: neutral"
          data-testid={testId ? `trend-${testId}` : undefined}
        >
          <TrendingRight className="h-4 w-4" />
        </span>
      </div>
      <p
        className="text-3xl font-bold tracking-tight"
        data-testid={testId ? `value-${testId}` : undefined}
      >
        {value}
      </p>
      {description && (
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      )}
    </div>
  )
}
