/**
 * App Header
 * Story: 1-5-login-session-management
 * AC8 — "Log Out" button
 * AC6 — Organization switcher dropdown for multi-org users
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, ChevronDown, Building2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError, TenantOrgInfo } from '@/lib/api'

interface AppHeaderProps {
  /** Currently active org name (shown in switcher) */
  currentOrgName?: string
  /** All orgs the user belongs to (for switcher) */
  orgs?: TenantOrgInfo[]
}

export default function AppHeader({ currentOrgName, orgs = [] }: AppHeaderProps) {
  const navigate = useNavigate()
  const [logoutLoading, setLogoutLoading] = useState(false)
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const [switchingId, setSwitchingId] = useState<string | null>(null)

  // AC8: Logout current session
  const handleLogout = async () => {
    setLogoutLoading(true)
    try {
      await authApi.logout()
    } catch {
      // Ignore errors — redirect to login regardless
    } finally {
      navigate('/login', { replace: true })
    }
  }

  // AC6: Switch active organization
  const handleSwitchOrg = async (org: TenantOrgInfo) => {
    setSwitcherOpen(false)
    setSwitchingId(org.id)
    try {
      await authApi.switchOrg({ tenant_id: org.id })
      // Force full reload so all org-scoped data refreshes
      window.location.reload()
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : 'Failed to switch organization.'
      alert(msg)
      setSwitchingId(null)
    }
  }

  const showSwitcher = orgs.length > 1

  return (
    <header className="border-b border-border bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-14 items-center justify-between">
          {/* Brand + Org switcher */}
          <div className="flex items-center gap-4">
            <a href="/" className="text-lg font-bold text-brand">
              QUALISYS
            </a>

            {/* Org switcher — AC6 */}
            {showSwitcher && currentOrgName && (
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  className="flex items-center gap-1 text-sm"
                  onClick={() => setSwitcherOpen((v) => !v)}
                  aria-haspopup="listbox"
                  aria-expanded={switcherOpen}
                  data-testid="org-switcher-btn"
                >
                  <Building2 className="h-4 w-4 text-muted-foreground" />
                  <span className="max-w-[180px] truncate">{currentOrgName}</span>
                  {switchingId ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <ChevronDown className="h-3 w-3 text-muted-foreground" />
                  )}
                </Button>

                {switcherOpen && (
                  <>
                    {/* Backdrop */}
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setSwitcherOpen(false)}
                      aria-hidden="true"
                    />
                    <ul
                      role="listbox"
                      className="absolute left-0 top-full z-20 mt-1 min-w-[200px] rounded-md border border-border bg-white shadow-md py-1"
                      data-testid="org-switcher-dropdown"
                    >
                      {orgs.map((org) => (
                        <li key={org.id} role="option" aria-selected={org.name === currentOrgName}>
                          <button
                            type="button"
                            className={`w-full text-left px-4 py-2 text-sm hover:bg-accent flex items-center gap-2 ${
                              org.name === currentOrgName
                                ? 'font-medium text-primary'
                                : 'text-foreground'
                            }`}
                            onClick={() => handleSwitchOrg(org)}
                            disabled={switchingId !== null}
                            data-testid={`switch-org-${org.id}`}
                          >
                            <Building2 className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                            <span className="truncate">{org.name}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            )}
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              disabled={logoutLoading}
              onClick={handleLogout}
              data-testid="logout-btn"
            >
              {logoutLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <LogOut className="mr-1.5 h-4 w-4" />
                  Log out
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}
