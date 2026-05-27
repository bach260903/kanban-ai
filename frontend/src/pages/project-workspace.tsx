import { isAxiosError } from 'axios'
import {
  CheckCircle2,
  Code2,
  Cpu,
  Eye,
  Settings,
  XCircle,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type ReactElement } from 'react'
import { useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { DependencyGraph } from '../components/organisms/dependency-graph'
import { DocumentPanel } from '../components/organisms/document-panel'
import { KanbanBoard } from '../components/organisms/kanban-board'
import { ProjectHeader } from '../components/organisms/project-header'
import { MemoryEditor } from '../components/organisms/memory-editor'
import { ReviewPanel } from '../components/organisms/review-panel'
import { ThoughtStreamPanel } from '../components/organisms/thought-stream-panel'
import { useInlineComments } from '../hooks/use-inline-comments'
import { showErrorToast } from '../lib/toast'
import { getAuditLogs, type AuditLogRow, type AuditLogsPage } from '../services/audit-api'
import { getDocuments } from '../services/document-api'
import { getProject } from '../services/project-api'
import { getTasks, groupedResponseToTaskColumns } from '../services/task-api'
import { emptyTaskColumns, useTaskStore, type TaskColumns } from '../store/task-store'
import type { TaskStatus } from '../types'
import { useProjectStore } from '../store/project-store'
import { relativeTime } from '../utils/relative-time'

import styles from './project-workspace.module.css'

type AuditAgentKind = 'architect' | 'coder' | 'reviewer' | 'system'

function classifyAgent(agentId: string): AuditAgentKind {
  const id = agentId.toLowerCase()
  if (id.includes('architect') || id.includes('planner') || id.includes('spec')) {
    return 'architect'
  }
  if (id.includes('review')) return 'reviewer'
  if (id.includes('coder') || id.includes('writer') || id.includes('code')) {
    return 'coder'
  }
  return 'system'
}

const AGENT_KIND_LABEL: Record<AuditAgentKind, string> = {
  architect: 'Architect',
  coder: 'Coder',
  reviewer: 'Reviewer',
  system: 'System',
}

function AgentIcon({ kind }: { kind: AuditAgentKind }) {
  const props = { size: 14, 'aria-hidden': true as const, className: styles.auditAgentIcon }
  if (kind === 'architect') return <Cpu {...props} />
  if (kind === 'coder') return <Code2 {...props} />
  if (kind === 'reviewer') return <Eye {...props} />
  return <Settings {...props} />
}

function humanizeAction(action: string): string {
  const map: Record<string, string> = {
    coder_llm: 'Coder: LLM call',
    coder_write_file: 'Coder: Write file',
    coder_run_tests: 'Coder: Run tests',
    coder_commit: 'Coder: Commit',
    task_diff_approve: 'Task: Approve diff',
    task_diff_reject: 'Task: Reject diff',
    architect_generate_spec: 'Architect: Generate SPEC',
    architect_generate_plan: 'Architect: Generate PLAN',
    reviewer_check: 'Reviewer: Run checks',
  }
  if (map[action]) return map[action]
  return action
    .split(/[_:]/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ')
}

function isSuccessResult(result: string): boolean {
  const r = result.toLowerCase()
  return r === 'success' || r === 'ok' || r === 'pass' || r === 'passed' || r === 'true'
}

function isFailureResult(result: string): boolean {
  const r = result.toLowerCase()
  return (
    r === 'failure' ||
    r === 'failed' ||
    r === 'fail' ||
    r === 'error' ||
    r === 'timeout' ||
    r === 'rejected'
  )
}

function renderResultCell(result: string): ReactElement {
  if (isSuccessResult(result)) {
    return (
      <span className={`${styles.auditResultCell} ${styles.auditResultSuccess}`}>
        <CheckCircle2 size={14} aria-hidden="true" />
        Success
      </span>
    )
  }
  if (isFailureResult(result)) {
    return (
      <span className={`${styles.auditResultCell} ${styles.auditResultFail}`}>
        <XCircle size={14} aria-hidden="true" />
        Failed
      </span>
    )
  }
  return <span className={styles.auditResultCell}>{result}</span>
}

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

const BOARD_STATUSES: TaskStatus[] = [
  'todo',
  'in_progress',
  'review',
  'done',
  'rejected',
  'conflict',
]

function findTaskStatus(columns: TaskColumns, taskId: string): TaskStatus | null {
  for (const status of BOARD_STATUSES) {
    if (columns[status].some((task) => task.id === taskId)) return status
  }
  return null
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
  const [activeTab, setActiveTab] = useState<
    'documents' | 'kanban' | 'memory' | 'audit' | 'dependencies'
  >('documents')
  const AUDIT_PAGE_SIZE = 25
  const [auditPage, setAuditPage] = useState<AuditLogsPage | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState<string | null>(null)
  const [auditOffset, setAuditOffset] = useState(0)
  const [auditAgentFilter, setAuditAgentFilter] = useState<'all' | AuditAgentKind>('all')
  const [auditResultFilter, setAuditResultFilter] = useState<'all' | 'success' | 'failed'>('all')
  const inlineComments = useInlineComments()

  const filteredAuditRows = useMemo<AuditLogRow[]>(() => {
    if (!auditPage) return []
    return auditPage.items.filter((row) => {
      if (auditAgentFilter !== 'all' && classifyAgent(row.agent_id) !== auditAgentFilter) {
        return false
      }
      if (auditResultFilter === 'success' && !isSuccessResult(row.result)) return false
      if (auditResultFilter === 'failed' && !isFailureResult(row.result)) return false
      return true
    })
  }, [auditPage, auditAgentFilter, auditResultFilter])

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
            onOpenTask={(taskId) => {
              const status = findTaskStatus(useTaskStore.getState().columns, taskId)
              if (!status) {
                showErrorToast('Task không thuộc dự án hiện tại')
                return
              }
              setActiveTab('kanban')
              if (status === 'review') {
                setSelectedReviewTaskId(taskId)
              }
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
            ) : activeTab === 'dependencies' ? (
              <section className={styles.memory} aria-labelledby="workspace-deps-heading">
                <h2 id="workspace-deps-heading" className={styles.memoryTitle}>
                  Dependencies
                </h2>
                <p className={styles.memoryHint}>
                  Task dependency graph — blocked tasks unlock when prerequisites reach Done.
                </p>
                <DependencyGraph
                  projectId={currentProject.id}
                  onChanged={() => void refreshKanbanColumns()}
                />
              </section>
            ) : activeTab === 'memory' ? (
              <section className={styles.memory} aria-labelledby="workspace-memory-heading">
                <h2 id="workspace-memory-heading" className={styles.memoryTitle}>
                  Memory
                </h2>
                <p className={styles.memoryHint}>Lessons learned from completed tasks.</p>
                <MemoryEditor projectId={currentProject.id} />
              </section>
            ) : (
              <section className={styles.audit} aria-labelledby="workspace-audit-heading">
                <h2 id="workspace-audit-heading" className={styles.auditTitle}>
                  Audit log
                </h2>
                <p className={styles.auditHint}>Read-only history for this project.</p>
                <div className={styles.auditFilters} role="group" aria-label="Audit log filters">
                  <label className={styles.auditFilterField}>
                    Agent:
                    <select
                      value={auditAgentFilter}
                      onChange={(e) =>
                        setAuditAgentFilter(e.target.value as 'all' | AuditAgentKind)
                      }
                    >
                      <option value="all">All agents</option>
                      <option value="architect">Architect</option>
                      <option value="coder">Coder</option>
                      <option value="reviewer">Reviewer</option>
                      <option value="system">System</option>
                    </select>
                  </label>
                  <label className={styles.auditFilterField}>
                    Result:
                    <select
                      value={auditResultFilter}
                      onChange={(e) =>
                        setAuditResultFilter(e.target.value as 'all' | 'success' | 'failed')
                      }
                    >
                      <option value="all">All results</option>
                      <option value="success">Success only</option>
                      <option value="failed">Failed only</option>
                    </select>
                  </label>
                </div>
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
                          {filteredAuditRows.length === 0 ? (
                            <tr>
                              <td colSpan={4} className={styles.auditEmpty}>
                                {auditPage.items.length === 0
                                  ? 'No audit entries yet.'
                                  : 'No entries match the selected filters.'}
                              </td>
                            </tr>
                          ) : (
                            filteredAuditRows.map((row) => {
                              const kind = classifyAgent(row.agent_id)
                              const failed = isFailureResult(row.result)
                              return (
                                <tr key={row.id} className={failed ? styles.auditRowFail : undefined}>
                                  <td>
                                    <span className={styles.auditAgentCell}>
                                      <AgentIcon kind={kind} />
                                      <span className={styles.auditAgentId}>
                                        {AGENT_KIND_LABEL[kind]}
                                      </span>
                                      <span className={styles.auditAgentVer}>
                                        v{row.agent_version}
                                      </span>
                                    </span>
                                  </td>
                                  <td>{humanizeAction(row.action_type)}</td>
                                  <td>
                                    <time
                                      dateTime={row.timestamp}
                                      title={new Date(row.timestamp).toLocaleString()}
                                    >
                                      {relativeTime(row.timestamp)}
                                    </time>
                                  </td>
                                  <td>{renderResultCell(row.result)}</td>
                                </tr>
                              )
                            })
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
          </section>
        </>
      ) : null}
    </div>
  )
}
