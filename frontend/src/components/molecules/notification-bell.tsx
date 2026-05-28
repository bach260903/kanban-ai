import { Bell } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { relativeTime } from '../../utils/relative-time'
import {
  getNotifications,
  markAllRead,
  markRead,
  type NotificationItem,
} from '../../services/notification-api'

import styles from './notification-bell.module.css'

const NOTIFICATION_LABELS: Record<string, string> = {
  task_assigned: 'Task được giao',
  task_needs_review: 'Cần review',
  task_done: 'Task hoàn thành',
  task_unblocked: 'Task đã mở khóa',
  agent_error: 'Lỗi agent',
  invite_accepted: 'Lời mời được chấp nhận',
  review_complete: 'Review hoàn thành',
  join_requested: 'Yêu cầu tham gia',
}

function notifLabel(type: string): string {
  return NOTIFICATION_LABELS[type] ?? type
}

const POLL_INTERVAL_MS = 30_000

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [totalUnread, setTotalUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const [markingAll, setMarkingAll] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const btnRef = useRef<HTMLButtonElement>(null)

  const fetchNotifications = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const data = await getNotifications({ limit: 20 })
      setItems(data.items)
      setTotalUnread(data.total_unread)
    } catch {
      // silent — don't show error for background polls
    } finally {
      if (!silent) setLoading(false)
    }
  }, [])

  // Load on mount + poll every 30s
  useEffect(() => {
    void fetchNotifications()
    const id = setInterval(() => void fetchNotifications(true), POLL_INTERVAL_MS)
    return () => clearInterval(id)
  }, [fetchNotifications])

  // Reload when opened
  useEffect(() => {
    if (open) void fetchNotifications()
  }, [open, fetchNotifications])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        !btnRef.current?.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  async function handleMarkRead(item: NotificationItem) {
    if (item.is_read) return
    try {
      await markRead(item.id)
      setItems((prev) => prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n)))
      setTotalUnread((c) => Math.max(0, c - 1))
    } catch {
      // ignore
    }
  }

  async function handleMarkAllRead() {
    setMarkingAll(true)
    try {
      await markAllRead()
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setTotalUnread(0)
    } catch {
      // ignore
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <div className={styles.wrap}>
      <button
        ref={btnRef}
        type="button"
        className={styles.bell}
        aria-label={`Thông báo${totalUnread > 0 ? ` (${totalUnread} chưa đọc)` : ''}`}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={18} aria-hidden="true" />
        {totalUnread > 0 ? (
          <span className={styles.badge} aria-hidden="true">
            {totalUnread > 99 ? '99+' : totalUnread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          ref={panelRef}
          className={styles.panel}
          role="dialog"
          aria-label="Thông báo"
        >
          <div className={styles.panelHeader}>
            <span className={styles.panelTitle}>Thông báo</span>
            {totalUnread > 0 ? (
              <button
                type="button"
                className={styles.markAll}
                disabled={markingAll}
                onClick={() => void handleMarkAllRead()}
              >
                {markingAll ? 'Đang xử lý…' : 'Đánh dấu tất cả đã đọc'}
              </button>
            ) : null}
          </div>

          {loading ? (
            <p className={styles.empty}>Đang tải…</p>
          ) : items.length === 0 ? (
            <p className={styles.empty}>Không có thông báo nào.</p>
          ) : (
            <ul className={styles.list} role="list">
              {items.map((item) => (
                <li
                  key={item.id}
                  className={`${styles.item} ${item.is_read ? styles.itemRead : styles.itemUnread}`}
                  onClick={() => void handleMarkRead(item)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') void handleMarkRead(item)
                  }}
                >
                  <div className={styles.itemTop}>
                    <span className={styles.itemType}>{notifLabel(item.type)}</span>
                    <time className={styles.itemTime} dateTime={item.created_at} title={new Date(item.created_at).toLocaleString()}>
                      {relativeTime(item.created_at)}
                    </time>
                  </div>
                  <p className={styles.itemContent}>{item.content}</p>
                  {!item.is_read ? <span className={styles.dot} aria-hidden="true" /> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  )
}
