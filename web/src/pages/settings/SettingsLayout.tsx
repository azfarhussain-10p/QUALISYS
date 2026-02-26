/**
 * Settings Layout
 * Story: 1-8-profile-notification-preferences
 * AC1 — tabbed settings layout (Profile, Security, Notifications)
 */

import { NavLink, Outlet, Navigate } from 'react-router-dom'

const TABS = [
  { label: 'Profile', path: '/settings/profile' },
  { label: 'Security', path: '/settings/security' },
  { label: 'Notifications', path: '/settings/notifications' },
]

export default function SettingsLayout() {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <h1 className="text-2xl font-semibold mb-8" data-testid="settings-heading">
          Settings
        </h1>

        <div className="flex gap-10">
          {/* Sidebar nav */}
          <nav className="w-44 shrink-0" aria-label="Settings navigation">
            <ul className="space-y-1" role="list">
              {TABS.map((tab) => (
                <li key={tab.path}>
                  <NavLink
                    to={tab.path}
                    className={({ isActive }) =>
                      `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                        isActive
                          ? 'bg-secondary text-foreground'
                          : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                      }`
                    }
                    data-testid={`settings-tab-${tab.label.toLowerCase()}`}
                  >
                    {tab.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {/* Tab content */}
          <main className="flex-1 min-w-0">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
