import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  XCircle,
  Zap,
} from 'lucide-react'

import {
  getHealthSummary,
  listIncidents,
  listRollbacks,
  type DeploymentHealthSummary,
  type IncidentOut,
  type RollbackEventOut,
} from '../../services/devops-api'
import styles from './health-dashboard.module.css'

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

function relFmt(iso: string | null): string {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function HealthStatusDot({ status }: { status: string | null }) {
  const cls =
    status === 'healthy' ? styles.dotGreen
    : status === 'degraded' ? styles.dotYellow
    : status === 'critical' ? styles.dotRed
    : styles.dotGray
  return <span className={`${styles.dot} ${cls}`} aria-label={status ?? 'unknown'} />
}

function SeverityBadge({ sev }: { sev: string }) {
  const cls =
    sev === 'critical' ? styles.sevCritical
    : sev === 'high' ? styles.sevHigh
    : sev === 'medium' ? styles.sevMedium
    : styles.sevLow
  return <span className={`${styles.sevBadge} ${cls}`}>{sev}</span>
}

function RollbackStatusBadge({ status }: { status: string }) {
  const cls =
    status === 'completed' ? styles.rbCompleted
    : status === 'failed' ? styles.rbFailed
    : status === 'rolling_back' ? styles.rbRolling
    : styles.rbOther
  return <span className={`${styles.rbBadge} ${cls}`}>{status.replace('_', ' ')}</span>
}

export default function HealthDashboardPage() {
  const { projectId } = useParams<{ projectId: string }>()

  const [summaries, setSummaries] = useState<DeploymentHealthSummary[]>([])
  const [incidents, setIncidents] = useState<IncidentOut[]>([])
  const [rollbacks, setRollbacks] = useState<RollbackEventOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    if (!projectId) return
    setLoading(true)
    setError(null)
    try {
      const [s, i, r] = await Promise.all([
        getHealthSummary(projectId),
        listIncidents(projectId, { limit: 30 }),
        listRollbacks(projectId, 20),
      ])
      setSummaries(s)
      setIncidents([...i].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99)))
      setRollbacks(r)
    } catch {
      setError('Failed to load DevOps health data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [projectId])

  // ── Loading / error ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loadingCenter}>
          <RefreshCw size={22} className={styles.spinIcon} />
          <span>Loading health data…</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <p className={styles.errorMsg}>{error}</p>
        <button className={styles.retryBtn} onClick={load}>Retry</button>
      </div>
    )
  }

  const openIncidents = incidents.filter(i => !i.resolved)
  const resolvedIncidents = incidents.filter(i => i.resolved)

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <nav className={styles.breadcrumb}>
        <Link to={`/projects/${projectId}`} className={styles.breadLink}>
          <ArrowLeft size={14} />
          Project
        </Link>
        <span className={styles.breadSep}>/</span>
        <span>DevOps Health</span>
      </nav>

      {/* Header */}
      <div className={styles.pageHeader}>
        <div className={styles.pageTitleRow}>
          <ShieldAlert size={22} className={styles.headerIcon} />
          <h1 className={styles.pageTitle}>DevOps Health</h1>
        </div>
        <button className={styles.refreshBtn} onClick={load}>
          <RefreshCw size={14} />
          Refresh
        </button>
      </div>

      {/* ── Deployment health grid ──────────────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Active Deployments</h2>
        {summaries.length === 0 ? (
          <p className={styles.empty}>No active deployments.</p>
        ) : (
          <div className={styles.deployGrid}>
            {summaries.map(s => (
              <Link
                key={s.deployment_id}
                to={`/projects/${projectId}/deployments/${s.deployment_id}`}
                className={styles.deployCard}
              >
                <div className={styles.deployCardHeader}>
                  <HealthStatusDot status={s.health_status} />
                  <span className={styles.deployId}>
                    {s.deployment_id.slice(0, 8)}…
                  </span>
                  {s.open_incidents > 0 && (
                    <span className={styles.incidentCount}>
                      <AlertTriangle size={11} />
                      {s.open_incidents}
                    </span>
                  )}
                </div>

                <dl className={styles.deployMeta}>
                  <dt>Status</dt>
                  <dd className={styles[`hs_${s.health_status ?? 'unknown'}`]}>
                    {s.health_status ?? 'unknown'}
                  </dd>

                  {s.latest_http_status !== null && (
                    <>
                      <dt>HTTP</dt>
                      <dd>{s.latest_http_status}</dd>
                    </>
                  )}

                  {s.latest_latency_ms !== null && (
                    <>
                      <dt>Latency</dt>
                      <dd>{s.latest_latency_ms} ms</dd>
                    </>
                  )}

                  <dt>Failures</dt>
                  <dd className={s.consecutive_failures > 0 ? styles.failureCount : ''}>
                    {s.consecutive_failures}
                  </dd>

                  <dt>Checked</dt>
                  <dd>{relFmt(s.last_checked_at)}</dd>
                </dl>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* ── Open incidents ─────────────────────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>
          Open Incidents
          {openIncidents.length > 0 && (
            <span className={styles.countPill}>{openIncidents.length}</span>
          )}
        </h2>
        {openIncidents.length === 0 ? (
          <div className={styles.allClearBanner}>
            <CheckCircle2 size={16} className={styles.checkIcon} />
            All systems healthy — no open incidents.
          </div>
        ) : (
          <ul className={styles.incidentList}>
            {openIncidents.map(inc => (
              <IncidentRow key={inc.id} incident={inc} />
            ))}
          </ul>
        )}
      </section>

      {/* ── Rollback timeline ──────────────────────────────────────────────── */}
      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Rollback History</h2>
        {rollbacks.length === 0 ? (
          <p className={styles.empty}>No rollbacks recorded.</p>
        ) : (
          <ul className={styles.rollbackList}>
            {rollbacks.map(rb => (
              <RollbackRow key={rb.id} event={rb} />
            ))}
          </ul>
        )}
      </section>

      {/* ── Resolved incidents (collapsed) ────────────────────────────────── */}
      {resolvedIncidents.length > 0 && (
        <section className={styles.section}>
          <details>
            <summary className={styles.resolvedSummary}>
              Resolved incidents ({resolvedIncidents.length})
            </summary>
            <ul className={styles.incidentList}>
              {resolvedIncidents.map(inc => (
                <IncidentRow key={inc.id} incident={inc} />
              ))}
            </ul>
          </details>
        </section>
      )}
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function IncidentRow({ incident }: { incident: IncidentOut }) {
  const [open, setOpen] = useState(false)
  const {
    incident_type, severity, title, description, ai_reasoning,
    rollback_triggered, resolved, created_at, resolved_at, risk_score,
  } = incident

  return (
    <li className={`${styles.incidentItem} ${resolved ? styles.incidentResolved : ''}`}>
      <div className={styles.incidentHeader} onClick={() => setOpen(o => !o)}>
        <SeverityBadge sev={severity} />
        <span className={styles.incidentType}>{incident_type.replace('_', ' ')}</span>
        <span className={styles.incidentTitle}>{title}</span>
        <div className={styles.incidentMeta}>
          {rollback_triggered && (
            <span className={styles.rbPill}>
              <RotateCcw size={10} /> Rolled back
            </span>
          )}
          {resolved && (
            <span className={styles.resolvedPill}>
              <CheckCircle2 size={10} /> Resolved
            </span>
          )}
          {risk_score !== null && (
            <span className={styles.riskPill}>
              risk {(risk_score * 100).toFixed(0)}%
            </span>
          )}
          <span className={styles.incidentTime}>{relFmt(created_at)}</span>
        </div>
        <span className={styles.chevron}>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div className={styles.incidentBody}>
          <p className={styles.incidentDesc}>{description}</p>
          {ai_reasoning && (
            <div className={styles.aiReasoning}>
              <span className={styles.aiLabel}>AI Reasoning</span>
              <p>{ai_reasoning}</p>
            </div>
          )}
          {resolved_at && (
            <p className={styles.resolvedAt}>
              <CheckCircle2 size={12} className={styles.checkIcon} />
              Resolved {relFmt(resolved_at)}
            </p>
          )}
        </div>
      )}
    </li>
  )
}

function RollbackRow({ event }: { event: RollbackEventOut }) {
  const [open, setOpen] = useState(false)
  const { triggered_by, status, reason, ai_reasoning, created_at, completed_at } = event

  return (
    <li className={styles.rollbackItem}>
      <div className={styles.rollbackHeader} onClick={() => setOpen(o => !o)}>
        <RotateCcw size={14} className={styles.rbIcon} />
        <RollbackStatusBadge status={status} />
        <span className={styles.rbTrigger}>{triggered_by.replace('_', ' ')}</span>
        <span className={styles.rbTime}>{relFmt(created_at)}</span>
        {completed_at && (
          <span className={styles.rbDuration}>
            <Clock size={11} />
            {Math.round((new Date(completed_at).getTime() - new Date(created_at).getTime()) / 1000)}s
          </span>
        )}
        <span className={styles.chevron}>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div className={styles.rollbackBody}>
          <p className={styles.rbReason}><strong>Reason:</strong> {reason}</p>
          {ai_reasoning && (
            <div className={styles.aiReasoning}>
              <span className={styles.aiLabel}>AI Reasoning</span>
              <p>{ai_reasoning}</p>
            </div>
          )}
        </div>
      )}
    </li>
  )
}
