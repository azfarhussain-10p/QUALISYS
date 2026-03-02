/**
 * QUALISYS — PM/CSM Multi-Project Health Grid
 * Story: 2-13-pm-dashboard-test-coverage-metrics
 * AC-3: Tenant-level grid of all project health cards
 * Route: /orgs/:orgId/pm-dashboard
 */

import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { dashboardApi, DashboardOverview, ProjectHealthItem } from '@/lib/api'
import { HealthDot, formatRelative } from '@/components/dashboard/health'

// ---------------------------------------------------------------------------
// Project card
// ---------------------------------------------------------------------------

function ProjectCard({ project }: { project: ProjectHealthItem }) {
  return (
    <Link
      to={`/projects/${project.project_id}/dashboard`}
      className="block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow"
    >
      <div className="flex items-center gap-2 mb-3">
        <HealthDot status={project.health_status as DashboardOverview['health_status']} />
        <h3 className="font-semibold text-gray-900 truncate">{project.project_name}</h3>
      </div>
      <div className="text-2xl font-bold text-gray-800 mb-1">
        {project.coverage_pct != null ? `${project.coverage_pct}%` : '—'}
      </div>
      <div className="text-xs text-gray-500">
        {project.coverage_pct != null ? 'coverage' : 'No coverage data'}
      </div>
      {project.last_run_at && (
        <div className="text-xs text-gray-400 mt-2">
          Last run {formatRelative(project.last_run_at)}
        </div>
      )}
    </Link>
  )
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-3 h-3 rounded-full bg-gray-200" />
        <div className="h-4 bg-gray-200 rounded w-2/3" />
      </div>
      <div className="h-8 bg-gray-200 rounded w-1/2 mb-1" />
      <div className="h-3 bg-gray-100 rounded w-1/3" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ProjectsGridPage() {
  const { orgId } = useParams<{ orgId: string }>()

  const { data, isLoading } = useQuery({
    queryKey: ['projects-health', orgId],
    queryFn: () => dashboardApi.getProjectsHealth(orgId!),
    staleTime: 60_000,
    enabled: !!orgId,
  })

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Project Health Overview</h1>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !data || data.projects.length === 0 ? (
        <div className="text-center py-16 text-gray-500">No projects found.</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.projects.map((project) => (
            <ProjectCard key={project.project_id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}
