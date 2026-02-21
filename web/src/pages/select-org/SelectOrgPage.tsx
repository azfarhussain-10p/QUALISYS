/**
 * Select Organization Page
 * Story: 1-5-login-session-management
 * AC6 — Multi-org users choose their active organization after login.
 *        Org list populated from sessionStorage (stored on login).
 *        POST /api/v1/auth/select-org issues a new JWT bound to chosen tenant.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Building2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError, TenantOrgInfo } from '@/lib/api'

// Role badge colors
const ROLE_COLORS: Record<string, string> = {
  owner: 'bg-purple-100 text-purple-700',
  admin: 'bg-blue-100 text-blue-700',
  member: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-600',
  billing: 'bg-yellow-100 text-yellow-700',
  support: 'bg-orange-100 text-orange-700',
}

function RoleBadge({ role }: { role: string }) {
  const colors = ROLE_COLORS[role] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium capitalize ${colors}`}>
      {role}
    </span>
  )
}

export default function SelectOrgPage() {
  const navigate = useNavigate()
  const [selectingId, setSelectingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Org list written to sessionStorage by LoginPage on multi-org login
  const orgs: TenantOrgInfo[] = (() => {
    try {
      const raw = sessionStorage.getItem('pendingOrgs')
      return raw ? (JSON.parse(raw) as TenantOrgInfo[]) : []
    } catch {
      return []
    }
  })()

  const handleSelect = async (org: TenantOrgInfo) => {
    setError(null)
    setSelectingId(org.id)
    try {
      await authApi.selectOrg({ tenant_id: org.id })
      sessionStorage.removeItem('pendingOrgs')
      navigate('/', { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Failed to select organization. Please try again.',
      )
      setSelectingId(null)
    }
  }

  // Edge case: no orgs in storage — user may have navigated here directly
  if (orgs.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <p className="text-muted-foreground mb-4">No organizations found. Please log in again.</p>
          <Button onClick={() => navigate('/login')}>Back to Login</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand mb-1">QUALISYS</h1>
          <p className="text-muted-foreground text-sm">AI-Powered Testing Platform</p>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-border p-8">
          <h2 className="text-xl font-semibold text-foreground mb-2">Select Organization</h2>
          <p className="text-sm text-muted-foreground mb-6">
            You're a member of multiple organizations. Choose which one to open.
          </p>

          {error && (
            <div
              role="alert"
              className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive"
              data-testid="select-org-error"
            >
              {error}
            </div>
          )}

          <ul className="space-y-3" data-testid="org-list">
            {orgs.map((org) => (
              <li
                key={org.id}
                className="flex items-center justify-between rounded-lg border border-border px-4 py-3 hover:bg-accent/40 transition-colors"
                data-testid={`org-item-${org.id}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="flex-shrink-0 h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center">
                    <Building2 className="h-4 w-4 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{org.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{org.slug}</p>
                  </div>
                  <RoleBadge role={org.role} />
                </div>

                <Button
                  size="sm"
                  className="ml-4 flex-shrink-0"
                  disabled={selectingId !== null}
                  onClick={() => handleSelect(org)}
                  data-testid={`select-org-btn-${org.id}`}
                >
                  {selectingId === org.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Open'
                  )}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
