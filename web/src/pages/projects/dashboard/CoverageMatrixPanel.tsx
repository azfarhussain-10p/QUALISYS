/**
 * QUALISYS — Coverage Matrix Drill-Down Panel
 * Story: 2-13-pm-dashboard-test-coverage-metrics
 * AC-2: Requirement coverage table sourced from GET /dashboard/coverage/matrix
 */

import { CoverageMatrixData } from '@/lib/api'

interface Props {
  data: CoverageMatrixData | undefined
  projectId: string
}

export function CoverageMatrixPanel({ data, projectId: _projectId }: Props) {
  if (!data) return null

  if (data.requirements.length === 0) {
    return (
      <div className="mt-4 rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        No coverage data yet — run AI agents to generate a coverage matrix.{' '}
        {data.fallback_url && (
          <a href={data.fallback_url} className="text-indigo-600 underline">
            View Artifacts →
          </a>
        )}
      </div>
    )
  }

  return (
    <div className="mt-4 rounded border border-gray-200 overflow-hidden">
      <div className="bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700">
        Coverage Matrix — {data.artifact_title ?? 'Latest'}
        {data.generated_at && (
          <span className="ml-2 text-xs text-gray-400">
            Generated {new Date(data.generated_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-100 text-left text-xs text-gray-500">
            <th className="px-4 py-2">Requirement</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Tests</th>
          </tr>
        </thead>
        <tbody>
          {data.requirements.map((req, i) => (
            <tr key={i} className="border-t border-gray-100">
              <td className="px-4 py-2 text-gray-800">{req.name}</td>
              <td className="px-4 py-2">
                {req.covered ? (
                  <span className="text-green-600 font-medium">✅ Covered</span>
                ) : (
                  <span className="text-red-600 font-medium">❌ Missing</span>
                )}
              </td>
              <td className="px-4 py-2 text-gray-500">{req.test_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
