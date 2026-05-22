import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ConstitutionEditor from './pages/constitution-editor'
<<<<<<< HEAD
import LoginPage from './pages/login'
=======
import DevAuth from './pages/dev-auth'
>>>>>>> feature
import ProjectList from './pages/project-list'
import ProjectWorkspace from './pages/project-workspace'
import RegisterPage from './pages/register'
import { getAuthToken } from './services/api'
import './App.css'

function RequireAuth({ children }: { children: React.ReactNode }) {
  return getAuthToken() ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<Navigate to="/projects" replace />} />
<<<<<<< HEAD
        <Route path="/projects" element={<RequireAuth><ProjectList /></RequireAuth>} />
        <Route path="/projects/:id" element={<RequireAuth><ProjectWorkspace /></RequireAuth>} />
        <Route path="/projects/:id/constitution" element={<RequireAuth><ConstitutionEditor /></RequireAuth>} />
=======
        <Route path="/dev/auth" element={<DevAuth />} />
        <Route path="/projects" element={<ProjectList />} />
        <Route path="/projects/:id" element={<ProjectWorkspace />} />
        <Route path="/projects/:id/constitution" element={<ConstitutionEditor />} />
>>>>>>> feature
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
