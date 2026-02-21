/**
 * Security Settings Page
 * Story: 1-5-login-session-management
 * AC7 — Active sessions list: device, IP, current indicator, revoke per session
 * AC8 — "Log out of all devices" button
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Monitor, Loader2, Trash2, LogOut } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError, SessionInfo } from '@/lib/api'

// Parse a rough device label from the user_agent string
function parseDevice(userAgent: string | null): string {
  if (!userAgent) return 'Unknown device'
  if (/Mobile|Android|iPhone|iPad/.test(userAgent)) return 'Mobile device'
  if (/Windows/.test(userAgent)) return 'Windows PC'
  if (/Mac OS/.test(userAgent)) return 'Mac'
  if (/Linux/.test(userAgent)) return 'Linux PC'
  return 'Unknown device'
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// Session row
// ---------------------------------------------------------------------------
function SessionRow({
  session,
  onRevoke,
  revoking,
}: {
  session: SessionInfo
  onRevoke: (id: string) => void
  revoking: boolean
}) {
  const device = session.device_name || parseDevice(session.user_agent)

  return (
    <div
      className="flex items-start justify-between gap-4 rounded-lg border border-border px-4 py-3"
      data-testid={`session-row-${session.session_id}`}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="flex-shrink-0 mt-0.5 h-9 w-9 rounded-full bg-secondary flex items-center justify-center">
          <Monitor className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium truncate">{device}</span>
            {session.is_current && (
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                Current
              </span>
            )}
          </div>
          {session.ip && (
            <p className="text-xs text-muted-foreground mt-0.5">IP: {session.ip}</p>
          )}
          <p className="text-xs text-muted-foreground">
            Started: {formatDate(session.created_at)}
          </p>
        </div>
      </div>

      {/* Revoke button — not shown for current session (AC7) */}
      {!session.is_current && (
        <Button
          variant="ghost"
          size="sm"
          className="flex-shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
          disabled={revoking}
          onClick={() => onRevoke(session.session_id)}
          aria-label={`Revoke session on ${device}`}
          data-testid={`revoke-btn-${session.session_id}`}
        >
          {revoking ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Trash2 className="h-4 w-4" />
          )}
        </Button>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SecurityPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [logoutAllLoading, setLogoutAllLoading] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  // Load sessions on mount
  useEffect(() => {
    let cancelled = false
    authApi
      .getSessions()
      .then((data) => {
        if (!cancelled) setSessions(data.sessions)
      })
      .catch((err) => {
        if (!cancelled) {
          setFetchError(
            err instanceof ApiError
              ? err.message
              : 'Failed to load sessions. Please refresh.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const handleRevoke = async (sessionId: string) => {
    setActionError(null)
    setRevokingId(sessionId)
    try {
      await authApi.revokeSession(sessionId)
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId))
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : 'Failed to revoke session.',
      )
    } finally {
      setRevokingId(null)
    }
  }

  const handleLogoutAll = async () => {
    setActionError(null)
    setLogoutAllLoading(true)
    try {
      await authApi.logoutAll()
      navigate('/login', { replace: true })
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : 'Failed to log out all devices.',
      )
      setLogoutAllLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h2 className="text-2xl font-semibold mb-1">Security</h2>
      <p className="text-muted-foreground text-sm mb-8">
        Manage your active sessions and connected devices.
      </p>

      {/* Active sessions — AC7 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium">Active Sessions</h3>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
            disabled={logoutAllLoading || sessions.length === 0}
            onClick={handleLogoutAll}
            data-testid="logout-all-btn"
          >
            {logoutAllLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Logging out…
              </>
            ) : (
              <>
                <LogOut className="mr-2 h-4 w-4" />
                Log out of all devices
              </>
            )}
          </Button>
        </div>

        {actionError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="action-error"
          >
            {actionError}
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-10" data-testid="sessions-loading">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : fetchError ? (
          <div
            role="alert"
            className="rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
            data-testid="fetch-error"
          >
            {fetchError}
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center" data-testid="no-sessions">
            No active sessions found.
          </p>
        ) : (
          <div className="space-y-3" data-testid="sessions-list">
            {sessions.map((session) => (
              <SessionRow
                key={session.session_id}
                session={session}
                onRevoke={handleRevoke}
                revoking={revokingId === session.session_id}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
