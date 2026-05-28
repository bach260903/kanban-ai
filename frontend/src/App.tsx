import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthGuard } from './components/molecules/auth-guard'
import { AuthProvider } from './contexts/auth-context'
import AcceptInvitePage from './pages/accept-invite'
import AnalyticsPage from './pages/analytics'
import AuthCallbackPage from './pages/auth-callback'
import ConstitutionEditor from './pages/constitution-editor'
import DashboardPage from './pages/dashboard'
import DeploymentDetailPage from './pages/deployments/deployment-detail'
import DeploymentHistoryPage from './pages/deployments/deployment-history'
import HealthDashboardPage from './pages/devops/health-dashboard'
import PipelineListPage from './pages/pipelines/pipeline-list'
import PipelineRunPage from './pages/pipelines/pipeline-run'
import DevAuth from './pages/dev-auth'
import LoginPage from './pages/login'
import ProjectList from './pages/project-list'
import ProjectSettings from './pages/project-settings'
import ProjectWorkspace from './pages/project-workspace'
import RegisterPage from './pages/register'
import ResetPasswordPage from './pages/reset-password'
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
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
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
            <Route
              path="/projects/:projectId/pipelines"
              element={
                <AuthGuard>
                  <PipelineListPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:projectId/pipeline-runs/:runId"
              element={
                <AuthGuard>
                  <PipelineRunPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:projectId/deployments"
              element={
                <AuthGuard>
                  <DeploymentHistoryPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:projectId/deployments/:deploymentId"
              element={
                <AuthGuard>
                  <DeploymentDetailPage />
                </AuthGuard>
              }
            />
            <Route
              path="/projects/:projectId/devops"
              element={
                <AuthGuard>
                  <HealthDashboardPage />
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
