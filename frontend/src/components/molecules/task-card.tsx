import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'

import { useTaskStore } from '../../store/task-store'
import { getTaskBranch, type TaskBranchInfo } from '../../services/task-api'

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
  const [branch, setBranch] = useState<TaskBranchInfo | null | undefined>(undefined)

  useEffect(() => {
    if (task.status === 'todo') {
      setBranch(undefined)
      return
    }
    let cancelled = false
    const ac = new AbortController()
    ;(async () => {
      try {
        const info = await getTaskBranch(task.id, ac.signal)
        if (!cancelled) setBranch(info)
      } catch (e) {
        if (ac.signal.aborted) return
        if (isAxiosError(e) && e.response?.status === 404) {
          if (!cancelled) setBranch(null)
          return
        }
        if (!cancelled) setBranch(null)
      }
    })()
    return () => {
      cancelled = true
      ac.abort()
    }
  }, [task.id, task.status])

  const branchTitle =
    branch && branch.branch_name
      ? `Branch: ${branch.branch_name} (${branch.status})` +
        (branch.merged_at ? ` · merged ${branch.merged_at}` : '')
      : undefined

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
          {task.status === 'conflict' ? (
            <span
              className={styles.mergeConflictBadge}
              title="Merge conflict detected — resolve manually"
              aria-label="Merge conflict detected — resolve manually"
            >
              Conflict
            </span>
          ) : (
            <span className={badgeClassForStatus(task.status)}>{statusLabel(task.status)}</span>
          )}
          {branch && branch.branch_name ? (
            <span className={styles.branchHint} title={branchTitle}>
              {branch.branch_name}
            </span>
          ) : null}
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
