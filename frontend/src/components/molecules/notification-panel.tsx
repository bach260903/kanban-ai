import { X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Spinner } from '../atoms/spinner'
import { showErrorToast } from '../../lib/toast'
import {
  getNotifications,
  markAllRead,
  markRead,
  type NotificationItem,
} from '../../services/notification-api'

import styles from './notification-panel.module.css'

const POLL_MS = 30_000

const TYPE_ICON: Record<string, string> = {
  task_assigned: '📋',
  task_needs_review: '👁',
  task_done: '✅',
  agent_error: '⚠️',
  task_unblocked: '🔓',
  invite_accepted: '👤',
  review_complete: '✓',
  agent_started: '🤖',
  task_in_progress: '⚙️',
}

function timeAgo(isoDate: string): string {
  const then = new Date(isoDate).getTime()
  if (Number.isNaN(then)) return ''
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000))
  if (sec < 60) return 'Vừa xong'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} phút trước`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} giờ trước`
  const day = Math.floor(hr / 24)
  return `${day} ngày trước`
}

function iconForType(type: string): string {
  return TYPE_ICON[type] ?? '🔔'
}

export type NotificationPanelProps = {
  projectId: string
  onClose: () => void
  onUnreadChange?: (count: number) => void
  onTaskClick?: (taskId: string) => void
}

export function NotificationPanel({
  projectId,
  onClose,
  onUnreadChange,
  onTaskClick,
}: NotificationPanelProps) {
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadedOnce, setLoadedOnce] = useState(false)
  const [markingAll, setMarkingAll] = useState(false)

  const refresh = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const res = await getNotifications({ limit: 50 })
      setItems(res.items)
      setUnreadCount(res.total_unread)
      onUnreadChange?.(res.total_unread)
      setLoadedOnce(true)
    } catch {
      /* silent — poll tiếp theo sẽ retry */
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [onUnreadChange])

  useEffect(() => {
    void refresh(true)
    const id = window.setInterval(() => void refresh(false), POLL_MS)
    return () => window.clearInterval(id)
  }, [refresh])

  async function handleMarkAll() {
    if (unreadCount <= 0) return
    setMarkingAll(true)
    try {
      await markAllRead()
      setItems((prev) => prev.map((item) => ({ ...item, is_read: true })))
      setUnreadCount(0)
      onUnreadChange?.(0)
    } catch {
      showErrorToast('Không đánh dấu được tất cả thông báo')
    } finally {
      setMarkingAll(false)
    }
  }

  async function handleItemClick(item: NotificationItem) {
    if (!item.is_read) {
      try {
        await markRead(item.id)
        setItems((prev) =>
          prev.map((row) => (row.id === item.id ? { ...row, is_read: true } : row)),
        )
        setUnreadCount((prev) => {
          const next = Math.max(0, prev - 1)
          onUnreadChange?.(next)
          return next
        })
      } catch {
        /* still navigate on failure */
      }
    }

    if (item.reference_type === 'task' && item.reference_id) {
      const targetProjectId = item.project_id ?? projectId
      if (onTaskClick && targetProjectId === projectId) {
        onTaskClick(item.reference_id)
      } else {
        navigate(`/projects/${targetProjectId}`)
      }
    }
    onClose()
  }

  return (
    <div className={styles.panel} role="dialog" aria-label="Thông báo">
      <div className={styles.header}>
        <h2 className={styles.title}>Thông báo</h2>
        <button
          type="button"
          className={styles.markAllBtn}
          onClick={() => void handleMarkAll()}
          disabled={markingAll || unreadCount <= 0}
        >
          {markingAll ? 'Đang xử lý…' : 'Đánh dấu tất cả đã đọc'}
        </button>
        <button
          type="button"
          className={styles.closeBtn}
          onClick={onClose}
          aria-label="Đóng thông báo"
        >
          <X size={14} aria-hidden="true" />
        </button>
      </div>

      {loading || !loadedOnce ? (
        <p className={styles.loading}>
          <Spinner aria-label="Đang tải thông báo" />
        </p>
      ) : items.length === 0 ? (
        <p className={styles.empty}>
          <span className={styles.emptyIcon} aria-hidden="true">
            🔔
          </span>
          Không có thông báo nào
        </p>
      ) : (
        <ul className={styles.list}>
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={`${styles.item} ${item.is_read ? '' : styles.itemUnread}`}
                onClick={() => void handleItemClick(item)}
              >
                <span className={styles.icon} aria-hidden="true">
                  {iconForType(item.type)}
                </span>
                <span className={styles.body}>
                  <p className={styles.content}>{item.content}</p>
                  <p className={styles.time}>{timeAgo(item.created_at)}</p>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
