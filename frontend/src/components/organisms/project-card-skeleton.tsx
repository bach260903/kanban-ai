import styles from './project-card-skeleton.module.css'

export function ProjectCardSkeleton() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={styles.row}>
        <span className={`${styles.shimmer} ${styles.title}`} />
        <span className={`${styles.shimmer} ${styles.badge}`} />
      </div>
      <span className={`${styles.shimmer} ${styles.desc}`} />
      <div className={styles.chipRow}>
        <span className={`${styles.shimmer} ${styles.chip}`} />
        <span className={`${styles.shimmer} ${styles.chip}`} />
      </div>
      <div className={styles.footer}>
        <span className={`${styles.shimmer} ${styles.footerChip}`} />
        <span className={`${styles.shimmer} ${styles.footerChip}`} />
        <span
          className={`${styles.shimmer} ${styles.footerChip}`}
          style={{ marginLeft: 'auto' }}
        />
      </div>
    </div>
  )
}
