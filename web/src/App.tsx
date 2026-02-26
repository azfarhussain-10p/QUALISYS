import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import SignupPage from '@/pages/signup/SignupPage'
import CheckEmailPage from '@/pages/verify-email/CheckEmailPage'
import VerifyEmailPage from '@/pages/verify-email/VerifyEmailPage'
import LoginPage from '@/pages/login/LoginPage'
import SelectOrgPage from '@/pages/select-org/SelectOrgPage'
import CreateOrgPage from '@/pages/create-org/CreateOrgPage'
import OrganizationSettingsPage from '@/pages/settings/organization/OrganizationSettingsPage'
import SettingsLayout from '@/pages/settings/SettingsLayout'
import ProfilePage from '@/pages/settings/profile/ProfilePage'
import SecurityPage from '@/pages/settings/security/SecurityPage'
import NotificationsPage from '@/pages/settings/notifications/NotificationsPage'
import InviteAcceptPage from '@/pages/invite/accept/InviteAcceptPage'
import ForgotPasswordPage from '@/pages/auth/forgot-password/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/auth/reset-password/ResetPasswordPage'
import CreateProjectPage from '@/pages/projects/create/CreateProjectPage'
import ProjectSettingsPage from '@/pages/projects/settings/ProjectSettingsPage'
import ProjectListPage from '@/pages/projects/ProjectListPage'
import Dashboard from '@/pages/admin/Dashboard'
import AuditLogs from '@/pages/admin/AuditLogs'

// TODO: replace with real org context once auth context provider is complete (Story 1.5+)
const CURRENT_ORG_ID = ''
const CURRENT_USER_ROLE = 'owner'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Story 1.1 — Auth */}
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/check-email" element={<CheckEmailPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />

        {/* Story 1.5 — Login & session management */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/select-org" element={<SelectOrgPage />} />

        {/* Story 1.2 — Org creation & settings */}
        <Route path="/create-org" element={<CreateOrgPage />} />
        <Route
          path="/settings/organization"
          element={<OrganizationSettingsPage orgId={CURRENT_ORG_ID} userRole={CURRENT_USER_ROLE} />}
        />

        {/* Story 1.8 — User settings (Profile, Security, Notifications) */}
        <Route path="/settings" element={<SettingsLayout />}>
          <Route index element={<Navigate to="/settings/profile" replace />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="security" element={<SecurityPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>

        {/* Story 1.3 — Invitation accept (public, unauthenticated) */}
        <Route path="/invite/accept" element={<InviteAcceptPage />} />

        {/* Story 1.6 — Password reset flow */}
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Story 1.9 — Project creation & settings */}
        <Route path="/projects/new" element={<CreateProjectPage />} />
        <Route path="/projects/:projectId/settings" element={<ProjectSettingsPage />} />

        {/* Story 1.11 — Project list (archive, delete, list) */}
        <Route path="/projects" element={<ProjectListPage />} />

        {/* Story 1.12 — Admin analytics + audit log viewer (Owner/Admin only) */}
        <Route path="/admin/dashboard" element={<Dashboard />} />
        <Route path="/admin/audit-logs" element={<AuditLogs />} />

        {/* Root — redirect to login */}
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
