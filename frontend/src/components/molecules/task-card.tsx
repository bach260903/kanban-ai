import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

import { useTaskStore } from '../../store/task-store'

import type { TaskColumnItem } from '../../store/task-store'
import type { AgentRunStatus, TaskStatus } from '../../types'

import styles from './task-card.module.css'

export type TaskCardProps = {
  task: TaskColumnItem
  /** When true (default), sortable item is registered but not draggable — T060 enables drag */
  sortableDisabled?: boolean
}

function statusLabel(status: TaskStatus): string {
  const labels: Record<TaskStatus, string> = {
    todo: 'To do',
    in_progress: 'In progress',
    review: 'Review',
    done: 'Done',
    rejected: 'Rejected',
    conflict: 'Conflict',
  }
  return labels[status]
}

function badgeClassForStatus(status: TaskStatus): string {
  const base = styles.badge
  switch (status) {
    case 'todo':
      return `${base} ${styles.badgeTodo}`
    case 'in_progress':
      return `${base} ${styles.badgeInProgress}`
    case 'review':
      return `${base} ${styles.badgeReview}`
    case 'done':
      return `${base} ${styles.badgeDone}`
    case 'rejected':
      return `${base} ${styles.badgeRejected}`
    case 'conflict':
      return `${base} ${styles.badgeConflict}`
  }
}

function agentRunBadgeClass(status: AgentRunStatus): string {
  const base = styles.agentBadge
  switch (status) {
    case 'running':
      return `${base} ${styles.agentRunning}`
    case 'success':
      return `${base} ${styles.agentSuccess}`
    case 'failure':
    case 'timeout':
      return `${base} ${styles.agentFailure}`
    case 'awaiting_hil':
      return `${base} ${styles.agentHil}`
    case 'paused':
      return `${base} ${styles.agentPaused}`
    default:
      return base
  }
}

function agentRunLabel(status: AgentRunStatus): string {
  const labels: Record<AgentRunStatus, string> = {
    running: 'Agent: running',
    success: 'Agent: done',
    failure: 'Agent: failed',
    awaiting_hil: 'Agent: awaiting review',
    paused: 'Agent: paused',
    timeout: 'Agent: timed out',
  }
  return labels[status]
}

export function TaskCard({ task, sortableDisabled = true }: TaskCardProps) {
  const agentRun = useTaskStore((s) => s.taskAgentByTaskId[task.id])

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    disabled: sortableDisabled,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const desc = task.description?.trim() ?? ''

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={`${styles.root} ${isDragging ? styles.rootDragging : ''}`}
      {...attributes}
    >
      <button
        type="button"
        className={styles.handle}
        tabIndex={-1}
        aria-hidden
        title={sortableDisabled ? 'Drag inactive for this column' : 'Drag into In Progress'}
        {...(sortableDisabled ? {} : listeners)}
      />
      <div className={styles.body}>
        <h3 className={styles.title}>{task.title}</h3>
        {desc ? (
          <p className={styles.description}>{desc}</p>
        ) : (
          <p className={`${styles.description} ${styles.descriptionEmpty}`}>No description</p>
        )}
        <div className={styles.meta}>
          <span className={styles.priority} title="Priority (lower = higher)">
            {task.priority}
          </span>
          <span className={badgeClassForStatus(task.status)}>{statusLabel(task.status)}</span>
          {agentRun ? (
            <span className={agentRunBadgeClass(agentRun.status)} title={`Run ${agentRun.runId}`}>
              {agentRunLabel(agentRun.status)}
            </span>
          ) : null}
        </div>
      </div>
    </article>
  )
}
