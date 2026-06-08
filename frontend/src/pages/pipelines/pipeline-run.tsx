/**
 * PipelineRunPage — live execution view for a single pipeline run.
 *
 * Route: /projects/:projectId/pipeline-runs/:runId
 *
 * Features:
 * - Sequential step timeline (test → lint → build → preview_deploy)
 * - Live status via SSE subscription
 * - Expandable logs + AI reasoning per step
 * - Status badges with pulse animation for running steps
 * - Phase 3: failure analysis panel + retry timeline + approval notices
 */

import { isAxiosError } from 'axios'
import {
  Bot,
  ChevronDown,
  CheckCircle2,
  Circle,
  ExternalLink,
  GitBranch,
  Loader2,
  RotateCcw,
  Rocket,
  Terminal,
  XCircle,
  SkipForward,
  Workflow,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Spinner } from '../../components/atoms/spinner'
import {
  FailureAnalysisPanel,
  type AnalysisState,
} from '../../components/organisms/failure-analysis-panel'
import {
  getPipelineRun,
  rerunPipelineRun,
  subscribePipelineRun,
  type PipelineEvent,
  type PipelineRunOut,
  type PipelineStepOut,
} from '../../services/pipeline-api'

import styles from './pipeline-run.module.css'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

function msgFromError(err: unknown): string {
  if (isAxiosError(err)) return (err.response?.data as { detail?: string })?.detail ?? err.message
  if (err instanceof Error) return err.message
  return 'Unknown error'
}

// ── Status badge ─────────────────────────────────────────────────────────────

type RunStatus = PipelineRunOut['status']

function RunStatusBadge({ status }: { status: RunStatus }) {
  const cls = {
    queued:    styles.badgeQueued,
    running:   styles.badgeRunning,
    success:   styles.badgeSuccess,
    failure:   styles.badgeFailure,
    cancelled: styles.badgeCancelled,
  }[status] ?? styles.badgeQueued

  const label = {
    queued: 'Queued', running: 'Running', success: 'Passed',
    failure: 'Failed', cancelled: 'Cancelled',
  }[status] ?? status

  return (
    <span className={`${styles.badge} ${cls}`}>
      {status === 'running' && <span className={styles.pulsingDot} />}
      {label}
    </span>
  )
}

// ── Step icon ─────────────────────────────────────────────────────────────────

type StepStatus = PipelineStepOut['status']

function StepIcon({ status }: { status: StepStatus }) {
  const map: Record<StepStatus, { icon: React.ReactNode; cls: string }> = {
    pending: { icon: <Circle size={12} />, cls: styles.stepIconPending },
    running: { icon: <Loader2 size={12} className="animate-spin" />, cls: styles.stepIconRunning },
    success: { icon: <CheckCircle2 size={12} />, cls: styles.stepIconSuccess },
    failure: { icon: <XCircle size={12} />, cls: styles.stepIconFailure },
    skipped: { icon: <SkipForward size={12} />, cls: styles.stepIconSkipped },
  }
  const { icon, cls } = map[status] ?? map.pending
  return <span className={`${styles.stepIcon} ${cls}`}>{icon}</span>
}

// ── Single step row ───────────────────────────────────────────────────────────

function StepRow({
  step,
  analysisState,
}: {
  step: PipelineStepOut
  analysisState: AnalysisState
}) {
  const [open, setOpen] = useState(step.status === 'failure')

  // Auto-open when analysis starts
  const prevPhase = useRef(analysisState.phase)
  useEffect(() => {
    if (prevPhase.current === 'idle' && analysisState.phase !== 'idle') {
      setOpen(true)
    }
    prevPhase.current = analysisState.phase
  }, [analysisState.phase])

  const hasAnalysis =
    step.failure_analyses.length > 0 || analysisState.phase !== 'idle'

  return (
    <div className={`${styles.step} ${step.attempt > 1 ? styles.stepRetried : ''}`}>
      <div
        className={styles.stepHeader}
        onClick={() => setOpen((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((v) => !v)}
        aria-expanded={open}
      >
        <div className={styles.stepLeft}>
          <StepIcon status={step.status} />
          <span className={styles.stepName}>{step.step_key}</span>
          {step.attempt > 1 && (
            <span className={styles.retryBadge} title={`Auto-retried — attempt ${step.attempt}`}>
              ×{step.attempt}
            </span>
          )}
          {step.ai_reasoning && (
            <span className={styles.stepReasoning}>{step.ai_reasoning}</span>
          )}
        </div>
        <div className={styles.stepRight}>
          {step.duration_ms != null && (
            <span className={styles.stepDuration}>{fmtDuration(step.duration_ms)}</span>
          )}
          {hasAnalysis && (
            <span className={styles.analysisIndicator} title="AI failure analysis available">
              <Bot size={11} aria-hidden />
            </span>
          )}
          <ChevronDown
            size={15}
            className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}
            aria-hidden
          />
        </div>
      </div>

      {open && (
        <div className={styles.stepBody}>
          {/* AI reasoning */}
          {step.ai_reasoning && (
            <p className={styles.stepAiReasoning}>
              <Bot size={12} style={{ verticalAlign: 'middle', marginRight: 5 }} aria-hidden />
              {step.ai_reasoning}
            </p>
          )}

          {/* Step logs */}
          {step.logs ? (
            <>
              <p className={styles.logsLabel}>Logs</p>
              <pre className={styles.logs}>{step.logs}</pre>
            </>
          ) : (
            <p className={styles.logsLabel}>No logs captured.</p>
          )}

          {/* Failure analysis panel (Phase 3) */}
          {(step.status === 'failure' || hasAnalysis) && (
            <FailureAnalysisPanel
              persistedAnalyses={step.failure_analyses}
              liveState={analysisState}
              attempt={step.attempt}
            />
          )}
        </div>
      )}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PipelineRunPage() {
  const { projectId = '', runId = '' } = useParams<{ projectId: string; runId: string }>()
  const navigate = useNavigate()

  const [run, setRun] = useState<PipelineRunOut | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rerunning, setRerunning] = useState(false)
  // Per-step live analysis state map: stepKey → AnalysisState
  const [analysisStates, setAnalysisStates] = useState<Record<string, AnalysisState>>({})
  const cleanupRef = useRef<(() => void) | null>(null)

  const handleRerun = useCallback(async () => {
    if (rerunning) return
    setRerunning(true)
    setError(null)
    try {
      const newRun = await rerunPipelineRun(projectId, runId)
      // Navigate to the freshly created run so the user watches it live.
      navigate(`/projects/${projectId}/pipeline-runs/${newRun.id}`)
    } catch (err) {
      setError(msgFromError(err))
    } finally {
      setRerunning(false)
    }
  }, [projectId, runId, rerunning, navigate])

  const setStepAnalysis = useCallback((stepKey: string, state: AnalysisState) => {
    setAnalysisStates((prev) => ({ ...prev, [stepKey]: state }))
  }, [])

  // Merge incoming SSE events into local state
  const handleEvent = useCallback(
    (evt: PipelineEvent) => {
      // ── Phase 3 failure analysis events ────────────────────────────────────
      if (evt.type === 'step_analysis_started') {
        setStepAnalysis(evt.step_key, { phase: 'analyzing' })
        return
      }

      if (evt.type === 'step_analysis_complete') {
        setStepAnalysis(evt.step_key, {
          phase: 'done',
          analysis: {
            root_cause: evt.root_cause,
            confidence: evt.confidence,
            fix_strategy: evt.fix_strategy,
            is_auto_fixable: evt.is_auto_fixable,
            human_approval_required: evt.human_approval_required,
            risk_level: evt.risk_level,
          },
        })
        return
      }

      if (evt.type === 'step_fix_started') {
        setStepAnalysis(evt.step_key, { phase: 'fixing' })
        return
      }

      if (evt.type === 'step_fix_complete') {
        setAnalysisStates((prev) => {
          const existing = prev[evt.step_key]
          if (existing?.phase === 'done') {
            return {
              ...prev,
              [evt.step_key]: {
                ...existing,
                analysis: {
                  ...existing.analysis,
                  patch_summary: evt.patch_summary,
                },
              },
            }
          }
          return prev
        })
        return
      }

      if (evt.type === 'step_retry_started') {
        setStepAnalysis(evt.step_key, {
          phase: 'retrying',
          attempt: evt.attempt,
          reason: evt.reason,
        })
        return
      }

      if (evt.type === 'approval_required') {
        setStepAnalysis(evt.step_key, {
          phase: 'approval_required',
          root_cause: evt.root_cause,
          fix_strategy: evt.fix_strategy,
        })
        return
      }

      // ── Standard pipeline events ────────────────────────────────────────────
      setRun((prev) => {
        if (!prev) return prev

        if (evt.type === 'pipeline_snapshot') {
          if (evt.preview_url) setPreviewUrl(evt.preview_url)
          const merged = evt.steps.map((s) => {
            const existing = prev.steps.find((x) => x.step_key === s.step_key)
            return existing
              ? {
                  ...existing,
                  status: s.status as StepStatus,
                  duration_ms: s.duration_ms,
                  ai_reasoning: s.ai_reasoning,
                  logs: s.logs,
                }
              : {
                  id: s.step_key,
                  run_id: prev.id,
                  step_key: s.step_key,
                  status: s.status as StepStatus,
                  attempt: 1,
                  logs: s.logs,
                  ai_reasoning: s.ai_reasoning,
                  started_at: null,
                  completed_at: null,
                  duration_ms: s.duration_ms,
                  created_at: new Date().toISOString(),
                  failure_analyses: [],
                }
          })
          return { ...prev, status: evt.status as RunStatus, steps: merged }
        }

        if (evt.type === 'step_started') {
          const steps = prev.steps.map((s) =>
            s.step_key === evt.step_key ? { ...s, status: 'running' as StepStatus } : s,
          )
          return { ...prev, steps }
        }

        if (evt.type === 'step_completed') {
          // Clear live analysis state when step completes (success or final failure)
          if (evt.status !== 'failure') {
            setStepAnalysis(evt.step_key, { phase: 'idle' })
          }
          const steps = prev.steps.map((s) =>
            s.step_key === evt.step_key
              ? {
                  ...s,
                  status: evt.status as StepStatus,
                  duration_ms: evt.duration_ms,
                  ai_reasoning: evt.ai_reasoning,
                  attempt: evt.attempt ?? s.attempt,
                }
              : s,
          )
          return { ...prev, steps }
        }

        if (evt.type === 'pipeline_completed' || evt.type === 'pipeline_failed') {
          if (evt.preview_url) setPreviewUrl(evt.preview_url)
          return { ...prev, status: evt.status as RunStatus, ai_summary: evt.ai_summary }
        }

        return prev
      })
    },
    [setStepAnalysis],
  )

  // Load (or reload) the run whenever runId changes.
  // Reset all local state first so navigating to a new run (e.g. after
  // "Chạy lại") never shows stale content or the old run's dark log panels.
  useEffect(() => {
    setRun(null)
    setError(null)
    setLoading(true)
    setPreviewUrl(null)
    setAnalysisStates({})

    let cancelled = false
    void (async () => {
      try {
        const data = await getPipelineRun(runId)
        if (!cancelled) setRun(data)
      } catch (err) {
        if (!cancelled) setError(msgFromError(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [runId])

  // Subscribe to SSE once the run is loaded and is still active.
  // Guard on run.id (not run.status alone) so that navigating to a fresh
  // re-run — which briefly keeps the old run in state — does NOT skip the
  // subscription because the old run had status 'failure'.
  useEffect(() => {
    if (!run) return
    // Only subscribe for the run that matches the current URL param.
    // If the state still holds the previous run (while the new fetch is in
    // flight after a re-run navigate), skip until the state is updated.
    if (run.id !== runId) return
    if (run.status === 'success' || run.status === 'failure' || run.status === 'cancelled') return

    cleanupRef.current = subscribePipelineRun(runId, handleEvent)
    return () => {
      cleanupRef.current?.()
    }
  }, [run?.id, run?.status, runId, handleEvent]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <Spinner /> Loading pipeline run…
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.error}>{error}</div>
      </div>
    )
  }

  // run is null only during the brief window between resetting state and the
  // fetch completing. Show the same spinner instead of an empty screen.
  if (!run) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <Spinner /> Loading pipeline run…
        </div>
      </div>
    )
  }

  const durationMs =
    run.started_at && run.completed_at
      ? new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()
      : null

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <div className={styles.breadcrumb}>
        <Link to={`/projects/${projectId}`} className={styles.breadcrumbLink}>
          Project
        </Link>
        <span>›</span>
        <Link to={`/projects/${projectId}/pipelines`} className={styles.breadcrumbLink}>
          Pipelines
        </Link>
        <span>›</span>
        <span>{run.task_title ?? `Run ${run.id.slice(0, 8)}`}</span>
      </div>

      {/* Header */}
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            <Workflow size={22} aria-hidden />
            {run.task_title ? `Pipeline: ${run.task_title}` : 'Pipeline Run'}
          </h1>
          <div className={styles.headerActions}>
            <RunStatusBadge status={run.status} />
            <button
              type="button"
              className={styles.rerunButton}
              onClick={handleRerun}
              disabled={rerunning || run.status === 'running' || run.status === 'queued'}
              title="Chạy lại pipeline cho task này"
            >
              {rerunning ? (
                <Loader2 size={14} className="animate-spin" aria-hidden />
              ) : (
                <RotateCcw size={14} aria-hidden />
              )}
              {rerunning ? 'Đang chạy lại…' : 'Chạy lại'}
            </button>
          </div>
        </div>
        <div className={styles.metaRow}>
          {run.branch_name && (
            <span className={styles.metaItem}>
              <GitBranch size={12} aria-hidden />
              {run.branch_name}
            </span>
          )}
          {run.commit_sha && (
            <span className={styles.metaItem}>
              <Terminal size={12} aria-hidden />
              {run.commit_sha.slice(0, 7)}
            </span>
          )}
          {run.triggered_by && (
            <span className={styles.metaItem}>Triggered by: {run.triggered_by}</span>
          )}
          {run.started_at && (
            <span className={styles.metaItem}>Started: {fmtTime(run.started_at)}</span>
          )}
          {durationMs != null && (
            <span className={styles.metaItem}>Duration: {fmtDuration(durationMs)}</span>
          )}
        </div>
      </header>

      {/* AI summary */}
      {run.ai_summary && (
        <div className={styles.aiSummaryCard}>
          <Bot size={16} className={styles.aiSummaryIcon} aria-hidden />
          <p className={styles.aiSummaryText}>{run.ai_summary}</p>
        </div>
      )}

      {/* Preview deployment URL */}
      {previewUrl && (
        <div className={styles.previewBanner}>
          <Rocket size={15} className={styles.previewBannerIcon} aria-hidden />
          <span className={styles.previewBannerLabel}>Preview deployment ready</span>
          <a
            href={previewUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.previewBannerLink}
          >
            {previewUrl}
            <ExternalLink size={12} aria-hidden />
          </a>
        </div>
      )}

      {/* Steps */}
      <div className={styles.stepsCard}>
        <div className={styles.stepsHeader}>Pipeline Steps</div>
        {run.steps.length === 0 ? (
          <div style={{ padding: '16px', color: 'var(--font-secondary-color)', fontSize: 13 }}>
            Steps initializing…
          </div>
        ) : (
          run.steps.map((step) => (
            <StepRow
              key={step.id}
              step={step}
              analysisState={analysisStates[step.step_key] ?? { phase: 'idle' }}
            />
          ))
        )}
      </div>
    </div>
  )
}
