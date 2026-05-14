import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DocumentPanel } from '../components/organisms/document-panel'
import { KanbanBoard } from '../components/organisms/kanban-board'
import { ProjectHeader } from '../components/organisms/project-header'
import { ReviewPanel } from '../components/organisms/review-panel'
import { getProject } from '../services/project-api'
import { getTasks, groupedResponseToTaskColumns } from '../services/task-api'
import { emptyTaskColumns, useTaskStore } from '../store/task-store'
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
  const columns = useTaskStore((s) => s.columns)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'documents' | 'kanban'>('documents')

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
      useTaskStore.getState().clearTaskAgentRuns()
      useTaskStore.getState().setColumns(emptyTaskColumns())
    }
  }, [id, setCurrentProject])

  useEffect(() => {
    if (!currentProject?.id) return
    let cancelled = false
    void (async () => {
      try {
        const data = await getTasks(currentProject.id)
        if (!cancelled) {
          useTaskStore.getState().clearTaskAgentRuns()
          useTaskStore.getState().setColumns(groupedResponseToTaskColumns(data))
        }
      } catch {
        /* Kanban tab will surface load errors if user opens it */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [currentProject?.id])

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
          {columns.review.length > 0 ? <ReviewPanel projectId={currentProject.id} /> : null}
          <div className={styles.tabs} role="tablist" aria-label="Workspace sections">
            <button
              type="button"
              role="tab"
              className={activeTab === 'documents' ? styles.tabActive : styles.tab}
              aria-selected={activeTab === 'documents'}
              id="workspace-tab-documents"
              onClick={() => setActiveTab('documents')}
            >
              Documents
            </button>
            <button
              type="button"
              role="tab"
              className={activeTab === 'kanban' ? styles.tabActive : styles.tab}
              aria-selected={activeTab === 'kanban'}
              id="workspace-tab-kanban"
              onClick={() => setActiveTab('kanban')}
            >
              Kanban
            </button>
          </div>
          <section className={styles.body}>
            {activeTab === 'documents' ? (
              <section className={styles.documents} aria-labelledby="workspace-documents-heading">
                <h2 id="workspace-documents-heading" className={styles.documentsTitle}>
                  Documents
                </h2>
                <div className={styles.documentPanels}>
                  <DocumentPanel projectId={currentProject.id} documentType="SPEC" />
                  <DocumentPanel projectId={currentProject.id} documentType="PLAN" />
                </div>
              </section>
            ) : (
              <section className={styles.kanban} aria-labelledby="workspace-kanban-heading">
                <h2 id="workspace-kanban-heading" className={styles.kanbanTitle}>
                  Kanban
                </h2>
                <KanbanBoard projectId={currentProject.id} />
              </section>
            )}
            <p>
              <Link to="/projects">Back to project list</Link>
            </p>
          </section>
        </>
      ) : null}
    </div>
  )
}
