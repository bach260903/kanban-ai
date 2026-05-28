/**
 * DeploymentHistoryPage — list of deployments for a project.
 * Route: /projects/:projectId/deployments
 */

import { isAxiosError } from 'axios'
import { CheckCircle2, ExternalLink, Rocket, XCircle, Clock, SkipForward } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Spinner } from '../../components/atoms/spinner'
import { listDeployments, type DeploymentOut } from '../../services/pipeline-api'
import styles from './deployment-history.module.css'

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' }) }
  catch { return '' }
}

function StatusBadge({ status }: { status: DeploymentOut['status'] }) {
  const map: Record<DeploymentOut['status'], { label: string; icon: React.ReactNode; cls: string }> = {
    pending:     { label: 'Pending',     icon: <Clock size={11} />,        cls: styles.badgePending },
    deploying:   { label: 'Deploying',   icon: <Rocket size={11} />,       cls: styles.badgeDeploying },
    healthy:     { label: 'Healthy',     icon: <CheckCircle2 size={11} />, cls: styles.badgeHealthy },
    degraded:    { label: 'Degraded',    icon: <XCircle size={11} />,      cls: styles.badgeDegraded },
    rolled_back: { label: 'Rolled Back', icon: <XCircle size={11} />,      cls: styles.badgeRolledBack },
    skipped:     { label: 'Skipped',     icon: <SkipForward size={11} />,  cls: styles.badgeSkipped },
  }
  const { label, icon, cls } = map[status] ?? map.skipped
  return <span className={`${styles.badge} ${cls}`}>{icon} {label}</span>
}

export default function DeploymentHistoryPage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const [deps, setDeps] = useState<DeploymentOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const data = await listDeployments(projectId)
        if (!cancelled) setDeps(data)
      } catch (err) {
        if (!cancelled) {
          const msg = isAxiosError(err)
            ? ((err.response?.data as { detail?: string })?.detail ?? err.message)
            : (err instanceof Error ? err.message : 'Error')
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
        <span>Deployments</span>
      </div>

      <header className={styles.header}>
        <h1 className={styles.title}>
          <Rocket size={22} aria-hidden />
          Deployment History
        </h1>
        <p className={styles.sub}>All deployment records linked to pipeline runs.</p>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      {loading ? (
        <div className={styles.loading}><Spinner /> Loading…</div>
      ) : deps.length === 0 ? (
        <div className={styles.empty}>
          <Rocket size={36} style={{ opacity: 0.3 }} />
          <p>No deployments yet.</p>
          <p style={{ fontSize: 13 }}>Deployments are created when pipeline runs complete.</p>
        </div>
      ) : (
        <div className={styles.table}>
          {deps.map((dep) => (
            <Link
              key={dep.id}
              to={`/projects/${projectId}/deployments/${dep.id}`}
              className={styles.row}
            >
              <div className={styles.rowLeft}>
                <StatusBadge status={dep.status} />
                <span className={styles.depId}>#{dep.id.slice(0, 8)}</span>
                {dep.run_id && (
                  <Link
                    to={`/projects/${projectId}/pipeline-runs/${dep.run_id}`}
                    className={styles.runLink}
                    onClick={(e) => e.stopPropagation()}
                  >
                    Run {dep.run_id.slice(0, 8)} ↗
                  </Link>
                )}
                {dep.preview_url && (
                  <a
                    href={dep.preview_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.previewLink}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink size={11} aria-hidden />
                    Preview
                  </a>
                )}
              </div>
              <div className={styles.rowRight}>
                {dep.risk_score != null && (
                  <span
                    className={styles.risk}
                    title={`Risk score: ${dep.risk_score}`}
                    style={{
                      color: dep.risk_score > 0.6 ? '#b91c1c' : dep.risk_score > 0.3 ? '#92400e' : '#15803d',
                    }}
                  >
                    Risk {(dep.risk_score * 100).toFixed(0)}%
                  </span>
                )}
                <span className={styles.time}>{fmtTime(dep.created_at)}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
