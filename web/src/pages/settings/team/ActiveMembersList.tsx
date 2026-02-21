/**
 * Active Members List with role-change and remove actions.
 * Story: 1-4-user-management-remove-change-roles
 * AC1 — paginated member list with search
 * AC2 — change-role dropdown with confirmation dialog
 * AC3 — remove with destructive confirmation dialog
 * AC6 — last-admin guard (disabled buttons + tooltip)
 * RBAC — action buttons hidden for non-Owner/Admin
 */

import { useState, useEffect, useCallback } from 'react'
import { Loader2, Shield, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  memberApi,
  MemberResponse,
  ApiError,
} from '@/lib/api'

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_ROLES: { value: string; label: string }[] = [
  { value: 'owner', label: 'Owner' },
  { value: 'admin', label: 'Admin' },
  { value: 'pm-csm', label: 'PM / CSM' },
  { value: 'qa-manual', label: 'QA — Manual' },
  { value: 'qa-automation', label: 'QA — Automation' },
  { value: 'developer', label: 'Developer' },
  { value: 'viewer', label: 'Viewer' },
]

function roleLabel(value: string): string {
  return ALL_ROLES.find((r) => r.value === value)?.label ?? value
}

function isOwnerOrAdmin(role: string): boolean {
  return role === 'owner' || role === 'admin'
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ActiveMembersListProps {
  orgId: string
  orgName: string
  /** Authenticated user's ID — used to disable self-action buttons (AC2/AC3) */
  currentUserId: string
  /** Authenticated user's role — used to control RBAC visibility (AC1) */
  currentUserRole: string
}

// ---------------------------------------------------------------------------
// Dialogs
// ---------------------------------------------------------------------------

interface ChangeRoleDialogProps {
  member: MemberResponse
  onConfirm: (newRole: string) => void
  onCancel: () => void
  saving: boolean
}

function ChangeRoleDialog({ member, onConfirm, onCancel, saving }: ChangeRoleDialogProps) {
  const [newRole, setNewRole] = useState(member.role)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" data-testid="change-role-dialog">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
        <h3 className="text-lg font-semibold mb-2">Change Role</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Change <strong>{member.full_name}</strong>'s role:
        </p>
        <div className="mb-2 text-xs text-muted-foreground">
          Current: <span className="font-medium">{roleLabel(member.role)}</span>
        </div>
        <select
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm mb-6 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          value={newRole}
          onChange={(e) => setNewRole(e.target.value)}
          data-testid="new-role-select"
        >
          {ALL_ROLES.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={onCancel} disabled={saving} data-testid="cancel-role-change-btn">
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(newRole)}
            disabled={saving || newRole === member.role}
            data-testid="confirm-role-change-btn"
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Confirm Change
          </Button>
        </div>
      </div>
    </div>
  )
}

interface RemoveDialogProps {
  member: MemberResponse
  orgName: string
  onConfirm: () => void
  onCancel: () => void
  removing: boolean
}

function RemoveDialog({ member, orgName, onConfirm, onCancel, removing }: RemoveDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" data-testid="remove-member-dialog">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-6">
        <h3 className="text-lg font-semibold mb-2">Remove Member</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Remove <strong>{member.full_name}</strong> from <strong>{orgName}</strong>?
        </p>
        <div className="bg-red-50 border border-red-200 rounded-md p-3 mb-6 text-sm text-red-700">
          This will revoke their access to all projects in this organization. Their account will remain active.
        </div>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={onCancel} disabled={removing} data-testid="cancel-remove-btn">
            Cancel
          </Button>
          <Button
            variant="outline"
            className="text-destructive border-destructive/40 hover:bg-destructive/10"
            onClick={onConfirm}
            disabled={removing}
            data-testid="confirm-remove-btn"
          >
            {removing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
            Remove
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ActiveMembersList({
  orgId,
  orgName,
  currentUserId,
  currentUserRole,
}: ActiveMembersListProps) {
  const canManage = isOwnerOrAdmin(currentUserRole)

  // List state
  const [members, setMembers] = useState<MemberResponse[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  // Dialog state
  const [changeRoleTarget, setChangeRoleTarget] = useState<MemberResponse | null>(null)
  const [removeTarget, setRemoveTarget] = useState<MemberResponse | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [savingRole, setSavingRole] = useState(false)
  const [removing, setRemoving] = useState(false)

  const PER_PAGE = 25
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE))

  // ---------------------------------------------------------------------------
  // Data loading (AC1)
  // ---------------------------------------------------------------------------

  const loadMembers = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const data = await memberApi.list(orgId, { page, per_page: PER_PAGE, q: search || undefined })
      setMembers(data.members)
      setTotal(data.total)
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : 'Failed to load members.')
    } finally {
      setLoading(false)
    }
  }, [orgId, page, search])

  useEffect(() => {
    loadMembers()
  }, [loadMembers])

  // Debounced search: commit on Enter or blur
  const commitSearch = useCallback(() => {
    setSearch(searchInput)
    setPage(1)
  }, [searchInput])

  // ---------------------------------------------------------------------------
  // Change role (AC2)
  // ---------------------------------------------------------------------------

  const handleChangeRole = useCallback(
    async (member: MemberResponse, newRole: string) => {
      setActionError(null)
      setSavingRole(true)
      try {
        const updated = await memberApi.changeRole(orgId, member.user_id, { role: newRole })
        // Optimistic update in list
        setMembers((prev) => prev.map((m) => (m.user_id === updated.user_id ? updated : m)))
        setChangeRoleTarget(null)
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Failed to change role.')
        setChangeRoleTarget(null)
      } finally {
        setSavingRole(false)
      }
    },
    [orgId],
  )

  // ---------------------------------------------------------------------------
  // Remove member (AC3)
  // ---------------------------------------------------------------------------

  const handleRemoveMember = useCallback(
    async (member: MemberResponse) => {
      setActionError(null)
      setRemoving(true)
      try {
        await memberApi.removeMember(orgId, member.user_id)
        setMembers((prev) => prev.filter((m) => m.user_id !== member.user_id))
        setTotal((t) => t - 1)
        setRemoveTarget(null)
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Failed to remove member.')
        setRemoveTarget(null)
      } finally {
        setRemoving(false)
      }
    },
    [orgId],
  )

  // ---------------------------------------------------------------------------
  // Helper: is the given member the last active Owner/Admin?
  // Used for last-admin guard tooltip. (AC6)
  // ---------------------------------------------------------------------------

  const isLastAdmin = useCallback(
    (member: MemberResponse): boolean => {
      if (!isOwnerOrAdmin(member.role)) return false
      const adminCount = members.filter((m) => isOwnerOrAdmin(m.role) && m.is_active).length
      return adminCount <= 1
    },
    [members],
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div data-testid="active-members-list">
      {/* Search + header (AC1) */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-foreground">Active Members</h3>
        <div className="flex gap-2">
          <Input
            placeholder="Search name or email…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && commitSearch()}
            onBlur={commitSearch}
            className="w-56 h-8 text-sm"
            data-testid="member-search-input"
          />
        </div>
      </div>

      {/* Members table */}
      <div className="bg-white rounded-lg shadow-sm border border-border">
        {loading ? (
          <div className="flex items-center justify-center py-12" data-testid="members-loading">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : listError ? (
          <div role="alert" className="px-6 py-4 text-sm text-destructive" data-testid="members-error">
            {listError}
          </div>
        ) : members.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-muted-foreground" data-testid="no-members">
            No active members found.
          </div>
        ) : (
          <table className="w-full text-sm" data-testid="members-table">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wide">
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Email</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Joined</th>
                {canManage && <th className="px-6 py-3">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {members.map((member) => {
                const isSelf = member.user_id === currentUserId
                const lastAdmin = isLastAdmin(member)
                const actionsDisabledReason = isSelf
                  ? 'You cannot modify your own membership.'
                  : lastAdmin
                  ? 'Transfer ownership first.'
                  : null

                return (
                  <tr key={member.user_id} className="border-b border-border last:border-0" data-testid={`member-row-${member.user_id}`}>
                    <td className="px-6 py-3 font-medium">
                      {member.full_name}
                      {isSelf && (
                        <span className="ml-2 text-xs text-muted-foreground">(you)</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-muted-foreground">{member.email}</td>
                    <td className="px-6 py-3">
                      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                        {isOwnerOrAdmin(member.role) && <Shield className="h-3 w-3" />}
                        {roleLabel(member.role)}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-muted-foreground text-xs">
                      {new Date(member.joined_at).toLocaleDateString()}
                    </td>
                    {canManage && (
                      <td className="px-6 py-3">
                        <div className="flex gap-2">
                          {/* Change role button (AC2) */}
                          <div title={actionsDisabledReason ?? undefined}>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setChangeRoleTarget(member)}
                              disabled={!!actionsDisabledReason}
                              data-testid={`change-role-btn-${member.user_id}`}
                            >
                              Change Role
                            </Button>
                          </div>
                          {/* Remove button (AC3) */}
                          <div title={actionsDisabledReason ?? undefined}>
                            <Button
                              size="sm"
                              variant="outline"
                              className="text-destructive border-destructive/40 hover:bg-destructive/10"
                              onClick={() => setRemoveTarget(member)}
                              disabled={!!actionsDisabledReason}
                              data-testid={`remove-btn-${member.user_id}`}
                            >
                              <Trash2 className="h-3 w-3 mr-1" />
                              Remove
                            </Button>
                          </div>
                        </div>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination (AC1) */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 text-sm text-muted-foreground">
          <span>
            Page {page} of {totalPages} ({total} members)
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              data-testid="prev-page-btn"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              data-testid="next-page-btn"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Action error (AC2/AC3) */}
      {actionError && (
        <p role="alert" className="mt-3 text-sm text-destructive" data-testid="member-action-error">
          {actionError}
        </p>
      )}

      {/* Change role dialog (AC2) */}
      {changeRoleTarget && (
        <ChangeRoleDialog
          member={changeRoleTarget}
          onConfirm={(newRole) => handleChangeRole(changeRoleTarget, newRole)}
          onCancel={() => setChangeRoleTarget(null)}
          saving={savingRole}
        />
      )}

      {/* Remove confirmation dialog (AC3) */}
      {removeTarget && (
        <RemoveDialog
          member={removeTarget}
          orgName={orgName}
          onConfirm={() => handleRemoveMember(removeTarget)}
          onCancel={() => setRemoveTarget(null)}
          removing={removing}
        />
      )}
    </div>
  )
}
