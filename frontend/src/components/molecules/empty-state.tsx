import { KanbanSquare, Plus } from 'lucide-react'

import { Button } from '../atoms/button'

import styles from './empty-state.module.css'

export type EmptyStateProps = {
  onCreate: () => void
}

export function EmptyState({ onCreate }: EmptyStateProps) {
  return (
    <section
      data-empty-state="true"
      className={styles.root}
      aria-labelledby="empty-state-title"
    >
      <div className={styles.iconWrap} aria-hidden="true">
        <KanbanSquare className={styles.icon} />
      </div>
      <h2 id="empty-state-title" className={styles.title}>
        No projects yet
      </h2>
      <p className={styles.subtitle}>
        Create your first project to start building with AI.
      </p>
      <Button
        type="button"
        variant="primary"
        onClick={onCreate}
        className={styles.cta}
      >
        <Plus size={16} aria-hidden="true" />
        Create Project
      </Button>
    </section>
  )
}
