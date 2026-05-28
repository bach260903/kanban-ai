/**
 * PipelineListPage — all pipeline runs for a project.
 * Route: /projects/:projectId/pipelines
 */

import { isAxiosError } from 'axios'
import { CheckCircle2, GitBranch, Loader2, Workflow, XCircle, Circle, SkipForward } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../../components/atoms/spinner'
import { listPipelineRuns, type PipelineRunOut } from '../../services/pipeline-api'
import styles from './pipeline-list.module.css'

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) }
  catch { return '' }
}

function fmtDuration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return '—'
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime()
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function StatusBadge({ status }: { status: PipelineRunOut['status'] }) {
  const map = {
    queued:    { label: 'Queued',    icon: <Circle size={11} />,                         cls: styles.badgeQueued },
    running:   { label: 'Running',   icon: <Loader2 size={11} className="animate-spin" />, cls: styles.badgeRunning },
    success:   { label: 'Passed',    icon: <CheckCircle2 size={11} />,                   cls: styles.badgeSuccess },
    failure:   { label: 'Failed',    icon: <XCircle size={11} />,                        cls: styles.badgeFailure },
    cancelled: { label: 'Cancelled', icon: <SkipForward size={11} />,                    cls: styles.badgeCancelled },
  }
  const { label, icon, cls } = map[status] ?? map.queued
  return <span className={`${styles.badge} ${cls}`}>{icon} {label}</span>
}

function StepPills({ steps }: { steps: PipelineRunOut['steps'] }) {
  const iconMap: Record<string, React.ReactNode> = {
    success: <CheckCircle2 size={10} style={{ color: '#16a34a' }} />,
    failure: <XCircle size={10} style={{ color: '#dc2626' }} />,
    running: <Loader2 size={10} className="animate-spin" style={{ color: '#3b82f6' }} />,
    pending: <Circle size={10} style={{ color: '#94a3b8' }} />,
    skipped: <SkipForward size={10} style={{ color: '#9ca3af' }} />,
  }
  return (
    <div className={styles.stepPills}>
      {steps.map((s) => (
        <span key={s.id} className={styles.stepPill} title={`${s.step_key}: ${s.status}`}>
          {iconMap[s.status] ?? iconMap.pending}
          <span className={styles.stepPillLabel}>{s.step_key}</span>
        </span>
      ))}
    </div>
  )
}

export default function PipelineListPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [runs, setRuns] = useState<PipelineRunOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const data = await listPipelineRuns(projectId)
        if (!cancelled) setRuns(data)
      } catch (err) {
        if (!cancelled) {
          const msg = isAxiosError(err)
            ? ((err.response?.data as { detail?: string })?.detail ?? err.message)
            : (err instanceof Error ? err.message : 'Error loading pipelines')
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId])

  return (
    <div className={styles.page}>
      <div className={styles.breadcrumb}>
        <Link to={`/projects/${projectId}`} className={styles.breadcrumbLink}>Project</Link>
        <span>›</span>
        <span>Pipelines</span>
      </div>

      <header className={styles.header}>
        <h1 className={styles.title}>
          <Workflow size={22} aria-hidden />
          Pipeline Runs
        </h1>
        <p className={styles.sub}>CI/CD pipeline history for this project.</p>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      {loading ? (
        <div className={styles.loading}><Spinner /> Loading…</div>
      ) : runs.length === 0 ? (
        <div className={styles.empty}>
          <Workflow size={36} style={{ color: 'var(--font-secondary-color)', opacity: 0.4 }} />
          <p>No pipeline runs yet.</p>
          <p style={{ fontSize: 13 }}>
            Pipelines run automatically when a task is approved (REVIEW → DONE).
          </p>
        </div>
      ) : (
        <div className={styles.table}>
          {runs.map((run) => (
            <Link
              key={run.id}
              to={`/projects/${projectId}/pipeline-runs/${run.id}`}
              className={styles.row}
            >
              <div className={styles.rowLeft}>
                <StatusBadge status={run.status} />
                <div>
                  <span className={styles.runId}>#{run.id.slice(0, 8)}</span>
                  {run.branch_name && (
                    <span className={styles.branch}>
                      <GitBranch size={11} aria-hidden />
                      {run.branch_name}
                    </span>
                  )}
                </div>
                <StepPills steps={run.steps} />
              </div>
              <div className={styles.rowRight}>
                <span className={styles.duration}>{fmtDuration(run.started_at, run.completed_at)}</span>
                <span className={styles.time}>{fmtTime(run.created_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
