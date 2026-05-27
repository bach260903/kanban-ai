import styles from './notification-badge.module.css'

type NotificationBadgeProps = {
  count: number
}

export function NotificationBadge({ count }: NotificationBadgeProps) {
  if (count <= 0) return null
  return (
    <span className={styles.badge} aria-hidden>
      {count > 99 ? '99+' : count}
    </span>
  )
}
