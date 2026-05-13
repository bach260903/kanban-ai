import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DocumentPanel } from '../components/organisms/document-panel'
import { ProjectHeader } from '../components/organisms/project-header'
import { getProject } from '../services/project-api'
import { useProjectStore } from '../store/project-store'

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
            <DocumentPanel projectId={currentProject.id} />
            <p>
              <Link to="/projects">Back to project list</Link>
            </p>
          </section>
        </>
      ) : null}
    </div>
  )
}
