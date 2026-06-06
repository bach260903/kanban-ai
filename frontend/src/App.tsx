import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { lazy, Suspense } from 'react'

import { AuthGuard } from './components/molecules/auth-guard'
import { AuthProvider } from './contexts/auth-context'
import { Spinner } from './components/atoms/spinner'
import LoginPage from './pages/login'
import RegisterPage from './pages/register'
import ResetPasswordPage from './pages/reset-password'
import AuthCallbackPage from './pages/auth-callback'
import DevAuth from './pages/dev-auth'
import './App.css'

// Heavy pages loaded on demand — keeps initial bundle small
const AcceptInvitePage    = lazy(() => import('./pages/accept-invite'))
const AnalyticsPage       = lazy(() => import('./pages/analytics'))
const ConstitutionEditor  = lazy(() => import('./pages/constitution-editor'))
const DashboardPage       = lazy(() => import('./pages/dashboard'))
const DeploymentDetailPage   = lazy(() => import('./pages/deployments/deployment-detail'))
const DeploymentHistoryPage  = lazy(() => import('./pages/deployments/deployment-history'))
const HealthDashboardPage    = lazy(() => import('./pages/devops/health-dashboard'))
const PipelineListPage       = lazy(() => import('./pages/pipelines/pipeline-list'))
const PipelineRunPage        = lazy(() => import('./pages/pipelines/pipeline-run'))
const ProjectList        = lazy(() => import('./pages/project-list'))
const ProjectSettings    = lazy(() => import('./pages/project-settings'))
const ProjectWorkspace   = lazy(() => import('./pages/project-workspace'))

function PageLoader() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: 8 }}>
      <Spinner aria-label="Loading page" />
    </div>
  )
}

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
          <Suspense fallback={<PageLoader />}>
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
          </Suspense>
        </main>
      </BrowserRouter>
    </AuthProvider>
  )
}
