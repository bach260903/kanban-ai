import { isAxiosError } from 'axios'
import { AlertTriangle, LayoutDashboard, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { getDashboard, type DashboardResponse } from '../services/analytics-api'
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

export default function DashboardPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
          <LayoutDashboard
            size={28}
            aria-hidden="true"
            style={{ verticalAlign: 'middle', marginRight: 8 }}
          />
          Dashboard
        </h1>
        <p className={styles.sub}>Tổng quan project và tiến độ task của bạn.</p>
      </header>

      {error ? <div className={styles.banner}>{error}</div> : null}

      {loading ? (
        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
          aria-busy="true"
          aria-label="Loading dashboard"
        >
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={`${styles.skeleton} animate-pulse`} />
          ))}
        </div>
      ) : cards.length === 0 && !error ? (
        <div className={styles.empty}>
          <p>Chưa có project nào</p>
          <Link to="/projects" className={styles.emptyLink}>
            Tạo project đầu tiên →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((project) => {
            const counts = project.task_counts ?? {}
            return (
              <article key={project.id} className={styles.card}>
                <Link
                  to={`/projects/${project.id}`}
                  className={styles.cardLink}
                  aria-label={`Open project ${project.name}`}
                />
                <div className={styles.cardHeader}>
                  <h2 className={styles.cardTitle}>{project.name}</h2>
                  <span className={styles.langBadge}>{project.primary_language}</span>
                </div>

                <div className={styles.pills}>
                  <span className={`${styles.pill} ${styles.pillTodo}`}>
                    Todo: {counts.todo ?? 0}
                  </span>
                  <span className={`${styles.pill} ${styles.pillProgress}`}>
                    In progress: {counts.in_progress ?? 0}
                  </span>
                  <span className={`${styles.pill} ${styles.pillReview}`}>
                    Review: {counts.review ?? 0}
                  </span>
                  <span className={`${styles.pill} ${styles.pillDone}`}>
                    Done: {counts.done ?? 0}
                  </span>
                </div>

                {project.stale_count > 0 ? (
                  <p className={styles.staleWarning}>
                    <AlertTriangle
                      size={14}
                      aria-hidden="true"
                      style={{ verticalAlign: 'text-bottom', marginRight: 4 }}
                    />
                    {project.stale_count} task chờ review quá 24h
                  </p>
                ) : null}

                <p className={styles.memberCount}>
                  <Users
                    size={14}
                    aria-hidden="true"
                    style={{ verticalAlign: 'text-bottom', marginRight: 4 }}
                  />
                  {project.member_count} thành viên
                </p>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
