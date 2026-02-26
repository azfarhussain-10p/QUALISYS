/**
 * QUALISYS API Client
 * Story: 1-1-user-account-creation, 1-5-login-session-management
 * AC: AC8 — structured error responses { error: { code, message } }
 * AC (1.5): AC4 — automatic refresh token rotation on 401
 */

import axios, { AxiosError } from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: true,  // send httpOnly cookies automatically
  headers: { 'Content-Type': 'application/json' },
})

// ---------------------------------------------------------------------------
// Refresh interceptor — AC4: transparent token rotation on expired access token
// ---------------------------------------------------------------------------
let _isRefreshing = false
const _pendingQueue: Array<{ resolve: () => void; reject: (err: unknown) => void }> = []

const _processQueue = (error: unknown) => {
  _pendingQueue.forEach((p) => (error ? p.reject(error) : p.resolve()))
  _pendingQueue.length = 0
}

type RetryableConfig = NonNullable<AxiosError['config']> & { _retry?: boolean }

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ error?: { code: string; message: string }; detail?: unknown }>) => {
    const cfg = error.config as RetryableConfig | undefined

    // Auto-refresh on 401 when not already retrying and not an auth endpoint itself
    if (
      error.response?.status === 401 &&
      !cfg?._retry &&
      !cfg?.url?.includes('/auth/login') &&
      !cfg?.url?.includes('/auth/refresh')
    ) {
      if (_isRefreshing) {
        // Queue additional requests while refresh is in flight
        return new Promise<void>((resolve, reject) => {
          _pendingQueue.push({ resolve, reject })
        }).then(() => (cfg ? apiClient(cfg) : Promise.reject(error)))
      }

      if (cfg) cfg._retry = true
      _isRefreshing = true

      try {
        await apiClient.post('/api/v1/auth/refresh')
        _processQueue(null)
        _isRefreshing = false
        return cfg ? apiClient(cfg) : Promise.reject(error)
      } catch (refreshErr) {
        _processQueue(refreshErr)
        _isRefreshing = false
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      }
    }

    // Normalize structured API errors
    const apiError = error.response?.data?.error
    if (apiError) {
      return Promise.reject(new ApiError(apiError.code, apiError.message, error.response?.status))
    }
    return Promise.reject(error)
  },
)

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export interface RegisterPayload {
  email: string
  password: string
  full_name: string
}

export interface UserResponse {
  id: string
  email: string
  full_name: string
  email_verified: boolean
  auth_provider: string
  avatar_url: string | null
  created_at: string
}

export interface AuthTokens {
  user: UserResponse
  access_token: string
  refresh_token: string
  token_type: string
}

// ---------------------------------------------------------------------------
// Story 1.5 — Login & Session types
// ---------------------------------------------------------------------------

export interface LoginPayload {
  email: string
  password: string
  remember_me?: boolean
}

export interface TenantOrgInfo {
  id: string
  name: string
  slug: string
  role: string
}

export interface LoginResponse {
  user: UserResponse
  orgs: TenantOrgInfo[]
  has_multiple_orgs: boolean
}

export interface MFAChallengeResponse {
  mfa_required: true
  mfa_token: string
}

export type LoginOrMFAResponse = LoginResponse | MFAChallengeResponse

export interface SessionInfo {
  session_id: string
  ip: string | null
  user_agent: string | null
  device_name: string | null
  created_at: string
  is_current: boolean
  remember_me: boolean
  tenant_id: string | null
}

export interface SessionListResponse {
  sessions: SessionInfo[]
}

export interface SelectOrgPayload {
  tenant_id: string
}

// ---------------------------------------------------------------------------

export const authApi = {
  register: (payload: RegisterPayload) =>
    apiClient.post<AuthTokens>('/api/v1/auth/register', payload).then((r) => r.data),

  verifyEmail: (token: string) =>
    apiClient
      .post<{ success: boolean; message: string }>('/api/v1/auth/verify-email', { token })
      .then((r) => r.data),

  resendVerification: (email: string) =>
    apiClient
      .post<{ success: boolean; message: string }>('/api/v1/auth/resend-verification', { email })
      .then((r) => r.data),

  googleAuthorize: () => {
    window.location.href = `${apiClient.defaults.baseURL}/api/v1/auth/oauth/google/authorize`
  },

  // Story 1.5 endpoints

  login: (payload: LoginPayload) =>
    apiClient.post<LoginOrMFAResponse>('/api/v1/auth/login', payload).then((r) => r.data),

  refresh: () =>
    apiClient.post<{ success: boolean }>('/api/v1/auth/refresh').then((r) => r.data),

  logout: () =>
    apiClient.post<{ success: boolean }>('/api/v1/auth/logout').then((r) => r.data),

  logoutAll: () =>
    apiClient.post<{ success: boolean }>('/api/v1/auth/logout-all').then((r) => r.data),

  getSessions: () =>
    apiClient.get<SessionListResponse>('/api/v1/auth/sessions').then((r) => r.data),

  revokeSession: (sessionId: string) =>
    apiClient.delete(`/api/v1/auth/sessions/${sessionId}`).then(() => undefined),

  selectOrg: (payload: SelectOrgPayload) =>
    apiClient.post<LoginResponse>('/api/v1/auth/select-org', payload).then((r) => r.data),

  switchOrg: (payload: SelectOrgPayload) =>
    apiClient.post<LoginResponse>('/api/v1/auth/switch-org', payload).then((r) => r.data),

  // Story 1.7 — MFA

  mfaSetup: () =>
    apiClient.post<{ qr_uri: string; secret: string; setup_token: string }>('/api/v1/auth/mfa/setup').then((r) => r.data),

  mfaSetupConfirm: (setup_token: string, totp_code: string) =>
    apiClient
      .post<{ backup_codes: string[]; message: string }>('/api/v1/auth/mfa/setup/confirm', { setup_token, totp_code })
      .then((r) => r.data),

  mfaVerify: (mfa_token: string, totp_code: string) =>
    apiClient
      .post<LoginResponse>('/api/v1/auth/mfa/verify', { mfa_token, totp_code })
      .then((r) => r.data),

  mfaBackup: (mfa_token: string, backup_code: string) =>
    apiClient
      .post<LoginResponse>('/api/v1/auth/mfa/backup', { mfa_token, backup_code })
      .then((r) => r.data),

  mfaDisable: (password: string) =>
    apiClient
      .post<{ success: boolean; message: string }>('/api/v1/auth/mfa/disable', { password })
      .then((r) => r.data),

  mfaRegenerateCodes: (password: string) =>
    apiClient
      .post<{ backup_codes: string[]; message: string }>('/api/v1/auth/mfa/backup-codes/regenerate', { password })
      .then((r) => r.data),

  mfaStatus: () =>
    apiClient
      .get<{ enabled: boolean; enabled_at: string | null; backup_codes_remaining: number }>('/api/v1/auth/mfa/status')
      .then((r) => r.data),

  // Story 1.6 — Password reset

  forgotPassword: (email: string) =>
    apiClient
      .post<{ success: boolean; message: string }>('/api/v1/auth/forgot-password', { email })
      .then((r) => r.data),

  validateResetToken: (token: string) =>
    apiClient
      .get<{ valid: boolean; email?: string; error?: string }>('/api/v1/auth/reset-password', {
        params: { token },
      })
      .then((r) => r.data),

  resetPassword: (token: string, new_password: string) =>
    apiClient
      .post<{ success: boolean; message: string }>('/api/v1/auth/reset-password', {
        token,
        new_password,
      })
      .then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Org endpoints — Story 1.2
// ---------------------------------------------------------------------------

export interface OrgResponse {
  id: string
  name: string
  slug: string
  logo_url: string | null
  custom_domain: string | null
  data_retention_days: number
  plan: string
  settings: Record<string, unknown>
  created_by: string | null
  created_at: string
  updated_at: string
  provisioning_status: string | null
}

export interface CreateOrgPayload {
  name: string
  slug?: string
  logo_url?: string
  custom_domain?: string
}

export interface UpdateOrgSettingsPayload {
  name?: string
  slug?: string
  logo_url?: string
  custom_domain?: string
  data_retention_days?: number
  settings?: Record<string, unknown>
}

export interface CreateOrgResponse {
  org: OrgResponse
  schema_name: string
  provisioning_status: string
}

export interface PresignedUrlResponse {
  upload_url: string
  key: string
  fields: Record<string, string>
  expires_in_seconds: number
}

// ---------------------------------------------------------------------------
// Invitation types — Story 1.3
// ---------------------------------------------------------------------------

export interface InvitationResponse {
  id: string
  email: string
  role: string
  status: string
  expires_at: string
  created_at: string
  accepted_at: string | null
}

export interface InviteItemPayload {
  email: string
  role: string
}

export interface BulkInvitePayload {
  invitations: InviteItemPayload[]
}

export interface BulkInviteResponse {
  data: InvitationResponse[]
  errors: Array<{ email: string; reason: string }>
}

export interface AcceptInviteDetailsResponse {
  org_name: string
  role: string
  email: string
  user_exists: boolean
  expires_at: string
}

export interface AcceptInvitePayload {
  token: string
  full_name?: string
  password?: string
}

export interface AcceptInviteResponse {
  user_id: string
  org_id: string
  role: string
  access_token?: string
  refresh_token?: string
  token_type: string
}

export const invitationApi = {
  create: (orgId: string, payload: BulkInvitePayload) =>
    apiClient
      .post<BulkInviteResponse>(`/api/v1/orgs/${orgId}/invitations`, payload)
      .then((r) => r.data),

  list: (orgId: string, statusFilter?: string) =>
    apiClient
      .get<InvitationResponse[]>(`/api/v1/orgs/${orgId}/invitations`, {
        params: statusFilter ? { status: statusFilter } : undefined,
      })
      .then((r) => r.data),

  revoke: (orgId: string, inviteId: string) =>
    apiClient
      .delete(`/api/v1/orgs/${orgId}/invitations/${inviteId}`)
      .then(() => undefined),

  resend: (orgId: string, inviteId: string) =>
    apiClient
      .post<InvitationResponse>(`/api/v1/orgs/${orgId}/invitations/${inviteId}/resend`)
      .then((r) => r.data),

  getAcceptDetails: (token: string) =>
    apiClient
      .get<AcceptInviteDetailsResponse>(`/api/v1/invitations/${encodeURIComponent(token)}`)
      .then((r) => r.data),

  accept: (payload: AcceptInvitePayload, accessToken?: string) =>
    apiClient
      .post<AcceptInviteResponse>('/api/v1/invitations/accept', payload, {
        headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
      })
      .then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Member management types + endpoints — Story 1.4
// ---------------------------------------------------------------------------

export interface MemberResponse {
  user_id: string
  email: string
  full_name: string
  role: string
  joined_at: string
  is_active: boolean
}

export interface PaginatedMembersResponse {
  members: MemberResponse[]
  total: number
  page: number
  per_page: number
}

export interface ChangeRolePayload {
  role: string
}

export interface RemoveMemberResponse {
  message: string
  removed_at: string
}

export const memberApi = {
  list: (orgId: string, params?: { page?: number; per_page?: number; q?: string }) =>
    apiClient
      .get<PaginatedMembersResponse>(`/api/v1/orgs/${orgId}/members`, { params })
      .then((r) => r.data),

  changeRole: (orgId: string, userId: string, payload: ChangeRolePayload) =>
    apiClient
      .patch<MemberResponse>(`/api/v1/orgs/${orgId}/members/${userId}/role`, payload)
      .then((r) => r.data),

  removeMember: (orgId: string, userId: string) =>
    apiClient
      .delete<RemoveMemberResponse>(`/api/v1/orgs/${orgId}/members/${userId}`)
      .then((r) => r.data),
}

// ---------------------------------------------------------------------------
// Org endpoints — Story 1.2
// ---------------------------------------------------------------------------

export const orgApi = {
  create: (payload: CreateOrgPayload) =>
    apiClient.post<CreateOrgResponse>('/api/v1/orgs', payload).then((r) => r.data),

  getSettings: (orgId: string) =>
    apiClient.get<OrgResponse>(`/api/v1/orgs/${orgId}/settings`).then((r) => r.data),

  updateSettings: (orgId: string, payload: UpdateOrgSettingsPayload) =>
    apiClient.patch<OrgResponse>(`/api/v1/orgs/${orgId}/settings`, payload).then((r) => r.data),

  getLogoPresignedUrl: (
    orgId: string,
    payload: { filename: string; content_type: string; file_size: number },
  ) =>
    apiClient
      .post<PresignedUrlResponse>(`/api/v1/orgs/${orgId}/logo/presigned-url`, payload)
      .then((r) => r.data),

  getProvisioningStatus: (orgId: string) =>
    apiClient
      .get<{ org_id: string; status: string; schema_exists: boolean }>(
        `/api/v1/orgs/${orgId}/provisioning-status`,
      )
      .then((r) => r.data),
}

// ---------------------------------------------------------------------------
// User Profile & Notifications — Story 1.8
// ---------------------------------------------------------------------------

export interface UserProfileResponse {
  id: string
  email: string
  full_name: string
  avatar_url: string | null
  timezone: string
  auth_provider: string
  email_verified: boolean
  created_at: string
  org_role: string | null  // Current tenant role (owner/admin/etc.)
}

export interface UpdateProfilePayload {
  full_name?: string
  timezone?: string
}

export interface AvatarPresignedUrlPayload {
  filename: string
  content_type: string
  file_size: number
}

export interface AvatarPresignedUrlResponse {
  upload_url: string
  key: string
  expires_in_seconds: number
}

export interface NotificationPreferences {
  email_test_completions: boolean
  email_test_failures: boolean
  email_team_changes: boolean
  email_security_alerts: boolean
  email_frequency: 'realtime' | 'daily' | 'weekly'
  digest_time: string   // "HH:MM"
  digest_day: string
}

export interface ChangePasswordPayload {
  current_password: string
  new_password: string
  confirm_new_password: string
}

// ---------------------------------------------------------------------------
// Project types + endpoints — Story 1.9
// ---------------------------------------------------------------------------

export interface ProjectResponse {
  id: string
  name: string
  slug: string
  description: string | null
  app_url: string | null
  github_repo_url: string | null
  status: string
  settings: Record<string, unknown>
  is_active: boolean
  created_by: string | null
  tenant_id: string
  organization_id: string | null
  created_at: string
  updated_at: string
}

// Story 1.11 — Extended project list item with member_count and health
export interface ProjectListItem extends ProjectResponse {
  member_count: number
  health: string  // '—' placeholder in Epic 1
}

export interface PaginationMeta {
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface PaginatedProjectsResponse {
  data: ProjectListItem[]
  pagination: PaginationMeta
}

// Story 1.11 — List query params
export interface ListProjectsParams {
  status?: 'active' | 'archived' | 'all'
  search?: string
  sort?: 'name' | 'created_at' | 'status'
  page?: number
  per_page?: number
}

export interface CreateProjectPayload {
  name: string
  description?: string
  app_url?: string
  github_repo_url?: string
}

export interface UpdateProjectPayload {
  name?: string
  description?: string
  app_url?: string
  github_repo_url?: string
  settings?: Record<string, unknown>
}

export interface ProjectSettingsResponse {
  id: string
  name: string
  slug: string
  description: string | null
  app_url: string | null
  github_repo_url: string | null
  default_environment: string | null
  default_browser: string | null
  tags: string[]
}

// ---------------------------------------------------------------------------
// Project member types + endpoints — Story 1.10
// ---------------------------------------------------------------------------

export interface ProjectMemberResponse {
  id: string
  project_id: string
  user_id: string
  added_by: string | null
  tenant_id: string
  created_at: string
  full_name: string | null
  email: string | null
  avatar_url: string | null
  org_role: string | null
}

export interface AddMemberPayload {
  user_id: string
}

export interface AddMembersBulkPayload {
  user_ids: string[]
}

export interface ProjectMembersListResponse {
  members: ProjectMemberResponse[]
  count: number
}

export interface BulkAddMembersResponse {
  added: ProjectMemberResponse[]
  count: number
}

export const projectApi = {
  // Story 1.11 — paginated list with filters
  list: (params?: ListProjectsParams) =>
    apiClient
      .get<PaginatedProjectsResponse>('/api/v1/projects', { params })
      .then((r) => r.data),

  create: (payload: CreateProjectPayload) =>
    apiClient.post<ProjectResponse>('/api/v1/projects', payload).then((r) => r.data),

  get: (projectId: string) =>
    apiClient.get<ProjectResponse>(`/api/v1/projects/${projectId}`).then((r) => r.data),

  update: (projectId: string, payload: UpdateProjectPayload) =>
    apiClient.patch<ProjectResponse>(`/api/v1/projects/${projectId}`, payload).then((r) => r.data),

  getSettings: (projectId: string) =>
    apiClient
      .get<ProjectSettingsResponse>(`/api/v1/projects/${projectId}/settings`)
      .then((r) => r.data),

  // Story 1.11 — archive, restore, delete
  archive: (projectId: string) =>
    apiClient
      .post<ProjectResponse>(`/api/v1/projects/${projectId}/archive`)
      .then((r) => r.data),

  restore: (projectId: string) =>
    apiClient
      .post<ProjectResponse>(`/api/v1/projects/${projectId}/restore`)
      .then((r) => r.data),

  delete: (projectId: string) =>
    apiClient
      .delete(`/api/v1/projects/${projectId}`)
      .then(() => undefined),

  // Team membership (Story 1.10)
  listMembers: (projectId: string) =>
    apiClient
      .get<ProjectMembersListResponse>(`/api/v1/projects/${projectId}/members`)
      .then((r) => r.data),

  addMember: (projectId: string, payload: AddMemberPayload) =>
    apiClient
      .post<ProjectMemberResponse>(`/api/v1/projects/${projectId}/members`, payload)
      .then((r) => r.data),

  addMembersBulk: (projectId: string, payload: AddMembersBulkPayload) =>
    apiClient
      .post<BulkAddMembersResponse>(`/api/v1/projects/${projectId}/members/bulk`, payload)
      .then((r) => r.data),

  removeMember: (projectId: string, userId: string) =>
    apiClient
      .delete(`/api/v1/projects/${projectId}/members/${userId}`)
      .then(() => undefined),
}

// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Admin types + endpoints — Story 1.12
// ---------------------------------------------------------------------------

export interface DashboardMetrics {
  active_users: number
  active_projects: number
  test_runs: number
  storage_consumed: string
}

export interface AuditLogEntry {
  id: string
  tenant_id: string
  actor_user_id: string
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}

export interface AuditLogPagination {
  page: number
  per_page: number
  total: number
  total_pages: number
}

export interface PaginatedAuditLogsResponse {
  data: AuditLogEntry[]
  pagination: AuditLogPagination
}

export interface AuditLogFilters {
  date_from?: string
  date_to?: string
  action?: string
  actor_user_id?: string
  page?: number
  per_page?: number
}

export const adminApi = {
  getMetrics: () =>
    apiClient.get<DashboardMetrics>('/api/v1/admin/analytics').then((r) => r.data),

  getAuditLogs: (filters?: AuditLogFilters) =>
    apiClient
      .get<PaginatedAuditLogsResponse>('/api/v1/admin/audit-logs', { params: filters })
      .then((r) => r.data),

  exportAuditLogs: (filters?: Omit<AuditLogFilters, 'page' | 'per_page'>) =>
    apiClient
      .post('/api/v1/admin/audit-logs/export', null, {
        params: filters,
        responseType: 'blob',
      })
      .then((r) => r.data as Blob),
}

// ---------------------------------------------------------------------------
// Data Export & Org Deletion — Story 1.13
// ---------------------------------------------------------------------------

export interface ExportJob {
  job_id: string
  status: 'processing' | 'completed' | 'failed'
  progress_percent: number
  file_size_bytes: number | null
  error: string | null
  created_at: string | null
  completed_at: string | null
  download_url: string | null
}

export interface RequestExportResponse {
  job_id: string
  status: string
  estimated_duration: string
}

export interface ExportEstimate {
  tables: Record<string, number>
  total_records: number
  note: string
}

export interface DeleteOrgPayload {
  org_name_confirmation: string
  totp_code?: string
  password?: string
}

export const exportApi = {
  getEstimate: (orgId: string) =>
    apiClient
      .get<ExportEstimate>(`/api/v1/orgs/${orgId}/export/estimate`)
      .then((r) => r.data),

  requestExport: (orgId: string) =>
    apiClient
      .post<RequestExportResponse>(`/api/v1/orgs/${orgId}/export`)
      .then((r) => r.data),

  listExports: (orgId: string) =>
    apiClient
      .get<{ exports: ExportJob[] }>(`/api/v1/orgs/${orgId}/exports`)
      .then((r) => r.data),

  getExportStatus: (orgId: string, jobId: string) =>
    apiClient
      .get<ExportJob>(`/api/v1/orgs/${orgId}/exports/${jobId}`)
      .then((r) => r.data),

  getDownloadUrl: (orgId: string, jobId: string) =>
    `/api/v1/orgs/${orgId}/exports/${jobId}/download`,

  deleteOrg: (orgId: string, payload: DeleteOrgPayload) =>
    apiClient
      .post<{ status: string; message: string }>(`/api/v1/orgs/${orgId}/delete`, payload)
      .then((r) => r.data),
}

// ---------------------------------------------------------------------------

export const userApi = {
  getMe: () =>
    apiClient.get<UserProfileResponse>('/api/v1/users/me').then((r) => r.data),

  updateProfile: (payload: UpdateProfilePayload) =>
    apiClient.patch<UserProfileResponse>('/api/v1/users/me/profile', payload).then((r) => r.data),

  getAvatarUploadUrl: (payload: AvatarPresignedUrlPayload) =>
    apiClient.post<AvatarPresignedUrlResponse>('/api/v1/users/me/avatar', payload).then((r) => r.data),

  setAvatarUrl: (avatar_url: string) =>
    apiClient.patch<UserProfileResponse>('/api/v1/users/me/avatar', { avatar_url }).then((r) => r.data),

  removeAvatar: () =>
    apiClient.delete<UserProfileResponse>('/api/v1/users/me/avatar').then((r) => r.data),

  getNotifications: () =>
    apiClient.get<NotificationPreferences>('/api/v1/users/me/notifications').then((r) => r.data),

  updateNotifications: (payload: Partial<NotificationPreferences>) =>
    apiClient.put<NotificationPreferences>('/api/v1/users/me/notifications', payload).then((r) => r.data),

  changePassword: (payload: ChangePasswordPayload) =>
    apiClient.post<{ message: string }>('/api/v1/users/me/change-password', payload).then((r) => r.data),
}
