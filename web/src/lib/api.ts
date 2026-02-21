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
    apiClient.post<LoginResponse>('/api/v1/auth/login', payload).then((r) => r.data),

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
