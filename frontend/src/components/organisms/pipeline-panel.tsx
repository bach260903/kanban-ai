/**
 * PipelinePanel — embeddable CI/CD pipeline runs list.
 *
 * Renders recent pipeline runs (status + per-step pills) inline, so the user sees
 * results directly in the Pipelines tab without navigating to the full-page view.
 * Each row still links to the full run detail. Auto-refreshes while a run is active.
 */

import { isAxiosError } from 'axios'
import { CheckCircle2, Circle, GitBranch, Loader2, SkipForward, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Spinner } from '../atoms/spinner'
import { listPipelineRuns, type PipelineRunOut } from '../../services/pipeline-api'
import styles from '../../pages/pipelines/pipeline-list.module.css'

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return ''
  }
}

function fmtDuration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return '—'
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime()
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function StatusBadge({ status }: { status: PipelineRunOut['status'] }) {
  const map = {
    queued: { label: 'Queued', icon: <Circle size={11} />, cls: styles.badgeQueued },
    running: { label: 'Running', icon: <Loader2 size={11} className="animate-spin" />, cls: styles.badgeRunning },
    success: { label: 'Passed', icon: <CheckCircle2 size={11} />, cls: styles.badgeSuccess },
    failure: { label: 'Failed', icon: <XCircle size={11} />, cls: styles.badgeFailure },
    cancelled: { label: 'Cancelled', icon: <SkipForward size={11} />, cls: styles.badgeCancelled },
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

const ACTIVE_STATUSES = new Set(['queued', 'running'])

export function PipelinePanel({ projectId, limit = 10 }: { projectId: string; limit?: number }) {
  const [runs, setRuns] = useState<PipelineRunOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await listPipelineRuns(projectId)
        if (!cancelled) {
          setRuns(data)
          setError(null)
          // Only keep polling if there are active runs
          const hasActive = data.some((r) => ACTIVE_STATUSES.has(r.status))
          if (!hasActive && timer.current) {
            clearInterval(timer.current)
            timer.current = null
          } else if (hasActive && !timer.current) {
            timer.current = setInterval(load, 8000)
          }
        }
      } catch (err) {
        if (!cancelled) {
          const msg = isAxiosError(err)
            ? ((err.response?.data as { detail?: string })?.detail ?? err.message)
            : err instanceof Error
              ? err.message
              : 'Error loading pipelines'
          setError(msg)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    // Start polling — load() will stop it automatically when no active runs
    timer.current = setInterval(load, 8000)
    return () => {
      cancelled = true
      if (timer.current) clearInterval(timer.current)
    }
  }, [projectId])

  if (loading) {
    return (
      <div className={styles.loading}>
        <Spinner /> Loading…
      </div>
    )
  }

  if (error) {
    return <div className={styles.error}>{error}</div>
  }

  if (runs.length === 0) {
    return (
      <p style={{ fontSize: 13, color: 'var(--font-secondary-color)' }}>
        No pipeline runs yet. Pipelines run automatically when a task is approved (REVIEW → DONE).
      </p>
    )
  }

  return (
    <div className={styles.table}>
      {runs.slice(0, limit).map((run) => (
        <Link
          key={run.id}
          to={`/projects/${projectId}/pipeline-runs/${run.id}`}
          className={styles.row}
        >
          <div className={styles.rowLeft}>
            <StatusBadge status={run.status} />
            <div>
              <span className={styles.runId}>{run.task_title ?? `#${run.id.slice(0, 8)}`}</span>
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
  )
}
