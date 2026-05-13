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

  const { setNodeRef, isOver } = useDroppable({
    id: `droppable-${status}`,
    data: { type: 'column', status },
  })

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
      <div
        ref={setNodeRef}
        className={`${styles.listWrap} ${isOver ? styles.listWrapOver : ''}`}
      >
        {tasks.length === 0 ? (
          <p className={styles.empty}>No tasks</p>
        ) : (
          <SortableContext id={`sortable-${status}`} items={ids} strategy={verticalListSortingStrategy}>
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
