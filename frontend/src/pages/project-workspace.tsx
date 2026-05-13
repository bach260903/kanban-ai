import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { getProject } from '../services/project-api'
import { useProjectStore } from '../store/project-store'
import type { Project } from '../types'

import styles from './project-workspace.module.css'

function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to load project.'
}

function ProjectHeader({ project }: { project: Project }) {
  return (
    <header className={styles.header}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>{project.name}</h1>
        <span className={styles.lang}>{project.primary_language}</span>
      </div>
      {project.description ? <p className={styles.description}>{project.description}</p> : null}
      <nav className={styles.tabs} aria-label="Workspace tabs">
        <span className={styles.tabActive}>Kanban</span>
        <span className={styles.tabPlaceholder}>Documents</span>
        <Link className={styles.tabLink} to={`/projects/${project.id}/constitution`}>
          Constitution
        </Link>
      </nav>
    </header>
  )
}

export default function ProjectWorkspace() {
  const { id } = useParams()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!id) {
        setError('Project ID is missing from URL.')
        setLoading(false)
        return
      }
      try {
        setLoading(true)
        setError(null)
        const project = await getProject(id)
        if (!cancelled) setCurrentProject(project)
      } catch (err) {
        if (!cancelled) setError(errorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
      setCurrentProject(null)
    }
  }, [id, setCurrentProject])

  return (
    <div className={styles.shell}>
      {loading ? (
        <p className={styles.loading}>
          <Spinner aria-label="Loading project workspace" />
          Loading workspace...
        </p>
      ) : null}

      {!loading && error ? <p className={styles.error}>{error}</p> : null}

      {!loading && !error && currentProject ? (
        <>
          <ProjectHeader project={currentProject} />
          <section className={styles.body}>
            <p>Workspace shell ready. Kanban board and document panel will be added in later tasks.</p>
            <p>
              <Link to="/projects">Back to project list</Link>
            </p>
          </section>
        </>
      ) : null}
    </div>
  )
}
