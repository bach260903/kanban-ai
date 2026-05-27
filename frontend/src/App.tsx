import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGuard } from './components/molecules/auth-guard'
import { AuthProvider } from './contexts/auth-context'
import AcceptInvitePage from './pages/accept-invite'
import AnalyticsPage from './pages/analytics'
import ConstitutionEditor from './pages/constitution-editor'
import DashboardPage from './pages/dashboard'
import DevAuth from './pages/dev-auth'
import LoginPage from './pages/login'
import ProjectList from './pages/project-list'
import ProjectSettings from './pages/project-settings'
import ProjectWorkspace from './pages/project-workspace'
import RegisterPage from './pages/register'
import './App.css'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <main id="main-content">
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/dev/auth" element={<DevAuth />} />
            <Route
              path="/invitations/:token"
              element={
                <AuthGuard>
                  <AcceptInvitePage />
                </AuthGuard>
              }
            />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="/dashboard"
              element={
                <AuthGuard>
                  <DashboardPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects"
              element={
                <AuthGuard>
                  <ProjectList />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:projectId/analytics"
              element={
                <AuthGuard>
                  <AnalyticsPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:id"
              element={
                <AuthGuard>
                  <ProjectWorkspace />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:id/settings"
              element={
                <AuthGuard>
                  <ProjectSettings />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:id/constitution"
              element={
                <AuthGuard>
                  <ConstitutionEditor />
                </AuthGuard>
              }
            />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </BrowserRouter>
    </AuthProvider>
  )
}
