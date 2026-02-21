/**
 * Team Members Tab — Organization Settings
 * Story: 1-3-team-member-invitation — invite dialog, pending invitations list
 * Story: 1-4-user-management-remove-change-roles — active members list with role-change + remove
 * AC: AC1 — Invite Member dialog with email + role dropdown; bulk invite; RBAC
 * AC: AC6 — Pending invitations list with Resend/Revoke actions
 */

import { useState, useEffect, useCallback } from 'react'
import { Loader2, UserPlus, Mail, RotateCcw, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  invitationApi,
  InvitationResponse,
  ApiError,
} from '@/lib/api'
import ActiveMembersList from './ActiveMembersList'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TeamMembersTabProps {
  orgId: string
  orgName: string
  /** Current user's ID — passed to ActiveMembersList for self-action prevention */
  currentUserId: string
  /** Current user's role in this org — used for RBAC-based UI hiding. AC1/AC6 */
  userRole: string
}

type Role = 'pm-csm' | 'qa-manual' | 'qa-automation' | 'developer' | 'viewer'

const INVITEABLE_ROLES: { value: Role; label: string }[] = [
  { value: 'pm-csm', label: 'PM / CSM' },
  { value: 'qa-manual', label: 'QA — Manual' },
  { value: 'qa-automation', label: 'QA — Automation' },
  { value: 'developer', label: 'Developer' },
  { value: 'viewer', label: 'Viewer' },
]

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  expired: 'bg-red-100 text-red-700',
  accepted: 'bg-green-100 text-green-700',
  revoked: 'bg-gray-100 text-gray-500',
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseEmails(raw: string): string[] {
  return raw
    .split(/[\n,]+/)
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
}

function isOwnerOrAdmin(role: string): boolean {
  return role === 'owner' || role === 'admin'
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TeamMembersTab({ orgId, orgName, currentUserId, userRole }: TeamMembersTabProps) {
  const [invitations, setInvitations] = useState<InvitationResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)

  // Invite dialog state
  const [showInviteDialog, setShowInviteDialog] = useState(false)
  const [bulkEmails, setBulkEmails] = useState('')
  const [selectedRole, setSelectedRole] = useState<Role>('viewer')
  const [inviting, setInviting] = useState(false)
  const [inviteErrors, setInviteErrors] = useState<Array<{ email: string; reason: string }>>([])
  const [inviteSuccess, setInviteSuccess] = useState<string | null>(null)

  // Action states
  const [resendingId, setResendingId] = useState<string | null>(null)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Confirm dialog
  const [confirmRevoke, setConfirmRevoke] = useState<InvitationResponse | null>(null)

  const canManage = isOwnerOrAdmin(userRole)

  // Load pending/expired invitations
  const loadInvitations = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const data = await invitationApi.list(orgId)
      setInvitations(data)
    } catch (err) {
      setListError(err instanceof ApiError ? err.message : 'Failed to load invitations.')
    } finally {
      setLoading(false)
    }
  }, [orgId])

  useEffect(() => {
    loadInvitations()
  }, [loadInvitations])

  // ---------------------------------------------------------------------------
  // Invite submission — AC1 (bulk invite)
  // ---------------------------------------------------------------------------

  const handleInvite = useCallback(async () => {
    setInviteErrors([])
    setInviteSuccess(null)

    const emails = parseEmails(bulkEmails)
    if (emails.length === 0) return
    if (emails.length > 20) {
      setInviteErrors([{ email: '', reason: 'Maximum 20 invitations per batch.' }])
      return
    }

    // AC1: client-side duplicate check
    const unique = new Set(emails)
    if (unique.size !== emails.length) {
      setInviteErrors([{ email: '', reason: 'Duplicate email addresses in the list.' }])
      return
    }

    setInviting(true)
    try {
      const result = await invitationApi.create(orgId, {
        invitations: emails.map((email) => ({ email, role: selectedRole })),
      })
      setInviteErrors(result.errors)
      if (result.data.length > 0) {
        setInviteSuccess(
          `${result.data.length} invitation${result.data.length > 1 ? 's' : ''} sent successfully.`,
        )
        setBulkEmails('')
        await loadInvitations()
      }
    } catch (err) {
      setInviteErrors([
        { email: '', reason: err instanceof ApiError ? err.message : 'Failed to send invitations.' },
      ])
    } finally {
      setInviting(false)
    }
  }, [orgId, bulkEmails, selectedRole, loadInvitations])

  // ---------------------------------------------------------------------------
  // Resend — AC6
  // ---------------------------------------------------------------------------

  const handleResend = useCallback(
    async (inv: InvitationResponse) => {
      setActionError(null)
      setResendingId(inv.id)
      try {
        await invitationApi.resend(orgId, inv.id)
        await loadInvitations()
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Failed to resend invitation.')
      } finally {
        setResendingId(null)
      }
    },
    [orgId, loadInvitations],
  )

  // ---------------------------------------------------------------------------
  // Revoke — AC6
  // ---------------------------------------------------------------------------

  const handleRevoke = useCallback(
    async (inv: InvitationResponse) => {
      setActionError(null)
      setRevokingId(inv.id)
      setConfirmRevoke(null)
      try {
        await invitationApi.revoke(orgId, inv.id)
        setInvitations((prev) => prev.filter((i) => i.id !== inv.id))
      } catch (err) {
        setActionError(err instanceof ApiError ? err.message : 'Failed to revoke invitation.')
      } finally {
        setRevokingId(null)
      }
    },
    [orgId],
  )

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div data-testid="team-members-tab">
      {/* Header + Invite button — AC1: hidden for non-Owner/Admin (AC7) */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Team Members</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your organization's members and pending invitations.
          </p>
        </div>
        {canManage && (
          <Button
            onClick={() => {
              setShowInviteDialog(true)
              setInviteErrors([])
              setInviteSuccess(null)
            }}
            data-testid="invite-member-btn"
          >
            <UserPlus className="mr-2 h-4 w-4" />
            Invite Member
          </Button>
        )}
      </div>

      {/* Invite dialog — AC1, AC3 */}
      {showInviteDialog && canManage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          data-testid="invite-dialog"
        >
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold mb-4">Invite Team Members</h3>

            <div className="mb-4">
              <Label htmlFor="invite-emails">
                Email addresses
                <span className="ml-1 text-muted-foreground font-normal text-xs">
                  (comma or newline-separated, max 20)
                </span>
              </Label>
              <textarea
                id="invite-emails"
                rows={4}
                className="mt-1 flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                placeholder="alice@example.com, bob@example.com"
                value={bulkEmails}
                onChange={(e) => setBulkEmails(e.target.value)}
                data-testid="bulk-email-input"
              />
            </div>

            <div className="mb-6">
              <Label htmlFor="invite-role">Role</Label>
              <select
                id="invite-role"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value as Role)}
                data-testid="role-select"
              >
                {INVITEABLE_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-muted-foreground">
                Owner and Admin roles cannot be assigned via invitation.
              </p>
            </div>

            {inviteSuccess && (
              <p role="status" className="mb-3 text-sm text-green-700" data-testid="invite-success">
                {inviteSuccess}
              </p>
            )}

            {inviteErrors.length > 0 && (
              <div role="alert" className="mb-3 space-y-1" data-testid="invite-errors">
                {inviteErrors.map((e, i) => (
                  <p key={i} className="text-sm text-destructive">
                    {e.email ? `${e.email}: ` : ''}
                    {e.reason}
                  </p>
                ))}
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => setShowInviteDialog(false)}
                disabled={inviting}
                data-testid="cancel-invite-btn"
              >
                Cancel
              </Button>
              <Button
                onClick={handleInvite}
                disabled={inviting || !bulkEmails.trim()}
                data-testid="send-invite-btn"
              >
                {inviting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Sending…
                  </>
                ) : (
                  <>
                    <Mail className="mr-2 h-4 w-4" />
                    Send Invitations
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Pending invitations list — AC6 */}
      <div className="bg-white rounded-lg shadow-sm border border-border">
        <div className="px-6 py-4 border-b border-border">
          <h3 className="text-sm font-semibold text-foreground">Pending Invitations</h3>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12" data-testid="invitations-loading">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
          </div>
        ) : listError ? (
          <div role="alert" className="px-6 py-4 text-sm text-destructive" data-testid="list-error">
            {listError}
          </div>
        ) : invitations.length === 0 ? (
          <div
            className="px-6 py-12 text-center text-sm text-muted-foreground"
            data-testid="no-invitations"
          >
            No pending invitations.
          </div>
        ) : (
          <table className="w-full text-sm" data-testid="invitations-table">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground uppercase tracking-wide">
                <th className="px-6 py-3">Email</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Sent</th>
                <th className="px-6 py-3">Expires</th>
                <th className="px-6 py-3">Status</th>
                {canManage && <th className="px-6 py-3">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {invitations.map((inv) => (
                <tr key={inv.id} className="border-b border-border last:border-0">
                  <td className="px-6 py-3 font-medium">{inv.email}</td>
                  <td className="px-6 py-3 capitalize">{inv.role}</td>
                  <td className="px-6 py-3 text-muted-foreground">
                    {new Date(inv.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 text-muted-foreground">
                    {new Date(inv.expires_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_BADGE[inv.status] ?? 'bg-gray-100 text-gray-600'}`}
                    >
                      {inv.status}
                    </span>
                  </td>
                  {canManage && (
                    <td className="px-6 py-3">
                      <div className="flex gap-2">
                        {/* Resend — available for expired (AC6) */}
                        {inv.status === 'expired' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleResend(inv)}
                            disabled={resendingId === inv.id}
                            data-testid={`resend-btn-${inv.id}`}
                          >
                            {resendingId === inv.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <RotateCcw className="h-3 w-3" />
                            )}
                            <span className="ml-1">Resend</span>
                          </Button>
                        )}
                        {/* Revoke — available for pending (AC6) */}
                        {inv.status === 'pending' && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-destructive border-destructive/40 hover:bg-destructive/10"
                            onClick={() => setConfirmRevoke(inv)}
                            disabled={revokingId === inv.id}
                            data-testid={`revoke-btn-${inv.id}`}
                          >
                            {revokingId === inv.id ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <XCircle className="h-3 w-3" />
                            )}
                            <span className="ml-1">Revoke</span>
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {actionError && (
        <p role="alert" className="mt-3 text-sm text-destructive" data-testid="action-error">
          {actionError}
        </p>
      )}

      {/* Revoke confirmation dialog — AC6 */}
      {confirmRevoke && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-sm mx-4 p-6" data-testid="revoke-confirm-dialog">
            <h3 className="text-lg font-semibold mb-2">Revoke Invitation</h3>
            <p className="text-sm text-muted-foreground mb-6">
              Are you sure you want to revoke the invitation for{' '}
              <strong>{confirmRevoke.email}</strong>? They will no longer be able to use this invitation link.
            </p>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setConfirmRevoke(null)} data-testid="cancel-revoke-btn">
                Cancel
              </Button>
              <Button
                variant="outline"
                className="text-destructive border-destructive/40 hover:bg-destructive/10"
                onClick={() => handleRevoke(confirmRevoke)}
                data-testid="confirm-revoke-btn"
              >
                Revoke
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Active members list with role-change + remove actions — Story 1.4 */}
      <div className="mt-8">
        <ActiveMembersList
          orgId={orgId}
          orgName={orgName}
          currentUserId={currentUserId}
          currentUserRole={userRole}
        />
      </div>
    </div>
  )
}
