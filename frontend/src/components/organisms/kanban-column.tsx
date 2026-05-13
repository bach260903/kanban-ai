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
  /** Passed through to each ``TaskCard`` (default keeps drag off until T060). */
  taskCardSortableDisabled?: boolean
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

export function KanbanColumn({ column, taskCardSortableDisabled = true }: KanbanColumnProps) {
  const { status, tasks } = column
  const ids = tasks.map((t) => t.id)

  return (
    <section className={styles.root} aria-labelledby={`kanban-col-${status}`}>
      <header className={styles.header}>
        <h2 className={styles.title} id={`kanban-col-${status}`}>
          {columnHeading(status)}
        </h2>
        <span className={styles.count}>
          {tasks.length} {tasks.length === 1 ? 'task' : 'tasks'}
        </span>
      </header>
      <div className={styles.listWrap}>
        {tasks.length === 0 ? (
          <p className={styles.empty}>No tasks</p>
        ) : (
          <SortableContext id={`kanban-column-${status}`} items={ids} strategy={verticalListSortingStrategy}>
            <ul className={styles.list}>
              {tasks.map((task) => (
                <li key={task.id} className={styles.listItem}>
                  <TaskCard task={task} sortableDisabled={taskCardSortableDisabled} />
                </li>
              ))}
            </ul>
          </SortableContext>
        )}
      </div>
    </section>
  )
}
