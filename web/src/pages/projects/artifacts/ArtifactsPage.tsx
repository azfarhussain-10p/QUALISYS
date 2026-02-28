/**
 * Artifacts Page — Story 2-10
 * Standalone route wrapper for ArtifactsTab at /projects/:projectId/artifacts.
 * AC-21: AgentsTab navigates here on pipeline completion.
 */

import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import ArtifactsTab from './ArtifactsTab'

export default function ArtifactsPage() {
  const { projectId } = useParams<{ projectId: string }>()

  if (!projectId) {
    return <div className="p-6 text-sm text-red-600">Missing project ID.</div>
  }

  return (
    <div className="max-w-5xl mx-auto p-6">
      <div className="mb-4">
        <Link
          to={`/projects/${projectId}/settings`}
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to project
        </Link>
      </div>
      <ArtifactsTab projectId={projectId} />
    </div>
  )
}
