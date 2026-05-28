import { isAxiosError } from 'axios'
import { AlertTriangle, Bot, Eye, LayoutDashboard, RefreshCw, Users, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import {
  getAIProjectReview,
  getDashboard,
  type AIReviewResponse,
  type DashboardResponse,
  type ProjectDashboard,
} from '../services/analytics-api'
import { showSuccessToast } from '../lib/toast'

import styles from './dashboard.module.css'

function messageFromUnknown(err: unknown): string {
  if (isAxiosError(err)) {
    if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
      return 'Backend không phản hồi. Kiểm tra server và thử lại.'
    }
    const detail = (err.response?.data as { detail?: string })?.detail
    if (typeof detail === 'string') return detail
    return err.message || 'Request failed'
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

// ── AI Review Modal ───────────────────────────────────────────────────────────

type AIReviewModalProps = {
  project: ProjectDashboard
  onClose: () => void
}

function AIReviewModal({ project, onClose }: AIReviewModalProps) {
  const [review, setReview] = useState<AIReviewResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const backdropRef = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAIProjectReview(String(project.id))
      setReview(data)
    } catch (err) {
      setError(messageFromUnknown(err))
    } finally {
      setLoading(false)
    }
  }, [project.id])

  useEffect(() => {
    void load()
  }, [load])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      ref={backdropRef}
      className={styles.modalBackdrop}
      onClick={(e) => { if (e.target === backdropRef.current) onClose() }}
    >
      <div className={styles.modal} role="dialog" aria-modal="true" aria-label={`AI review: ${project.name}`}>
        {/* Header */}
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <Bot size={16} aria-hidden="true" />
            <span>AI tổng quan — <strong>{project.name}</strong></span>
          </div>
          <button type="button" className={styles.modalClose} onClick={onClose} aria-label="Đóng">
            <X size={16} />
          </button>
        </div>

        {/* Task stats strip */}
        <div className={styles.modalStats}>
          {[
            { label: 'Todo',       key: 'todo',        cls: styles.pillTodo },
            { label: 'Đang làm',   key: 'in_progress', cls: styles.pillProgress },
            { label: 'Review',     key: 'review',      cls: styles.pillReview },
            { label: 'Done',       key: 'done',        cls: styles.pillDone },
            { label: 'Rejected',   key: 'rejected',    cls: styles.pillRejected },
          ].map(({ label, key, cls }) => (
            <span key={key} className={`${styles.pill} ${cls}`}>
              {label}: {project.task_counts?.[key] ?? 0}
            </span>
          ))}
        </div>

        {/* AI summary */}
        <div className={styles.modalBody}>
          {loading ? (
            <div className={styles.modalLoading}>
              <Spinner aria-label="AI đang phân tích…" />
              <span>AI đang phân tích dự án…</span>
            </div>
          ) : error ? (
            <p className={styles.modalError}>{error}</p>
          ) : (
            <p className={styles.modalSummary}>{review?.summary}</p>
          )}

          {/* Active tasks */}
          {!loading && !error && review && review.active_tasks.length > 0 && (
            <div className={styles.modalActiveTasks}>
              <p className={styles.modalActiveTitle}>
                ⚙️ Đang xử lý ({review.active_tasks.length} task)
              </p>
              <ul className={styles.modalActiveList}>
                {review.active_tasks.map((t) => (
                  <li key={t.task_id} className={styles.modalActiveItem}>
                    <span className={styles.aiActiveDot} />
                    {t.task_title}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!loading && review && (
            <p className={styles.modalFooter}>Cập nhật lúc {formatTime(review.generated_at)}</p>
          )}
        </div>

        {/* Refresh */}
        <div className={styles.modalActions}>
          <button
            type="button"
            className={styles.aiReviewRefresh}
            disabled={loading}
            onClick={() => void load()}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
            {loading ? 'Đang phân tích…' : 'Làm mới'}
          </button>
          <Link to={`/projects/${project.id}`} className={styles.openProjectLink}>
            Mở project →
          </Link>
        </div>
      </div>
    </div>
  )
}

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reviewProject, setReviewProject] = useState<ProjectDashboard | null>(null)

  useEffect(() => {
    const toast = (location.state as { toast?: string } | null)?.toast
    if (toast) {
      showSuccessToast(toast)
      navigate(location.pathname, { replace: true, state: {} })
    }
  }, [location.pathname, location.state, navigate])

  useEffect(() => {
    const ac = new AbortController()
    void (async () => {
      setLoading(true)
      setError(null)
      try {
        const dashboard = await getDashboard({ signal: ac.signal })
        if (ac.signal.aborted) return
        setData(dashboard)
      } catch (err) {
        if (ac.signal.aborted) return
        setError(messageFromUnknown(err))
      } finally {
        if (!ac.signal.aborted) setLoading(false)
      }
    })()
    return () => ac.abort()
  }, [])

  const cards = data?.projects ?? []

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>
          <LayoutDashboard size={28} aria-hidden="true" style={{ verticalAlign: 'middle', marginRight: 8 }} />
          Dashboard
        </h1>
        <p className={styles.sub}>Tổng quan project và tiến độ task của bạn.</p>
      </header>

      {error ? <div className={styles.banner}>{error}</div> : null}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" aria-busy="true">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={`${styles.skeleton} animate-pulse`} />
          ))}
        </div>
      ) : cards.length === 0 && !error ? (
        <div className={styles.empty}>
          <p>Chưa có project nào</p>
          <Link to="/projects" className={styles.emptyLink}>Tạo project đầu tiên →</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((project) => {
            const counts = project.task_counts ?? {}
            return (
              <article key={project.id} className={styles.card}>
                {/* Clickable overlay to open project (z-index below eye button) */}
                <Link
                  to={`/projects/${project.id}`}
                  className={styles.cardLink}
                  aria-label={`Open project ${project.name}`}
                />
                <div className={styles.cardHeader}>
                  <h2 className={styles.cardTitle}>{project.name}</h2>
                  <div className={styles.cardHeaderRight}>
                    <span className={styles.langBadge}>{project.primary_language}</span>
                    {/* AI Review eye button */}
                    <button
                      type="button"
                      className={styles.eyeBtn}
                      title="AI tổng quan dự án"
                      onClick={(e) => {
                        e.preventDefault()
                        setReviewProject(project)
                      }}
                    >
                      <Eye size={15} aria-hidden="true" />
                    </button>
                  </div>
                </div>

                <div className={styles.pills}>
                  <span className={`${styles.pill} ${styles.pillTodo}`}>Todo: {counts.todo ?? 0}</span>
                  <span className={`${styles.pill} ${styles.pillProgress}`}>In progress: {counts.in_progress ?? 0}</span>
                  <span className={`${styles.pill} ${styles.pillReview}`}>Review: {counts.review ?? 0}</span>
                  <span className={`${styles.pill} ${styles.pillDone}`}>Done: {counts.done ?? 0}</span>
                </div>

                {project.stale_count > 0 ? (
                  <p className={styles.staleWarning}>
                    <AlertTriangle size={14} aria-hidden="true" style={{ verticalAlign: 'text-bottom', marginRight: 4 }} />
                    {project.stale_count} task chờ review quá 24h
                  </p>
                ) : null}

                <p className={styles.memberCount}>
                  <Users size={14} aria-hidden="true" style={{ verticalAlign: 'text-bottom', marginRight: 4 }} />
                  {project.member_count} thành viên
                </p>
              </article>
            )
          })}
        </div>
      )}

      {/* AI Review modal */}
      {reviewProject && (
        <AIReviewModal project={reviewProject} onClose={() => setReviewProject(null)} />
      )}
    </div>
  )
}
