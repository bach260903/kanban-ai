import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DocumentPanel } from '../components/organisms/document-panel'
import { KanbanBoard } from '../components/organisms/kanban-board'
import { ProjectHeader } from '../components/organisms/project-header'
import { ReviewPanel } from '../components/organisms/review-panel'
import { getAuditLogs, type AuditLogsPage } from '../services/audit-api'
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
  const [activeTab, setActiveTab] = useState<'documents' | 'kanban' | 'audit'>('documents')
  const AUDIT_PAGE_SIZE = 25
  const [auditPage, setAuditPage] = useState<AuditLogsPage | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [auditOffset, setAuditOffset] = useState(0)

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

  useEffect(() => {
    if (activeTab !== 'audit' || !currentProject?.id) return
    let cancelled = false
    void (async () => {
      try {
        setAuditLoading(true)
        setAuditError(null)
        const page = await getAuditLogs(currentProject.id, {
          offset: auditOffset,
          limit: AUDIT_PAGE_SIZE,
        })
        if (!cancelled) setAuditPage(page)
      } catch (err) {
        if (!cancelled) {
          setAuditError(errorMessage(err))
          setAuditPage(null)
        }
      } finally {
        if (!cancelled) setAuditLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeTab, currentProject?.id, auditOffset])

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
            <button
              type="button"
              role="tab"
              className={activeTab === 'audit' ? styles.tabActive : styles.tab}
              aria-selected={activeTab === 'audit'}
              id="workspace-tab-audit"
              onClick={() => {
                setAuditOffset(0)
                setActiveTab('audit')
              }}
            >
              Audit log
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
            ) : activeTab === 'kanban' ? (
              <section className={styles.kanban} aria-labelledby="workspace-kanban-heading">
                <h2 id="workspace-kanban-heading" className={styles.kanbanTitle}>
                  Kanban
                </h2>
                <KanbanBoard projectId={currentProject.id} />
              </section>
            ) : (
              <section className={styles.audit} aria-labelledby="workspace-audit-heading">
                <h2 id="workspace-audit-heading" className={styles.auditTitle}>
                  Audit log
                </h2>
                <p className={styles.auditHint}>Read-only history for this project.</p>
                {auditLoading ? (
                  <p className={styles.loading}>
                    <Spinner aria-label="Loading audit log" />
                    Loading…
                  </p>
                ) : null}
                {auditError ? <p className={styles.error}>{auditError}</p> : null}
                {!auditLoading && !auditError && auditPage ? (
                  <>
                    <div className={styles.auditTableWrap}>
                      <table className={styles.auditTable}>
                        <thead>
                          <tr>
                            <th scope="col">Agent</th>
                            <th scope="col">Action</th>
                            <th scope="col">Timestamp</th>
                            <th scope="col">Result</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditPage.items.length === 0 ? (
                            <tr>
                              <td colSpan={4} className={styles.auditEmpty}>
                                No audit entries yet.
                              </td>
                            </tr>
                          ) : (
                            auditPage.items.map((row) => (
                              <tr key={row.id}>
                                <td>
                                  <span className={styles.auditAgentId}>{row.agent_id}</span>
                                  <span className={styles.auditAgentVer}> v{row.agent_version}</span>
                                </td>
                                <td>{row.action_type}</td>
                                <td>{new Date(row.timestamp).toLocaleString()}</td>
                                <td>{row.result}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                    {auditPage.total > 0 ? (
                      <div className={styles.auditPager} role="navigation" aria-label="Audit log pages">
                        <button
                          type="button"
                          className={styles.auditPagerBtn}
                          disabled={auditPage.offset <= 0}
                          onClick={() => setAuditOffset((o) => Math.max(0, o - AUDIT_PAGE_SIZE))}
                        >
                          Previous
                        </button>
                        <span className={styles.auditPagerMeta}>
                          {auditPage.offset + 1}–{auditPage.offset + auditPage.items.length} of{' '}
                          {auditPage.total}
                        </span>
                        <button
                          type="button"
                          className={styles.auditPagerBtn}
                          disabled={auditPage.offset + auditPage.items.length >= auditPage.total}
                          onClick={() => setAuditOffset((o) => o + AUDIT_PAGE_SIZE)}
                        >
                          Next
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : null}
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
