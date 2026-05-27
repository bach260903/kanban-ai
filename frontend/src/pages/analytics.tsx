import { isAxiosError } from 'axios'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Avatar } from '../components/atoms/avatar'
import {
  getProjectAnalytics,
  type AnalyticsRange,
  type AnalyticsResponse,
} from '../services/analytics-api'

import styles from './analytics.module.css'

function messageFromUnknown(err: unknown): string {
  if (isAxiosError(err)) {
    if (err.response?.status === 403) {
      return 'Bạn không có quyền xem analytics. Chỉ Leader hoặc Owner mới truy cập được.'
    }
    const detail = (err.response?.data as { detail?: string })?.detail
    if (typeof detail === 'string') return detail
    return err.message || 'Request failed'
  }
  if (err instanceof Error) return err.message
  return 'Something went wrong'
}

function formatAgentLabel(agentType: string): string {
  return agentType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function AnalyticsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [range, setRange] = useState<AnalyticsRange>('7d')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [customHint, setCustomHint] = useState<string | null>(null)

  const canFetchCustom = range !== 'custom' || (fromDate !== '' && toDate !== '')

  useEffect(() => {
    const ac = new AbortController()
    void (async () => {
      if (!projectId) return
      if (!canFetchCustom) {
        setLoading(false)
        setError(null)
        setData(null)
        setCustomHint('Chọn ngày bắt đầu và kết thúc để xem analytics.')
        return
      }
      if (range === 'custom' && fromDate > toDate) {
        setLoading(false)
        setData(null)
        setCustomHint(null)
        setError('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.')
        return
      }
      setCustomHint(null)
      setLoading(true)
      setError(null)
      try {
        const fromIso = range === 'custom' && fromDate ? `${fromDate}T00:00:00Z` : undefined
        const toIso = range === 'custom' && toDate ? `${toDate}T23:59:59Z` : undefined
        const result = await getProjectAnalytics(projectId, range, fromIso, toIso, {
          signal: ac.signal,
        })
        if (ac.signal.aborted) return
        setData(result)
      } catch (err) {
        if (ac.signal.aborted) return
        setData(null)
        setError(messageFromUnknown(err))
      } finally {
        if (!ac.signal.aborted) setLoading(false)
      }
    })()
    return () => ac.abort()
  }, [projectId, range, fromDate, toDate, canFetchCustom])

  const barData = useMemo(
    () =>
      (data?.by_backend ?? []).map((row) => ({
        name: formatAgentLabel(row.agent_type),
        avg_seconds: Math.round(row.avg_seconds),
        agent_type: row.agent_type,
      })),
    [data],
  )

  const approveRateData = useMemo(
    () =>
      (data?.by_backend ?? []).map((row) => ({
        name: formatAgentLabel(row.agent_type),
        rate: Math.round(row.first_approve_rate * 100),
      })),
    [data],
  )

  if (!projectId) {
    return (
      <div className={styles.page}>
        <p className={styles.banner}>Thiếu project ID.</p>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <Link to={`/projects/${projectId}`} className={styles.backLink}>
        ← Quay lại workspace
      </Link>

      <header className={styles.header}>
        <h1 className={styles.title}>Analytics</h1>
        <p className={styles.sub}>Hiệu suất agent và thành viên theo khoảng thời gian.</p>
      </header>

      <div className={styles.rangeRow}>
        {(['7d', '30d', 'custom'] as const).map((r) => (
          <button
            key={r}
            type="button"
            className={`${styles.rangeBtn} ${range === r ? styles.rangeBtnActive : ''}`}
            onClick={() => setRange(r)}
          >
            {r === '7d' ? '7 ngày' : r === '30d' ? '30 ngày' : 'Tùy chọn'}
          </button>
        ))}
        {range === 'custom' ? (
          <div className={styles.customDates}>
            <input
              type="date"
              className={styles.dateInput}
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              aria-label="From date"
            />
            <span>→</span>
            <input
              type="date"
              className={styles.dateInput}
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              aria-label="To date"
            />
          </div>
        ) : null}
      </div>

      {error ? <div className={styles.banner}>{error}</div> : null}
      {customHint ? <p className={styles.sub}>{customHint}</p> : null}

      {loading ? (
        <p aria-busy="true">Đang tải analytics…</p>
      ) : data && !error ? (
        <>
          {typeof data.reviewer_avg_score === 'number' ? (
            <div className={styles.section}>
              <p className={styles.scoreCard}>
                Điểm review trung bình:{' '}
                <strong>{data.reviewer_avg_score.toFixed(1)}</strong>
              </p>
            </div>
          ) : null}

          <section className={styles.section} aria-labelledby="avg-seconds-title">
            <h2 id="avg-seconds-title" className={styles.sectionTitle}>
              Thời gian trung bình theo agent (giây)
            </h2>
            <div className={styles.chartWrap}>
              <ResponsiveContainer width="100%" height={250} minWidth={500}>
                <BarChart data={barData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="avg_seconds" fill="#0D9488" name="Giây" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className={styles.section} aria-labelledby="approve-rate-title">
            <h2 id="approve-rate-title" className={styles.sectionTitle}>
              Tỷ lệ thành công theo agent (%)
            </h2>
            <div className={styles.chartWrap}>
              <ResponsiveContainer width="100%" height={250} minWidth={500}>
                <BarChart data={approveRateData} layout="vertical" margin={{ left: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 100]} unit="%" />
                  <YAxis type="category" dataKey="name" width={100} />
                  <Tooltip formatter={(value: number) => `${value}%`} />
                  <Bar dataKey="rate" fill="#F97316" name="Success rate" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className={styles.section} aria-labelledby="members-title">
            <h2 id="members-title" className={styles.sectionTitle}>
              Thành viên
            </h2>
            {data.by_member.length === 0 ? (
              <p className={styles.sub}>Chưa có dữ liệu thành viên.</p>
            ) : (
              <table className={styles.memberTable}>
                <thead>
                  <tr>
                    <th>Thành viên</th>
                    <th>Done</th>
                    <th>In progress</th>
                  </tr>
                </thead>
                <tbody>
                  {data.by_member.map((member, index) => (
                    <tr key={`${member.display_name}-${index}`}>
                      <td>
                        <div className={styles.memberCell}>
                          <Avatar name={member.display_name} size="sm" />
                          {member.display_name}
                        </div>
                      </td>
                      <td>{member.tasks_done}</td>
                      <td>{member.tasks_in_progress}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className={styles.section} aria-labelledby="errors-title">
            <h2 id="errors-title" className={styles.sectionTitle}>
              Error breakdown
            </h2>
            {data.error_breakdown.length === 0 ? (
              <p className={styles.sub}>Không có lỗi trong khoảng thời gian này.</p>
            ) : (
              <div className={styles.badges}>
                {data.error_breakdown.map((item) => (
                  <span key={item.action_type} className={styles.errorBadge}>
                    {item.action_type}: {item.count}
                  </span>
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  )
}
