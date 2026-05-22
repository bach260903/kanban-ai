import { useSortable } from '@dnd-kit/sortable'

import { CSS } from '@dnd-kit/utilities'

import { isAxiosError } from 'axios'

import { useEffect, useState } from 'react'



import { Badge } from '../atoms/badge'
import { Button } from '../atoms/button'

import { useTaskStore } from '../../store/task-store'

import { getTaskBranch, type TaskBranchInfo } from '../../services/task-api'



import type { TaskColumnItem } from '../../store/task-store'

import type { AgentRunStatus } from '../../types'



import styles from './task-card.module.css'



export type TaskCardProps = {
  task: TaskColumnItem
  sortableDisabled?: boolean
  /** When set, shows a Start button (To do → In progress). */
  onStart?: () => void
  startBusy?: boolean
  /** Cancel in-progress coder and return task to To do. */
  onCancel?: () => void
  cancelBusy?: boolean
  /** Open code review panel (Review column only). */
  onOpenReview?: () => void
  isReviewSelected?: boolean
}



function agentRunLabel(status: AgentRunStatus): string {

  const labels: Record<AgentRunStatus, string> = {

    running: 'Running',

    success: 'Done',

    failure: 'Failure',

    awaiting_hil: 'Awaiting HIL',

    paused: 'Paused',

    timeout: 'Timeout',

  }

  return labels[status]

}



export function TaskCard({
  task,
  sortableDisabled = true,
  onStart,
  startBusy = false,
  onCancel,
  cancelBusy = false,
  onOpenReview,
  isReviewSelected = false,
}: TaskCardProps) {

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



  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({

    id: task.id,

    disabled: sortableDisabled,

  })



  const style = {

    transform: CSS.Transform.toString(transform),

    transition,

  }



  const desc = task.description?.trim() ?? ''

  const isAgentRunning =
    agentRun?.status === 'running' || agentRun?.status === 'paused'

  const branchLabel =

    branch?.branch_name ??

    (task.status === 'done' ? 'merged' : task.status === 'conflict' ? 'Conflict' : null)



  const dragProps = sortableDisabled ? {} : { ...attributes, ...listeners }

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={[
        styles.root,
        isDragging ? styles.rootDragging : '',
        isAgentRunning ? styles.rootAgentRunning : '',
        task.status === 'conflict' ? styles.rootConflict : '',
        isReviewSelected ? styles.rootReviewSelected : '',
        !sortableDisabled ? styles.rootDraggable : '',
        onOpenReview ? styles.rootClickable : '',
      ]
        .filter(Boolean)
        .join(' ')}
      {...dragProps}
      onClick={
        onOpenReview
          ? (e) => {
              if ((e.target as HTMLElement).closest('button')) return
              onOpenReview()
            }
          : undefined
      }
      onKeyDown={
        onOpenReview
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpenReview()
              }
            }
          : undefined
      }
      role={onOpenReview ? 'button' : undefined}
      tabIndex={onOpenReview ? 0 : undefined}
      title={
        onOpenReview
          ? 'Open code review'
          : sortableDisabled
            ? undefined
            : 'Drag to In progress or use Start'
      }
    >
      <span
        className={styles.handle}
        aria-hidden
        title={sortableDisabled ? undefined : 'Drag handle'}
      >
        ⋮⋮
      </span>

      <div className={styles.body}>

        <div className={styles.topRow}>

          <Badge kind="task" status="todo" label={`#${task.priority}`} className={styles.priorityBadge} />

          {task.status === 'conflict' ? (

            <Badge kind="task" status="conflict" label="Conflict" />

          ) : (

            <Badge kind="task" status={task.status} />

          )}

        </div>

        <h3 className={styles.title}>{task.title}</h3>

        {desc ? (

          <p className={styles.description}>{desc}</p>

        ) : (

          <p className={`${styles.description} ${styles.descriptionEmpty}`}>No description</p>

        )}

        <hr className={styles.divider} />

        <div className={styles.footer}>

          {isAgentRunning ? (

            <div className={styles.agentRunningBand} role="status" aria-label="Coder Agent is running">

              <span className={styles.agentRunningSpinner} aria-hidden />

              Coder Agent đang chạy

            </div>

          ) : agentRun ? (

            <Badge kind="agent" status={agentRun.status} label={agentRunLabel(agentRun.status)} />

          ) : (

            <span className={styles.agentPlaceholder}>Agent: —</span>

          )}

          {branchLabel ? (

            <Badge

              kind="task"

              status={task.status === 'conflict' ? 'conflict' : task.status === 'done' ? 'done' : 'in_progress'}

              label={branchLabel}

              className={styles.branchBadge}

            />

          ) : null}

          <span className={styles.updated}>Updated —</span>
        </div>
        {onCancel ? (
          <Button
            type="button"
            variant="danger"
            disabled={cancelBusy}
            onClick={(e) => {
              e.stopPropagation()
              onCancel()
            }}
          >
            Cancel
          </Button>
        ) : null}
        {onStart ? (
          <Button
            type="button"
            variant="primary"
            disabled={startBusy}
            onClick={(e) => {
              e.stopPropagation()
              onStart()
            }}
          >
            Start
          </Button>
        ) : null}
        {onOpenReview ? (
          <span className={styles.reviewHint}>{isReviewSelected ? 'Reviewing' : 'Click to review'}</span>
        ) : null}
      </div>
    </article>
  )

}


