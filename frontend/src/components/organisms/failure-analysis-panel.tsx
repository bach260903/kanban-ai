/**
 * FailureAnalysisPanel — shows AI root cause, confidence, fix strategy,
 * and retry history for a failed pipeline step.
 *
 * Used inside StepRow (pipeline-run.tsx) when a step has failed.
 */

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  Loader2,
  RefreshCw,
  ShieldAlert,
  Wrench,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'

import type { FailureAnalysisOut } from '../../services/pipeline-api'
import styles from './failure-analysis-panel.module.css'

// ── Types ─────────────────────────────────────────────────────────────────────

type LiveAnalysis = {
  root_cause: string
  confidence: number
  fix_strategy: string
  is_auto_fixable: boolean
  human_approval_required: boolean
  risk_level: string
  patch_summary?: string
  retry_attempt?: number
}

type AnalysisState =
  | { phase: 'idle' }
  | { phase: 'analyzing' }
  | { phase: 'fixing' }
  | { phase: 'retrying'; attempt: number; reason: string }
  | { phase: 'approval_required'; root_cause: string; fix_strategy: string }
  | { phase: 'done'; analysis: LiveAnalysis }

export type { LiveAnalysis, AnalysisState }

// ── Confidence bar ────────────────────────────────────────────────────────────

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const cls =
    score >= 0.8 ? styles.confHigh : score >= 0.5 ? styles.confMed : styles.confLow
  return (
    <div className={styles.confRow} title={`AI confidence: ${pct}%`}>
      <span className={styles.confLabel}>Confidence</span>
      <div className={styles.confTrack}>
        <div className={`${styles.confFill} ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={styles.confPct}>{pct}%</span>
    </div>
  )
}

// ── Risk badge ────────────────────────────────────────────────────────────────

function RiskBadge({ level }: { level: string }) {
  const map: Record<string, { cls: string; label: string }> = {
    low:    { cls: styles.riskLow,  label: 'Low risk' },
    medium: { cls: styles.riskMed,  label: 'Medium risk' },
    high:   { cls: styles.riskHigh, label: 'High risk' },
  }
  const { cls, label } = map[level] ?? map.medium
  return <span className={`${styles.riskBadge} ${cls}`}>{label}</span>
}

// ── Persisted analysis card (from DB) ─────────────────────────────────────────

function PersistedAnalysisCard({ fa }: { fa: FailureAnalysisOut }) {
  const [open, setOpen] = useState(false)

  return (
    <div className={styles.persistedCard}>
      <div
        className={styles.persistedHeader}
        onClick={() => setOpen((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && setOpen((v) => !v)}
        aria-expanded={open}
      >
        <Bot size={13} className={styles.persistedIcon} aria-hidden />
        <span className={styles.persistedTitle}>AI Analysis</span>
        <span className={styles.persistedRoot}>{fa.root_cause}</span>
        <ChevronDown
          size={13}
          className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}
          aria-hidden
        />
      </div>

      {open && (
        <div className={styles.persistedBody}>
          <ConfidenceBar score={fa.confidence} />
          <RiskBadge level={fa.risk_level} />

          <div className={styles.section}>
            <p className={styles.sectionLabel}>Root cause</p>
            <p className={styles.sectionText}>{fa.root_cause}</p>
          </div>

          <div className={styles.section}>
            <p className={styles.sectionLabel}>Fix strategy</p>
            <p className={styles.sectionText}>{fa.fix_strategy}</p>
          </div>

          <div className={styles.pills}>
            {fa.is_auto_fixable && (
              <span className={styles.pillGreen}>
                <Wrench size={10} aria-hidden /> Auto-fixable
              </span>
            )}
            {fa.human_approval_required && (
              <span className={styles.pillYellow}>
                <ShieldAlert size={10} aria-hidden /> Approval required
              </span>
            )}
            {fa.patch_applied && (
              <span className={styles.pillGreen}>
                <CheckCircle2 size={10} aria-hidden /> Patch applied
              </span>
            )}
            {fa.retry_triggered && (
              <span className={styles.pillBlue}>
                <RefreshCw size={10} aria-hidden /> Retried (attempt {fa.retry_attempt})
              </span>
            )}
          </div>

          {fa.patch_summary && (
            <div className={styles.patchBox}>
              <p className={styles.sectionLabel}>Patch summary</p>
              <p className={styles.patchText}>{fa.patch_summary}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Live analysis state card (from SSE) ──────────────────────────────────────

function LiveAnalysisCard({ state }: { state: AnalysisState }) {
  if (state.phase === 'idle') return null

  if (state.phase === 'analyzing') {
    return (
      <div className={`${styles.liveCard} ${styles.liveAnalyzing}`}>
        <Loader2 size={13} className={styles.spin} aria-hidden />
        <span>AI is analyzing the failure…</span>
      </div>
    )
  }

  if (state.phase === 'fixing') {
    return (
      <div className={`${styles.liveCard} ${styles.liveFixing}`}>
        <Loader2 size={13} className={styles.spin} aria-hidden />
        <span>Applying AI-generated patch…</span>
      </div>
    )
  }

  if (state.phase === 'retrying') {
    return (
      <div className={`${styles.liveCard} ${styles.liveRetrying}`}>
        <RefreshCw size={13} className={styles.spin} aria-hidden />
        <span>Retrying (attempt {state.attempt}) — {state.reason}</span>
      </div>
    )
  }

  if (state.phase === 'approval_required') {
    return (
      <div className={`${styles.liveCard} ${styles.liveApproval}`}>
        <ShieldAlert size={14} aria-hidden />
        <div>
          <p className={styles.approvalTitle}>Human approval required</p>
          <p className={styles.approvalCause}>{state.root_cause}</p>
          <p className={styles.approvalStrategy}>{state.fix_strategy}</p>
        </div>
      </div>
    )
  }

  if (state.phase === 'done') {
    const a = state.analysis
    return (
      <div className={`${styles.liveCard} ${styles.liveDone}`}>
        <div className={styles.liveDoneHeader}>
          <Bot size={13} className={styles.liveIcon} aria-hidden />
          <span className={styles.liveDoneTitle}>AI Analysis complete</span>
          <RiskBadge level={a.risk_level} />
        </div>
        <ConfidenceBar score={a.confidence} />
        <p className={styles.liveCause}>{a.root_cause}</p>
        <p className={styles.liveStrategy}>{a.fix_strategy}</p>
        <div className={styles.pills}>
          {a.is_auto_fixable && (
            <span className={styles.pillGreen}><Wrench size={10} /> Auto-fixable</span>
          )}
          {a.human_approval_required && (
            <span className={styles.pillYellow}><ShieldAlert size={10} /> Approval required</span>
          )}
          {a.patch_summary && (
            <span className={styles.pillGreen}><CheckCircle2 size={10} /> Patch applied</span>
          )}
          {a.retry_attempt != null && a.retry_attempt > 0 && (
            <span className={styles.pillBlue}><RefreshCw size={10} /> Retry scheduled</span>
          )}
        </div>
      </div>
    )
  }

  return null
}

// ── Retry timeline ────────────────────────────────────────────────────────────

function RetryTimeline({ attempt }: { attempt: number }) {
  if (attempt <= 1) return null
  return (
    <div className={styles.retryTimeline}>
      <div className={styles.retryDot} data-success="false" title="Original attempt (failed)" />
      <div className={styles.retryLine} />
      <Bot size={12} className={styles.retryBotIcon} title="AI intervened" aria-hidden />
      <div className={styles.retryLine} />
      {attempt >= 2 && (
        <div className={styles.retryDot} data-attempt="2" title={`Attempt ${attempt}`} />
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type Props = {
  /** Persisted analyses loaded from DB */
  persistedAnalyses?: FailureAnalysisOut[]
  /** Live state from SSE stream */
  liveState?: AnalysisState
  /** Step attempt count (for retry timeline) */
  attempt?: number
}

export function FailureAnalysisPanel({
  persistedAnalyses = [],
  liveState = { phase: 'idle' },
  attempt = 1,
}: Props) {
  const hasContent =
    persistedAnalyses.length > 0 ||
    liveState.phase !== 'idle'

  if (!hasContent) return null

  return (
    <div className={styles.panel}>
      <div className={styles.panelLabel}>
        <AlertTriangle size={12} aria-hidden />
        Failure Analysis
      </div>

      {/* Live state (SSE) */}
      <LiveAnalysisCard state={liveState} />

      {/* Retry timeline indicator */}
      <RetryTimeline attempt={attempt} />

      {/* Persisted analyses from DB */}
      {persistedAnalyses.map((fa) => (
        <PersistedAnalysisCard key={fa.id} fa={fa} />
      ))}
    </div>
  )
}
