/**
 * Artifacts Tab — Story 2-10 (viewer) + Story 2-11 (editing + versioning)
 * AC-26b: 4 tabs filtering by artifact_type (coverage_matrix, manual_checklist, playwright_script, bdd_scenario).
 * AC-26c: Contextual empty state per tab.
 * AC-26d: Coverage matrix → HTML table from JSON; others → pre block with font-mono.
 * AC-27: Monaco Editor inline per expanded ArtifactCard with language-appropriate syntax highlighting.
 * AC-28: Save edits → PUT /artifacts/{id} → new artifact_versions row; version history dropdown.
 * AC-29: Compare Versions → Monaco DiffEditor side-by-side.
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Editor, { DiffEditor } from '@monaco-editor/react'
import {
  ClipboardList,
  CheckSquare,
  Code2,
  List,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Edit2,
  Save,
  X,
} from 'lucide-react'
import { ArtifactDetail, ArtifactSummary, ArtifactVersionSummary, artifactApi } from '@/lib/api'

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
// Monaco language mapping (AC-27, C7)
// ---------------------------------------------------------------------------

function monacoLanguage(artifactType: ArtifactType): string {
  switch (artifactType) {
    case 'playwright_script':
      return 'typescript'
    case 'manual_checklist':
      return 'markdown'
    case 'coverage_matrix':
      return 'json'
    default:
      return 'plaintext' // bdd_scenario — Monaco has no built-in gherkin
  }
}

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
// Artifact card (collapsed + expandable + editable + versioned + diff)
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

  // AC-27: Edit mode state
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saveError, setSaveError] = useState<string | null>(null)

  // AC-28: Version history state — null means viewing current version
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null)

  // AC-29: Diff view state
  const [diffMode, setDiffMode] = useState(false)
  const [diffVersionA, setDiffVersionA] = useState(0)
  const [diffVersionB, setDiffVersionB] = useState(0)

  const queryClient = useQueryClient()

  // Fetch current-version detail when expanded
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

  // AC-28: Fetch version list when expanded and multi-version artifact
  const { data: versions } = useQuery<ArtifactVersionSummary[]>({
    queryKey: ['artifact-versions', projectId, artifact.id],
    queryFn: () => artifactApi.listVersions(projectId, artifact.id),
    enabled: expanded && artifact.current_version > 1,
    staleTime: 30_000,
  })

  // AC-28: Fetch historical version content when a past version is selected
  const { data: historicalDetail } = useQuery<ArtifactDetail>({
    queryKey: ['artifact-version-detail', projectId, artifact.id, selectedVersion],
    queryFn: () => artifactApi.getVersion(projectId, artifact.id, selectedVersion!),
    enabled: selectedVersion !== null,
    staleTime: 5 * 60 * 1000,
  })

  // AC-29: Fetch diff version content for DiffEditor
  const { data: diffOriginal } = useQuery<ArtifactDetail>({
    queryKey: ['artifact-version-detail', projectId, artifact.id, diffVersionA],
    queryFn: () => artifactApi.getVersion(projectId, artifact.id, diffVersionA),
    enabled: diffMode && diffVersionA > 0,
    staleTime: 5 * 60 * 1000,
  })
  const { data: diffModified } = useQuery<ArtifactDetail>({
    queryKey: ['artifact-version-detail', projectId, artifact.id, diffVersionB],
    queryFn: () => artifactApi.getVersion(projectId, artifact.id, diffVersionB),
    enabled: diffMode && diffVersionB > 0,
    staleTime: 5 * 60 * 1000,
  })

  // AC-28: Save mutation — PUT /artifacts/{id}
  const saveMutation = useMutation({
    mutationFn: (content: string) => artifactApi.update(projectId, artifact.id, content),
    onSuccess: () => {
      setEditing(false)
      setSaveError(null)
      queryClient.invalidateQueries({ queryKey: ['artifact-detail', projectId, artifact.id] })
      queryClient.invalidateQueries({ queryKey: ['artifacts', projectId] })
      queryClient.invalidateQueries({ queryKey: ['artifact-versions', projectId, artifact.id] })
    },
    onError: () => setSaveError('Failed to save. Please try again.'),
  })

  const handleToggle = () => setExpanded((prev) => !prev)

  const tokensUsed = artifact.metadata?.tokens_used

  // Edit button shown only when: expanded, detail loaded, not editing, not in diff mode,
  // and viewing current version (C6)
  const showEditButton =
    expanded && detail && !editing && !diffMode && selectedVersion === null

  // Compare Versions button shown when current_version > 1 and not editing/diffing
  const showCompareButton = artifact.current_version > 1 && !editing && !diffMode

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm" data-testid={`artifact-card-${artifact.id}`}>
      {/* Card header — toggle + version badge + action buttons */}
      <div className="flex items-center gap-2 px-4 py-3">
        <button
          type="button"
          className="flex flex-1 items-center gap-3 text-left hover:bg-gray-50 transition-colors min-w-0"
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

        {/* Action buttons (shown in header when expanded) */}
        {expanded && detail && (
          <div className="flex shrink-0 items-center gap-1">
            {showEditButton && (
              <button
                type="button"
                className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                onClick={() => {
                  setEditContent(detail.content)
                  setEditing(true)
                }}
                title="Edit artifact"
              >
                <Edit2 className="h-3 w-3" />
                Edit
              </button>
            )}
            {showCompareButton && (
              <button
                type="button"
                className="flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                onClick={() => {
                  setDiffMode(true)
                  setEditing(false)
                  setDiffVersionA(artifact.current_version - 1)
                  setDiffVersionB(artifact.current_version)
                }}
                title="Compare versions"
              >
                Compare Versions
              </button>
            )}
          </div>
        )}
      </div>

      {loadError && (
        <div className="mx-4 mb-3 flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          <AlertCircle className="h-3 w-3 shrink-0" />
          Failed to load artifact content.
        </div>
      )}

      {expanded && detail && (
        <div className="border-t border-gray-100 px-4 py-3 space-y-3">

          {/* AC-28: Version history dropdown — shown above content when multi-version */}
          {artifact.current_version > 1 && versions && versions.length > 0 && !editing && !diffMode && (
            <div className="flex items-center gap-2">
              <label className="text-xs font-medium text-gray-600 shrink-0">Version:</label>
              <select
                className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={selectedVersion ?? ''}
                onChange={(e) =>
                  setSelectedVersion(e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">Current (v{artifact.current_version})</option>
                {versions
                  .filter((v) => v.version !== artifact.current_version)
                  .map((v) => (
                    <option key={v.version} value={v.version}>
                      v{v.version} — {v.created_at ? formatDate(v.created_at) : ''}
                    </option>
                  ))}
              </select>
            </div>
          )}

          {/* AC-29: Diff view */}
          {diffMode && (
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1">
                  <label className="text-xs font-medium text-gray-600">Original:</label>
                  <select
                    className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={diffVersionA}
                    onChange={(e) => setDiffVersionA(Number(e.target.value))}
                  >
                    {versions
                      ? versions.map((v) => (
                          <option key={v.version} value={v.version}>
                            v{v.version}
                          </option>
                        ))
                      : Array.from({ length: artifact.current_version }, (_, i) => i + 1).map((v) => (
                          <option key={v} value={v}>
                            v{v}
                          </option>
                        ))}
                  </select>
                </div>
                <div className="flex items-center gap-1">
                  <label className="text-xs font-medium text-gray-600">Modified:</label>
                  <select
                    className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={diffVersionB}
                    onChange={(e) => setDiffVersionB(Number(e.target.value))}
                  >
                    {versions
                      ? versions.map((v) => (
                          <option key={v.version} value={v.version}>
                            v{v.version}
                          </option>
                        ))
                      : Array.from({ length: artifact.current_version }, (_, i) => i + 1).map((v) => (
                          <option key={v} value={v}>
                            v{v}
                          </option>
                        ))}
                  </select>
                </div>
                <button
                  type="button"
                  className="ml-auto flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 transition-colors"
                  onClick={() => setDiffMode(false)}
                >
                  <X className="h-3 w-3" />
                  Close Diff
                </button>
              </div>
              <DiffEditor
                height="500px"
                language={monacoLanguage(artifactType)}
                original={diffOriginal?.content ?? ''}
                modified={diffModified?.content ?? ''}
                options={{ readOnly: true, minimap: { enabled: false } }}
              />
            </div>
          )}

          {/* AC-27 + AC-28: Monaco editor (edit mode) */}
          {!diffMode && editing && (
            <div className="space-y-2">
              <Editor
                height="400px"
                language={monacoLanguage(artifactType)}
                value={editContent}
                onChange={(v) => setEditContent(v ?? '')}
                options={{ minimap: { enabled: false }, scrollBeyondLastLine: false }}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  onClick={() => saveMutation.mutate(editContent)}
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Save className="h-3 w-3" />
                  )}
                  {saveMutation.isPending ? 'Saving…' : 'Save'}
                </button>
                <button
                  type="button"
                  className="flex items-center gap-1 rounded border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  onClick={() => {
                    setEditing(false)
                    setSaveError(null)
                  }}
                >
                  <X className="h-3 w-3" />
                  Cancel
                </button>
              </div>
              {saveError && (
                <div className="flex items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {saveError}
                </div>
              )}
            </div>
          )}

          {/* Read-only content — current or historical version */}
          {!diffMode && !editing && (
            <>
              {selectedVersion !== null ? (
                // Historical version — read-only
                historicalDetail ? (
                  artifactType === 'coverage_matrix' ? (
                    <CoverageMatrixTable content={historicalDetail.content} />
                  ) : (
                    <pre className="whitespace-pre-wrap break-words rounded-md bg-gray-50 p-4 text-sm font-mono text-gray-800 max-h-[600px] overflow-y-auto">
                      {historicalDetail.content}
                    </pre>
                  )
                ) : (
                  <div className="flex justify-center py-6">
                    <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                  </div>
                )
              ) : (
                // Current version
                artifactType === 'coverage_matrix' ? (
                  <CoverageMatrixTable content={detail.content} />
                ) : (
                  <pre className="whitespace-pre-wrap break-words rounded-md bg-gray-50 p-4 text-sm font-mono text-gray-800 max-h-[600px] overflow-y-auto">
                    {detail.content}
                  </pre>
                )
              )}
            </>
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

      {/* Artifact cards — AC-26b, AC-26d, AC-27, AC-28, AC-29 */}
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
