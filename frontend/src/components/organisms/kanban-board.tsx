import {
  closestCorners,
  DndContext,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { isAxiosError } from 'axios'
import { useCallback, useEffect, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import { KanbanColumn } from './kanban-column'
import { getTasks, groupedResponseToTaskColumns, moveTask as moveTaskOnServer } from '../../services/task-api'
import { emptyTaskColumns, useTaskStore } from '../../store/task-store'
import type { TaskColumns } from '../../store/task-store'
import type { TaskStatus } from '../../types'

import styles from './kanban-board.module.css'

/** Primary board columns (US7 checkpoint); rejected/conflict stay in store but off MVP board. */
const BOARD_STATUSES = ['todo', 'in_progress', 'review', 'done'] as const satisfies readonly TaskStatus[]

const SORTABLE_PREFIX = 'sortable-'

export type KanbanBoardProps = {
  projectId: string
}

function loadErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    return err.message
  }
  if (err instanceof Error) return err.message
  return 'Unable to load tasks.'
}

function findColumnForTask(columns: TaskColumns, taskId: string): TaskStatus | undefined {
  for (const st of BOARD_STATUSES) {
    if (columns[st].some((t) => t.id === taskId)) return st
  }
  return undefined
}

function resolveDropTarget(
  over: NonNullable<DragEndEvent['over']>,
  columns: TaskColumns,
): TaskStatus | undefined {
  const data = over.data.current as { type?: string; status?: TaskStatus } | undefined
  if (data?.type === 'column' && data.status) return data.status
  return findColumnForTask(columns, String(over.id))
}

export function KanbanBoard({ projectId }: KanbanBoardProps) {
  const columns = useTaskStore((s) => s.columns)
  const setColumns = useTaskStore((s) => s.setColumns)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over) return

      const containerId = active.data.current?.sortable?.containerId as string | undefined
      const fromStatus = containerId?.startsWith(SORTABLE_PREFIX)
        ? (containerId.slice(SORTABLE_PREFIX.length) as TaskStatus)
        : undefined
      if (!fromStatus) return

      const toStatus = resolveDropTarget(over, columns)
      if (!toStatus) return

      if (fromStatus !== 'todo' || toStatus !== 'in_progress') {
        return
      }

      const taskId = String(active.id)
      const snapshot = useTaskStore.getState().columns
      useTaskStore.getState().moveTask(taskId, 'todo', 'in_progress')

      void moveTaskOnServer(projectId, taskId, 'in_progress').catch(() => {
        useTaskStore.getState().setColumns(snapshot)
      })
    },
    [columns, projectId],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getTasks(projectId)
        if (!cancelled) setColumns(groupedResponseToTaskColumns(data))
      } catch (err) {
        if (!cancelled) {
          setError(loadErrorMessage(err))
          setColumns(emptyTaskColumns())
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
      setColumns(emptyTaskColumns())
    }
  }, [projectId, setColumns])

  if (loading) {
    return (
      <p className={styles.loading}>
        <Spinner aria-label="Loading Kanban tasks" />
        Loading tasks…
      </p>
    )
  }

  if (error) {
    return <p className={styles.error}>{error}</p>
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
      <div className={styles.board}>
        {BOARD_STATUSES.map((status) => (
          <KanbanColumn
            key={status}
            column={{ status, tasks: columns[status] }}
            taskCardSortableDisabled={status !== 'todo'}
          />
        ))}
      </div>
    </DndContext>
  )
}
