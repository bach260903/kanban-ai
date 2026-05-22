import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'

import { TaskCard } from '../molecules/task-card'
import type { TaskColumnItem } from '../../store/task-store'
import type { TaskStatus } from '../../types'

import styles from './kanban-column.module.css'

/** One Kanban column: status key + tasks currently in that column. */
export type KanbanColumnModel = {
  status: TaskStatus
  tasks: TaskColumnItem[]
}

export type KanbanColumnProps = {
  column: KanbanColumnModel
  /** When true, cards are not draggable (e.g. all columns except To do for US8 MVP). */
  taskCardSortableDisabled?: boolean
  /** When true, render WIP = 1 chip in header (only for In Progress). */
  isWip?: boolean
  /** When false and column is 'todo', show PLAN-pending warning banner. */
  planApproved?: boolean
  /** Start handler for To do tasks (todo → in_progress). */
  onStartTask?: (taskId: string) => void
  /** Task id currently starting (disables its Start button). */
  startingTaskId?: string | null
  /** Task id with review panel open. */
  selectedReviewTaskId?: string | null
  onOpenReview?: (taskId: string) => void
  onCancelTask?: (taskId: string) => void
  cancellingTaskId?: string | null
}

function columnHeading(status: TaskStatus): string {
  const titles: Record<TaskStatus, string> = {
    todo: 'To do',
    in_progress: 'In progress',
    review: 'Review',
    done: 'Done',
    rejected: 'Rejected',
    conflict: 'Conflict',
  }
  return titles[status]
}

const EMPTY_HINTS: Record<TaskStatus, string> = {
  todo: 'No tasks yet.',
  in_progress: 'Drag a task here to start the Coder.',
  review: 'Coder finished — click a task to review when ready.',
  done: 'No tasks done yet.',
  rejected: 'No rejected tasks.',
  conflict: 'No conflicts.',
}

export function KanbanColumn({
  column,
  taskCardSortableDisabled = true,
  isWip = false,
  planApproved = false,
  onStartTask,
  startingTaskId = null,
  selectedReviewTaskId = null,
  onOpenReview,
  onCancelTask,
  cancellingTaskId = null,
}: KanbanColumnProps) {
  const { status, tasks } = column
  const ids = tasks.map((t) => t.id)

  const { setNodeRef, isOver } = useDroppable({
    id: `droppable-${status}`,
    data: { type: 'column', status },
  })

  const showPlanPending = tasks.length === 0 && status === 'todo' && !planApproved

  return (
    <section className={styles.root} aria-labelledby={`kanban-col-${status}`}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h2 className={styles.title} id={`kanban-col-${status}`}>
            {columnHeading(status)}
          </h2>
          <span className={styles.count}>
            {tasks.length} {tasks.length === 1 ? 'task' : 'tasks'}
          </span>
        </div>
        {isWip && (
          <span className={styles.wip} aria-label="WIP limit: 1">
            WIP = 1
          </span>
        )}
      </header>
      <div
        ref={setNodeRef}
        className={`${styles.listWrap} ${isOver ? styles.listWrapOver : ''}`}
      >
        {tasks.length === 0 ? (
          showPlanPending ? (
            <div className={styles.emptyBanner} role="status">
              <span aria-hidden>⏳</span>
              <span>Approve PLAN.md to generate tasks.</span>
            </div>
          ) : (
            <p className={styles.empty}>{EMPTY_HINTS[status]}</p>
          )
        ) : (
          <SortableContext id={`sortable-${status}`} items={ids} strategy={verticalListSortingStrategy}>
            <ul className={styles.list}>
              {tasks.map((task) => (
                <li key={task.id} className={styles.listItem}>
                  <TaskCard
                    task={task}
                    sortableDisabled={taskCardSortableDisabled}
                    onStart={
                      status === 'todo' && onStartTask ? () => onStartTask(task.id) : undefined
                    }
                    startBusy={startingTaskId === task.id}
                    onCancel={
                      status === 'in_progress' && onCancelTask
                        ? () => onCancelTask(task.id)
                        : undefined
                    }
                    cancelBusy={cancellingTaskId === task.id}
                    onOpenReview={
                      status === 'review' && onOpenReview ? () => onOpenReview(task.id) : undefined
                    }
                    isReviewSelected={status === 'review' && selectedReviewTaskId === task.id}
                  />
                </li>
              ))}
            </ul>
          </SortableContext>
        )}
      </div>
    </section>
  )
}
