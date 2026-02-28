/**
 * Artifacts Tab — Story 2-10
 * AC-26b: 4 tabs filtering by artifact_type (coverage_matrix, manual_checklist, playwright_script, bdd_scenario).
 * AC-26c: Contextual empty state per tab.
 * AC-26d: Coverage matrix → HTML table from JSON; others → pre block with font-mono.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ClipboardList,
  CheckSquare,
  Code2,
  List,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { ArtifactDetail, ArtifactSummary, artifactApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

const TABS = [
  {
    key: 'coverage_matrix' as const,
    label: 'Coverage Matrix',
    icon: ClipboardList,
    iconColor: 'text-blue-600',
    emptyMessage: 'No coverage matrix generated yet. Run the BA Consultant agent.',
  },
  {
    key: 'manual_checklist' as const,
    label: 'Manual Checklists',
    icon: CheckSquare,
    iconColor: 'text-green-600',
    emptyMessage: 'No manual checklists generated yet. Run the QA Consultant agent.',
  },
  {
    key: 'playwright_script' as const,
    label: 'Playwright Scripts',
    icon: Code2,
    iconColor: 'text-purple-600',
    emptyMessage: 'No Playwright scripts generated yet. Run the Automation Consultant agent.',
  },
  {
    key: 'bdd_scenario' as const,
    label: 'BDD Scenarios',
    icon: List,
    iconColor: 'text-amber-600',
    emptyMessage: 'No BDD scenarios generated yet. Run the QA Consultant agent.',
  },
] as const

type ArtifactType = (typeof TABS)[number]['key']

// ---------------------------------------------------------------------------
// Coverage matrix table renderer
// ---------------------------------------------------------------------------

interface CoverageMatrixRow {
  requirement_id: string
  description: string
  source: string
  coverage_status: string
  notes: string
}

function CoverageMatrixTable({ content }: { content: string }) {
  let rows: CoverageMatrixRow[]
  try {
    rows = JSON.parse(content)
    if (!Array.isArray(rows)) throw new Error('Not an array')
  } catch {
    return (
      <pre className="whitespace-pre-wrap break-words rounded-md bg-gray-50 p-4 text-sm font-mono text-gray-800">
        {content}
      </pre>
    )
  }

  if (rows.length === 0) {
    return <p className="text-sm text-gray-500 italic">Empty coverage matrix.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 text-sm" data-testid="coverage-matrix-table">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-gray-600">Req ID</th>
            <th className="px-3 py-2 text-left font-medium text-gray-600">Description</th>
            <th className="px-3 py-2 text-left font-medium text-gray-600">Source</th>
            <th className="px-3 py-2 text-left font-medium text-gray-600">Status</th>
            <th className="px-3 py-2 text-left font-medium text-gray-600">Notes</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{row.requirement_id}</td>
              <td className="px-3 py-2">{row.description}</td>
              <td className="px-3 py-2 whitespace-nowrap">{row.source}</td>
              <td className="px-3 py-2 whitespace-nowrap">
                <span
                  className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    row.coverage_status === 'covered'
                      ? 'bg-green-100 text-green-700'
                      : row.coverage_status === 'partially_covered'
                        ? 'bg-yellow-100 text-yellow-700'
                        : 'bg-red-100 text-red-700'
                  }`}
                >
                  {row.coverage_status}
                </span>
              </td>
              <td className="px-3 py-2 text-gray-600">{row.notes}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Artifact card (collapsed + expandable)
// ---------------------------------------------------------------------------

function agentDisplayName(agentType: string): string {
  switch (agentType) {
    case 'ba_consultant':
      return 'BA Consultant'
    case 'qa_consultant':
      return 'QA Consultant'
    case 'automation_consultant':
      return 'Automation Consultant'
    default:
      return agentType
  }
}

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

interface ArtifactCardProps {
  artifact: ArtifactSummary
  projectId: string
  artifactType: ArtifactType
}

function ArtifactCard({ artifact, projectId, artifactType }: ArtifactCardProps) {
  const [expanded, setExpanded] = useState(false)

  const {
    data: detail,
    isLoading: loading,
    isError: loadError,
  } = useQuery({
    queryKey: ['artifact-detail', projectId, artifact.id],
    queryFn: () => artifactApi.get(projectId, artifact.id),
    enabled: expanded,
    staleTime: 5 * 60 * 1000,
  })

  const handleToggle = () => setExpanded((prev) => !prev)

  const tokensUsed = artifact.metadata?.tokens_used

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm" data-testid={`artifact-card-${artifact.id}`}>
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
        onClick={handleToggle}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-gray-900 truncate">{artifact.title}</h4>
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
              v{artifact.current_version}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
            <span>{agentDisplayName(artifact.agent_type)}</span>
            <span>·</span>
            <span>{formatDate(artifact.created_at)}</span>
            {tokensUsed != null && (
              <>
                <span>·</span>
                <span>{tokensUsed.toLocaleString()} tokens</span>
              </>
            )}
          </div>
        </div>
        {loading ? (
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-gray-400" />
        ) : expanded ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-gray-400" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-gray-400" />
        )}
      </button>

      {loadError && (
        <div className="mx-4 mb-3 flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <AlertCircle className="h-3 w-3 shrink-0" />
          Failed to load artifact content.
        </div>
      )}

      {expanded && detail && (
        <div className="border-t border-gray-100 px-4 py-3">
          {artifactType === 'coverage_matrix' ? (
            <CoverageMatrixTable content={detail.content} />
          ) : (
            <pre className="whitespace-pre-wrap break-words rounded-md bg-gray-50 p-4 text-sm font-mono text-gray-800 max-h-[600px] overflow-y-auto">
              {detail.content}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ArtifactsTab — main component
// ---------------------------------------------------------------------------

interface ArtifactsTabProps {
  projectId: string
}

export default function ArtifactsTab({ projectId }: ArtifactsTabProps) {
  const [activeTab, setActiveTab] = useState<ArtifactType>('coverage_matrix')

  const currentTabDef = TABS.find((t) => t.key === activeTab)!

  const { data: artifacts, isLoading, isError } = useQuery({
    queryKey: ['artifacts', projectId, activeTab],
    queryFn: () => artifactApi.list(projectId, activeTab),
  })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">Test Artifacts</h2>
        <p className="mt-1 text-sm text-gray-500">
          Review AI-generated test outputs organized by type.
        </p>
      </div>

      {/* Tab buttons — AC-26b */}
      <div className="flex gap-1 border-b" data-testid="artifact-tabs">
        {TABS.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.key}
              type="button"
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
              onClick={() => setActiveTab(tab.key)}
              data-testid={`tab-${tab.key}`}
            >
              <Icon className={`h-4 w-4 ${activeTab === tab.key ? tab.iconColor : 'text-gray-400'}`} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Failed to load artifacts. Please refresh the page.
        </div>
      )}

      {/* Empty state — AC-26c */}
      {!isLoading && !isError && artifacts?.length === 0 && (
        <div
          className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-200 py-12 text-center"
          data-testid="empty-state"
        >
          {(() => {
            const Icon = currentTabDef.icon
            return <Icon className={`h-10 w-10 ${currentTabDef.iconColor} mb-3 opacity-40`} />
          })()}
          <p className="text-sm text-gray-500">{currentTabDef.emptyMessage}</p>
        </div>
      )}

      {/* Artifact cards — AC-26b, AC-26d */}
      {!isLoading && !isError && artifacts && artifacts.length > 0 && (
        <div className="space-y-3" data-testid="artifact-list">
          {artifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.id}
              artifact={artifact}
              projectId={projectId}
              artifactType={activeTab}
            />
          ))}
        </div>
      )}
    </div>
  )
}
