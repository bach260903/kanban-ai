import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ConstitutionStub from './pages/constitution-stub'
import ProjectList from './pages/project-list'
import ProjectWorkspace from './pages/project-workspace'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectList />} />
        <Route path="/projects/:id" element={<ProjectWorkspace />} />
        <Route path="/projects/:id/constitution" element={<ConstitutionStub />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
