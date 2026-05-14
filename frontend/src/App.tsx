import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ConstitutionEditor from './pages/constitution-editor'
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
        <Route path="/projects/:id/constitution" element={<ConstitutionEditor />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
