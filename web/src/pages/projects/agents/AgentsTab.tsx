/**
 * Agents Tab — Stories 2-6 + 2-9
 * AC-15: Display 3 MVP agents with icon, name, description, required inputs, expected outputs.
 * AC-16: "Run Selected Agents" button — disabled when 0 selected; fires POST /agent-runs on click.
 * AC-19: Open EventSource to /api/v1/events/agent-runs/{run_id} after 201 response.
 * AC-20: Render live per-agent status cards (queued/running/complete/error).
 * AC-21: On all_done=true → show success banner + navigate to Artifacts tab after 1.5 s.
 */

import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  ClipboardList,
  CheckSquare,
  Code2,
  Loader2,
  AlertCircle,
  CheckCircle,
  ChevronRight,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AgentDefinition, ApiError, agentApi } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type AgentStatus = 'queued' | 'running' | 'complete' | 'error'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getAgentIcon(icon: string) {
  switch (icon) {
    case 'ClipboardList':
      return <ClipboardList className="h-6 w-6 text-blue-600" />
    case 'CheckSquare':
      return <CheckSquare className="h-6 w-6 text-green-600" />
    case 'Code2':
      return <Code2 className="h-6 w-6 text-purple-600" />
    default:
      return <ClipboardList className="h-6 w-6 text-gray-500" />
  }
}

// ---------------------------------------------------------------------------
// AgentCard (selection)
// ---------------------------------------------------------------------------

interface AgentCardProps {
  agent:    AgentDefinition
  selected: boolean
  onToggle: (agentType: string) => void
  disabled: boolean
}

function AgentCard({ agent, selected, onToggle, disabled }: AgentCardProps) {
  return (
    <div
      className={`relative cursor-pointer rounded-lg border-2 p-5 transition-all ${
        selected
          ? 'border-blue-500 bg-blue-50 shadow-md'
          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      onClick={() => !disabled && onToggle(agent.agent_type)}
      data-testid={`agent-card-${agent.agent_type}`}
    >
      {/* Checkbox indicator */}
      <div
        className={`absolute right-4 top-4 h-5 w-5 rounded border-2 transition-colors ${
          selected ? 'border-blue-500 bg-blue-500' : 'border-gray-300 bg-white'
        }`}
        aria-checked={selected}
        role="checkbox"
      >
        {selected && (
          <svg viewBox="0 0 12 10" className="h-full w-full fill-white p-0.5">
            <polyline points="1,5 4,9 11,1" strokeWidth="2" stroke="white" fill="none" />
          </svg>
        )}
      </div>

      {/* Icon + name */}
      <div className="flex items-center gap-3 pr-8">
        <div className="shrink-0">{getAgentIcon(agent.icon)}</div>
        <h3 className="text-base font-semibold text-gray-900">{agent.name}</h3>
      </div>

      {/* Description */}
      <p className="mt-2 text-sm text-gray-600">{agent.description}</p>

      {/* Required inputs */}
      <div className="mt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Required Inputs</p>
        <ul className="mt-1 space-y-0.5">
          {agent.required_inputs.map((input) => (
            <li key={input} className="flex items-center gap-1.5 text-xs text-gray-600">
              <ChevronRight className="h-3 w-3 shrink-0 text-gray-400" />
              {input}
            </li>
          ))}
        </ul>
      </div>

      {/* Expected outputs */}
      <div className="mt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Expected Outputs</p>
        <ul className="mt-1 space-y-0.5">
          {agent.expected_outputs.map((output) => (
            <li key={output} className="flex items-center gap-1.5 text-xs text-gray-700 font-medium">
              <CheckCircle className="h-3 w-3 shrink-0 text-green-500" />
              {output}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AgentStatusCard — AC-20: per-agent real-time status card
// ---------------------------------------------------------------------------

interface AgentStatusCardProps {
  agentType:    string
  agentName:    string
  status:       AgentStatus
  progressPct:  number
  progressLabel: string
}

function AgentStatusCard({
  agentType,
  agentName,
  status,
  progressPct,
  progressLabel,
}: AgentStatusCardProps) {
  const baseClass = 'rounded-lg border-2 p-4 transition-all'

  if (status === 'queued') {
    return (
      <div
        className={`${baseClass} border-gray-200 bg-gray-50`}
        data-testid={`status-card-${agentType}`}
      >
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full border-2 border-gray-300 bg-gray-200" />
          <span className="text-sm font-medium text-gray-500">{agentName}</span>
          <span className="ml-auto text-xs text-gray-400">Queued</span>
        </div>
      </div>
    )
  }

  if (status === 'running') {
    return (
      <div
        className={`${baseClass} border-blue-300 bg-blue-50`}
        data-testid={`status-card-${agentType}`}
      >
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
          <span className="text-sm font-medium text-blue-700">{agentName}</span>
          <span className="ml-auto text-xs text-blue-500">Running</span>
        </div>
        {progressLabel && (
          <p className="mt-1 text-xs text-blue-600">{progressLabel}</p>
        )}
        {/* Animated progress bar */}
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-blue-100">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>
    )
  }

  if (status === 'complete') {
    return (
      <div
        className={`${baseClass} border-green-300 bg-green-50`}
        data-testid={`status-card-${agentType}`}
      >
        <div className="flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-green-700">{agentName}</span>
          <span className="ml-auto text-xs text-green-500">Complete</span>
        </div>
      </div>
    )
  }

  // error
  return (
    <div
      className={`${baseClass} border-red-300 bg-red-50`}
      data-testid={`status-card-${agentType}`}
    >
      <div className="flex items-center gap-2">
        <XCircle className="h-4 w-4 text-red-500" />
        <span className="text-sm font-medium text-red-700">{agentName}</span>
        <span className="ml-auto text-xs text-red-500">Error</span>
      </div>
      {progressLabel && (
        <p className="mt-1 text-xs text-red-600">{progressLabel}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AgentsTab — main component
// ---------------------------------------------------------------------------

interface AgentsTabProps {
  projectId:   string
  projectRole: string | null
}

export default function AgentsTab({ projectId, projectRole }: AgentsTabProps) {
  const navigate = useNavigate()

  const [selected, setSelected]               = useState<Set<string>>(new Set())
  const [runError, setRunError]               = useState<string | null>(null)
  const [queuedRunId, setQueuedRunId]         = useState<string | null>(null)
  const [completionMessage, setCompletionMessage] = useState<string | null>(null)

  // AC-20: real-time status state
  const [activeAgents, setActiveAgents]           = useState<string[]>([])
  const [agentStatuses, setAgentStatuses]         = useState<Record<string, AgentStatus>>({})
  const [agentProgress, setAgentProgress]         = useState<Record<string, number>>({})
  const [agentLabels, setAgentLabels]             = useState<Record<string, string>>({})

  // Ref so cleanup effect always has the latest EventSource
  const eventSourceRef = useRef<EventSource | null>(null)

  const canRun = projectRole === 'owner' || projectRole === 'admin' || projectRole === 'qa-automation'

  // Cleanup EventSource on unmount (AC-20)
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  // AC-15: fetch agent definitions
  const { data: agents, isLoading, isError } = useQuery({
    queryKey: ['agents'],
    queryFn:  () => agentApi.listAgents(),
    staleTime: Infinity,
  })

  // Build a quick lookup: agent_type → agent name (for status cards)
  const agentNameMap = (agents ?? []).reduce<Record<string, string>>((acc, a) => {
    acc[a.agent_type] = a.name
    return acc
  }, {})

  // AC-16: run mutation
  const runMutation = useMutation({
    mutationFn: () => agentApi.startRun(projectId, Array.from(selected)),
    onSuccess: (run) => {
      setRunError(null)
      setQueuedRunId(run.id)
      setSelected(new Set())
      setCompletionMessage(null)

      // AC-20: initialise status cards for all selected agents
      const agents_selected = run.agents_selected
      setActiveAgents(agents_selected)
      const initialStatuses: Record<string, AgentStatus> = {}
      agents_selected.forEach((a) => { initialStatuses[a] = 'queued' })
      setAgentStatuses(initialStatuses)
      setAgentProgress({})
      setAgentLabels({})

      // AC-19: open EventSource for real-time updates
      const es = new EventSource(
        `/api/v1/events/agent-runs/${run.id}`,
        { withCredentials: true },
      )
      eventSourceRef.current = es

      es.onmessage = (e) => {
        // L-1: guard against malformed SSE data
        let parsed: { type: string; payload: Record<string, unknown> }
        try {
          parsed = JSON.parse(e.data) as { type: string; payload: Record<string, unknown> }
        } catch {
          setRunError('Received malformed event data from server.')
          return
        }
        const { type, payload } = parsed

        if (type === 'running') {
          const agentType = payload.agent_type as string
          setAgentStatuses((s) => ({ ...s, [agentType]: 'running' }))
          setAgentProgress((p) => ({ ...p, [agentType]: (payload.progress_pct as number) ?? 0 }))
          setAgentLabels((l) => ({ ...l, [agentType]: (payload.progress_label as string) ?? '' }))
        } else if (type === 'complete' && !payload.all_done) {
          const agentType = payload.agent_type as string
          setAgentStatuses((s) => ({ ...s, [agentType]: 'complete' }))
        } else if (type === 'complete' && payload.all_done) {
          // AC-21: pipeline done — close stream
          es.close()
          eventSourceRef.current = null
          if (payload.error) {
            // M-1c: pipeline failed — show error state, do NOT navigate to artifacts
            setRunError('Agent pipeline failed. Check the agent status cards above.')
            setActiveAgents([])
          } else {
            // Success path — show banner and navigate to artifacts after 1.5 s
            setCompletionMessage('Agent pipeline completed successfully!')
            setTimeout(() => {
              navigate(`/projects/${projectId}/artifacts`)
            }, 1500)
          }
        } else if (type === 'error') {
          const agentType = payload.agent_type as string
          setAgentStatuses((s) => ({ ...s, [agentType]: 'error' }))
          setAgentLabels((l) => ({ ...l, [agentType]: (payload.message as string) ?? 'Step failed' }))
        }
      }

      es.onerror = () => {
        setRunError('Connection to agent stream lost. Check the run status manually.')
        setActiveAgents([])  // L-2: re-enable agent selection after stream error
        es.close()
        eventSourceRef.current = null
      }
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError) {
        setRunError(err.message || 'Failed to start agent run.')
      } else {
        setRunError('Failed to start agent run. Please try again.')
      }
    },
  })

  const handleToggle = (agentType: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(agentType)) {
        next.delete(agentType)
      } else {
        next.add(agentType)
      }
      return next
    })
    setQueuedRunId(null)
    setRunError(null)
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    )
  }

  if (isError || !agents) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        <AlertCircle className="h-4 w-4 shrink-0" />
        Failed to load agent definitions. Please refresh the page.
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-900">AI Agents</h2>
        <p className="mt-1 text-sm text-gray-500">
          Select one or more agents to analyse your project and generate test artifacts.
        </p>
      </div>

      {/* Agent cards — AC-15 */}
      <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-3" data-testid="agent-cards">
        {agents.map((agent) => (
          <AgentCard
            key={agent.agent_type}
            agent={agent}
            selected={selected.has(agent.agent_type)}
            onToggle={handleToggle}
            disabled={!canRun || runMutation.isPending || activeAgents.length > 0}
          />
        ))}
      </div>

      {/* AC-20: Real-time status cards — shown while a run is active */}
      {activeAgents.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-700">Agent Pipeline Status</h3>
          <div className="grid gap-3 sm:grid-cols-1 lg:grid-cols-3" data-testid="status-cards">
            {activeAgents.map((agentType) => (
              <AgentStatusCard
                key={agentType}
                agentType={agentType}
                agentName={agentNameMap[agentType] ?? agentType}
                status={agentStatuses[agentType] ?? 'queued'}
                progressPct={agentProgress[agentType] ?? 0}
                progressLabel={agentLabels[agentType] ?? ''}
              />
            ))}
          </div>
        </div>
      )}

      {/* Error banner */}
      {runError && (
        <div
          className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          data-testid="run-error"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {runError}
          <button
            className="ml-auto text-red-500 hover:text-red-700"
            onClick={() => setRunError(null)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* Queued banner */}
      {queuedRunId && !completionMessage && (
        <div
          className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700"
          data-testid="run-queued"
        >
          <CheckCircle className="h-4 w-4 shrink-0" />
          <span>
            Agent pipeline queued!{' '}
            <span className="font-mono text-xs text-green-600">Run ID: {queuedRunId}</span>
          </span>
        </div>
      )}

      {/* AC-21: completion success banner */}
      {completionMessage && (
        <div
          className="flex items-center gap-2 rounded-lg border border-green-400 bg-green-100 px-4 py-3 text-sm font-semibold text-green-800"
          data-testid="run-complete"
        >
          <CheckCircle className="h-4 w-4 shrink-0 text-green-600" />
          {completionMessage}
          <span className="ml-auto text-xs font-normal text-green-600">Navigating to Artifacts…</span>
        </div>
      )}

      {/* Run button — AC-16 */}
      {canRun && (
        <div className="flex justify-end">
          <Button
            onClick={() => runMutation.mutate()}
            disabled={selected.size === 0 || runMutation.isPending || activeAgents.length > 0}
            data-testid="run-agents-btn"
          >
            {runMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Starting…
              </>
            ) : (
              `Run Selected Agents${selected.size > 0 ? ` (${selected.size})` : ''}`
            )}
          </Button>
        </div>
      )}
    </div>
  )
}
