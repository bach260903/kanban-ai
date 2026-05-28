/**
 * DeploymentDetailPage — detailed view of a single deployment.
 *
 * Route: /projects/:projectId/deployments/:deploymentId
 *
 * Shows: status, provider, environment, branch/commit, preview URL,
 *        deploy logs, error message, risk score, AI summary (via pipeline run),
 *        link to source pipeline run.
 */

import { isAxiosError } from 'axios'
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  ExternalLink,
  GitBranch,
  Rocket,
  SkipForward,
  Terminal,
  XCircle,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../../components/atoms/spinner'
import { getDeployment, type DeploymentOut } from '../../services/pipeline-api'
import styles from './deployment-detail.module.css'

// ── helpers ──────────────────────────────────────────────────────────────────

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'medium' })
  } catch {
    return iso
  }
}

function fmtDuration(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function msgFromError(err: unknown): string {
  if (isAxiosError(err)) return (err.response?.data as { detail?: string })?.detail ?? err.message
  if (err instanceof Error) return err.message
  return 'Unknown error'
}

// ── Status badge ─────────────────────────────────────────────────────────────

type DepStatus = DeploymentOut['status']

function StatusBadge({ status }: { status: DepStatus }) {
  const map: Record<DepStatus, { label: string; icon: React.ReactNode; cls: string }> = {
    pending:     { label: 'Pending',     icon: <Clock size={12} />,        cls: styles.badgePending },
    deploying:   { label: 'Deploying',   icon: <Rocket size={12} />,       cls: styles.badgeDeploying },
    healthy:     { label: 'Healthy',     icon: <CheckCircle2 size={12} />, cls: styles.badgeHealthy },
    degraded:    { label: 'Degraded',    icon: <XCircle size={12} />,      cls: styles.badgeDegraded },
    rolled_back: { label: 'Rolled Back', icon: <AlertTriangle size={12} />, cls: styles.badgeRolledBack },
    skipped:     { label: 'Skipped',     icon: <SkipForward size={12} />,  cls: styles.badgeSkipped },
  }
  const { label, icon, cls } = map[status] ?? map.skipped
  return (
    <span className={`${styles.badge} ${cls}`}>
      {icon}
      {label}
    </span>
  )
}

// ── Risk badge ────────────────────────────────────────────────────────────────

function RiskBadge({ score }: { score: number }) {
  const pct = (score * 100).toFixed(0)
  const cls = score > 0.6
    ? styles.riskHigh
    : score > 0.3
    ? styles.riskMed
    : styles.riskLow
  return <span className={`${styles.riskBadge} ${cls}`}>Risk {pct}%</span>
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DeploymentDetailPage() {
  const { projectId = '', deploymentId = '' } = useParams<{ projectId: string; deploymentId: string }>()
  const [dep, setDep] = useState<DeploymentOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const data = await getDeployment(projectId, deploymentId)
        if (!cancelled) setDep(data)
      } catch (err) {
        if (!cancelled) setError(msgFromError(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId, deploymentId])

  if (loading) {
    return (
      <div className={styles.page}>
        <div className={styles.loading}><Spinner /> Loading deployment…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>{error}</div>
      </div>
    )
  }

  if (!dep) return null

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <div className={styles.breadcrumb}>
        <Link to={`/projects/${projectId}`} className={styles.breadcrumbLink}>Project</Link>
        <span>›</span>
        <Link to={`/projects/${projectId}/deployments`} className={styles.breadcrumbLink}>Deployments</Link>
        <span>›</span>
        <span>{dep.id.slice(0, 8)}</span>
      </div>

      {/* Header */}
      <header className={styles.header}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            <Rocket size={22} aria-hidden />
            Deployment
          </h1>
          <StatusBadge status={dep.status} />
          {dep.risk_score != null && <RiskBadge score={dep.risk_score} />}
        </div>
        <p className={styles.depId}>ID: {dep.id}</p>
      </header>

      {/* Preview URL */}
      {dep.preview_url && (
        <div className={styles.previewBanner}>
          <CheckCircle2 size={15} className={styles.previewIcon} aria-hidden />
          <span className={styles.previewLabel}>Preview URL</span>
          <a
            href={dep.preview_url}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.previewLink}
          >
            {dep.preview_url}
            <ExternalLink size={12} aria-hidden />
          </a>
        </div>
      )}

      {/* Metadata grid */}
      <div className={styles.metaGrid}>
        <MetaRow label="Provider" value={dep.provider ?? '—'} />
        <MetaRow label="Environment" value={dep.environment ?? '—'} />
        {dep.branch_name && (
          <MetaRow
            label="Branch"
            value={
              <span className={styles.metaCode}>
                <GitBranch size={12} aria-hidden />
                {dep.branch_name}
              </span>
            }
          />
        )}
        {dep.commit_sha && (
          <MetaRow
            label="Commit"
            value={
              <span className={styles.metaCode}>
                <Terminal size={12} aria-hidden />
                {dep.commit_sha.slice(0, 7)}
              </span>
            }
          />
        )}
        {dep.external_id && (
          <MetaRow label="External ID" value={<span className={styles.metaCode}>{dep.external_id}</span>} />
        )}
        <MetaRow label="Duration" value={fmtDuration(dep.duration_ms)} />
        <MetaRow label="Deployed at" value={fmtTime(dep.deployed_at)} />
        <MetaRow label="Created at" value={fmtTime(dep.created_at)} />
        {dep.run_id && (
          <MetaRow
            label="Pipeline run"
            value={
              <Link
                to={`/projects/${projectId}/pipeline-runs/${dep.run_id}`}
                className={styles.runLink}
              >
                Run {dep.run_id.slice(0, 8)} ↗
              </Link>
            }
          />
        )}
      </div>

      {/* Error message */}
      {dep.error_message && (
        <div className={styles.errorCard}>
          <div className={styles.cardTitle}>
            <XCircle size={14} aria-hidden />
            Deployment Error
          </div>
          <pre className={styles.errorPre}>{dep.error_message}</pre>
        </div>
      )}

      {/* Deploy logs */}
      {dep.deploy_logs && (
        <div className={styles.logsCard}>
          <div className={styles.cardTitle}>
            <Terminal size={14} aria-hidden />
            Deploy Logs
          </div>
          <pre className={styles.logs}>{dep.deploy_logs}</pre>
        </div>
      )}

      {!dep.deploy_logs && !dep.error_message && (
        <div className={styles.noLogs}>
          <Bot size={24} style={{ opacity: 0.25 }} />
          <p>No logs available for this deployment.</p>
        </div>
      )}
    </div>
  )
}

// ── MetaRow helper ────────────────────────────────────────────────────────────

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className={styles.metaLabel}>{label}</dt>
      <dd className={styles.metaValue}>{value}</dd>
    </>
  )
}
