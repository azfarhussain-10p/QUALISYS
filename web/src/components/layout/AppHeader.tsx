/**
 * App Header
 * Story: 1-5-login-session-management
 * AC8 — "Log Out" button
 * AC6 — Organization switcher dropdown for multi-org users
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LogOut, ChevronDown, Building2, Loader2, Settings, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { authApi, ApiError, TenantOrgInfo } from '@/lib/api'

interface AppHeaderProps {
  /** Currently active org name (shown in switcher) */
  currentOrgName?: string
  /** All orgs the user belongs to (for switcher) */
  orgs?: TenantOrgInfo[]
  /** Display name for the logged-in user (shown in user menu) */
  userName?: string
  /** Avatar URL for the logged-in user */
  avatarUrl?: string | null
}

export default function AppHeader({
  currentOrgName,
  orgs = [],
  userName,
  avatarUrl,
}: AppHeaderProps) {
  const navigate = useNavigate()
  const [logoutLoading, setLogoutLoading] = useState(false)
  const [switcherOpen, setSwitcherOpen] = useState(false)
  const [switchingId, setSwitchingId] = useState<string | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

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

          {/* Right actions — user avatar menu (AC1: Settings link) */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="flex items-center gap-2 text-muted-foreground"
                onClick={() => setUserMenuOpen((v) => !v)}
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                data-testid="user-menu-btn"
              >
                {avatarUrl ? (
                  <img
                    src={avatarUrl}
                    alt="avatar"
                    className="h-7 w-7 rounded-full object-cover"
                  />
                ) : (
                  <User className="h-4 w-4" />
                )}
                {userName && (
                  <span className="max-w-[120px] truncate text-sm">{userName}</span>
                )}
                <ChevronDown className="h-3 w-3" />
              </Button>

              {userMenuOpen && (
                <>
                  {/* Backdrop */}
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setUserMenuOpen(false)}
                    aria-hidden="true"
                  />
                  <ul
                    role="menu"
                    className="absolute right-0 top-full z-20 mt-1 min-w-[160px] rounded-md border border-border bg-white shadow-md py-1 text-sm"
                    data-testid="user-menu-dropdown"
                  >
                    <li role="none">
                      <button
                        type="button"
                        role="menuitem"
                        className="w-full text-left px-4 py-2 flex items-center gap-2 hover:bg-accent text-foreground"
                        onClick={() => {
                          setUserMenuOpen(false)
                          navigate('/settings/profile')
                        }}
                        data-testid="settings-link"
                      >
                        <Settings className="h-4 w-4 text-muted-foreground" />
                        Settings
                      </button>
                    </li>
                    <li role="none" className="border-t border-border my-1" />
                    <li role="none">
                      <button
                        type="button"
                        role="menuitem"
                        className="w-full text-left px-4 py-2 flex items-center gap-2 hover:bg-accent text-foreground"
                        disabled={logoutLoading}
                        onClick={handleLogout}
                        data-testid="logout-btn"
                      >
                        {logoutLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <LogOut className="h-4 w-4 text-muted-foreground" />
                        )}
                        Log out
                      </button>
                    </li>
                  </ul>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
