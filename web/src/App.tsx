import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import SignupPage from '@/pages/signup/SignupPage'
import CheckEmailPage from '@/pages/verify-email/CheckEmailPage'
import VerifyEmailPage from '@/pages/verify-email/VerifyEmailPage'
import LoginPage from '@/pages/login/LoginPage'
import SelectOrgPage from '@/pages/select-org/SelectOrgPage'
import CreateOrgPage from '@/pages/create-org/CreateOrgPage'
import OrganizationSettingsPage from '@/pages/settings/organization/OrganizationSettingsPage'
import SecurityPage from '@/pages/settings/security/SecurityPage'
import InviteAcceptPage from '@/pages/invite/accept/InviteAcceptPage'

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

        {/* Story 1.5 — Security / session management */}
        <Route path="/settings/security" element={<SecurityPage />} />

        {/* Story 1.3 — Invitation accept (public, unauthenticated) */}
        <Route path="/invite/accept" element={<InviteAcceptPage />} />

        {/* Root — redirect to login */}
        <Route path="/" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
