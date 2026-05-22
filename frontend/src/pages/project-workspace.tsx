import { isAxiosError } from 'axios'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DocumentPanel } from '../components/organisms/document-panel'
import { KanbanBoard } from '../components/organisms/kanban-board'
import { ProjectHeader } from '../components/organisms/project-header'
import { MemoryEditor } from '../components/organisms/memory-editor'
import { ReviewPanel } from '../components/organisms/review-panel'
import { ThoughtStreamPanel } from '../components/organisms/thought-stream-panel'
import { useInlineComments } from '../hooks/use-inline-comments'
import { getAuditLogs, type AuditLogsPage } from '../services/audit-api'
import { getDocuments } from '../services/document-api'
import { getProject } from '../services/project-api'
import { getTasks, groupedResponseToTaskColumns } from '../services/task-api'
import { emptyTaskColumns, useTaskStore } from '../store/task-store'
import { useProjectStore } from '../store/project-store'

import styles from './project-workspace.module.css'

function errorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
      return (
        'Backend did not respond in time. Restart uvicorn on port 8000 ' +
        '(kanban-ai/backend) and ensure Postgres/Redis are running.'
      )
    }
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
  const inProgressTask = useMemo(() => {
    const list = [...columns.in_progress].sort(
      (a, b) => a.priority - b.priority || a.title.localeCompare(b.title),
    )
    return list[0] ?? null
  }, [columns.in_progress])
  const [thoughtStreamOpen, setThoughtStreamOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [planApproved, setPlanApproved] = useState(false)
  const [planPendingRunId, setPlanPendingRunId] = useState<string | null>(null)
  const [documentsRefreshKey, setDocumentsRefreshKey] = useState(0)
  const [selectedReviewTaskId, setSelectedReviewTaskId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'documents' | 'kanban' | 'memory' | 'audit'>('documents')
  const AUDIT_PAGE_SIZE = 25
  const [auditPage, setAuditPage] = useState<AuditLogsPage | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [auditOffset, setAuditOffset] = useState(0)
  const inlineComments = useInlineComments()

  const refreshKanbanColumns = useCallback(async () => {
    if (!currentProject?.id) return
    try {
      const data = await getTasks(currentProject.id)
      useTaskStore.getState().clearTaskAgentRuns()
      useTaskStore.getState().setColumns(groupedResponseToTaskColumns(data))
    } catch {
      /* KanbanBoard load effect will retry */
    }
  }, [currentProject?.id])

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
      setLoading(false)
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
        const [data, planDocs] = await Promise.all([
          getTasks(currentProject.id),
          getDocuments(currentProject.id, 'PLAN'),
        ])
        if (!cancelled) {
          useTaskStore.getState().clearTaskAgentRuns()
          useTaskStore.getState().setColumns(groupedResponseToTaskColumns(data))
          setPlanApproved(planDocs.some((d) => d.status === 'approved'))
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

  useEffect(() => {
    if (inProgressTask == null) {
      setThoughtStreamOpen(false)
    }
  }, [inProgressTask])

  useEffect(() => {
    if (
      selectedReviewTaskId != null &&
      !columns.review.some((t) => t.id === selectedReviewTaskId)
    ) {
      setSelectedReviewTaskId(null)
    }
  }, [columns.review, selectedReviewTaskId])

  /** Re-sync columns when opening Kanban (fixes stale in_progress after coder → review). */
  useEffect(() => {
    if (activeTab !== 'kanban') return
    void refreshKanbanColumns()
  }, [activeTab, refreshKanbanColumns])

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
          <ProjectHeader
            project={currentProject}
            activeTab={activeTab}
            onTabChange={(tab) => {
              if (tab === 'audit') setAuditOffset(0)
              setActiveTab(tab)
            }}
          />
          {activeTab === 'kanban' && selectedReviewTaskId ? (
            <ReviewPanel
              projectId={currentProject.id}
              taskId={selectedReviewTaskId}
              inlineComments={inlineComments}
              onClose={() => setSelectedReviewTaskId(null)}
            />
          ) : null}
          {inProgressTask ? (
            <>
              {!thoughtStreamOpen ? (
                <button
                  type="button"
                  className={styles.thoughtStreamFab}
                  onClick={() => setThoughtStreamOpen(true)}
                  aria-expanded={false}
                  aria-controls="thought-stream-panel"
                >
                  Thought stream
                </button>
              ) : null}
              {thoughtStreamOpen ? (
                <>
                  <button
                    type="button"
                    className={styles.thoughtStreamBackdrop}
                    aria-label="Close thought stream"
                    onClick={() => setThoughtStreamOpen(false)}
                  />
                  <aside
                    id="thought-stream-panel"
                    className={styles.thoughtStreamPanel}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="thought-stream-panel-heading"
                  >
                    <div className={styles.thoughtStreamPanelToolbar}>
                      <div>
                        <h2 id="thought-stream-panel-heading" className={styles.thoughtStreamPanelTitle}>
                          Thought stream
                        </h2>
                        <p className={styles.thoughtStreamPanelSubtitle}>{inProgressTask.title}</p>
                      </div>
                      <button
                        type="button"
                        className={styles.thoughtStreamClose}
                        onClick={() => setThoughtStreamOpen(false)}
                        aria-label="Close thought stream panel"
                      >
                        Close
                      </button>
                    </div>
                    <div className={styles.thoughtStreamPanelBody}>
                      <ThoughtStreamPanel
                        taskId={inProgressTask.id}
                        embedded
                        onStreamEnded={() => {
                          void refreshKanbanColumns()
                        }}
                      />
                    </div>
                  </aside>
                </>
              ) : null}
            </>
          ) : null}
          <section className={styles.body}>
            {activeTab === 'documents' ? (
              <section className={styles.documents} aria-labelledby="workspace-documents-heading">
                <h2 id="workspace-documents-heading" className={styles.documentsTitle}>
                  Documents
                </h2>
                <div className={styles.documentPanels}>
                  <DocumentPanel
                    projectId={currentProject.id}
                    documentType="SPEC"
                    refreshKey={documentsRefreshKey}
                    onPlanAutoStart={(runId) => {
                      setPlanPendingRunId(runId)
                      setDocumentsRefreshKey((k) => k + 1)
                    }}
                  />
                  <DocumentPanel
                    projectId={currentProject.id}
                    documentType="PLAN"
                    linkedAgentRunId={planPendingRunId}
                    refreshKey={documentsRefreshKey}
                  />
                </div>
              </section>
            ) : activeTab === 'kanban' ? (
              <section className={styles.kanban} aria-labelledby="workspace-kanban-heading">
                <h2 id="workspace-kanban-heading" className={styles.kanbanTitle}>
                  Kanban
                </h2>
                <KanbanBoard
                  projectId={currentProject.id}
                  planApproved={planApproved}
                  selectedReviewTaskId={selectedReviewTaskId}
                  onSelectReviewTask={setSelectedReviewTaskId}
                />
              </section>
            ) : activeTab === 'memory' ? (
              <section className={styles.memory} aria-labelledby="workspace-memory-heading">
                <h2 id="workspace-memory-heading" className={styles.memoryTitle}>
                  Memory
                </h2>
                <p className={styles.memoryHint}>Lessons learned from completed work on this project.</p>
                <MemoryEditor projectId={currentProject.id} />
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
