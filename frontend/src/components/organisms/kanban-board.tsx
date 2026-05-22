import { DndContext } from '@dnd-kit/core'
import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'

import { Spinner } from '../atoms/spinner'
import { KanbanColumn } from './kanban-column'
import { useKanban } from '../../hooks/use-kanban'
import { getTasks, groupedResponseToTaskColumns } from '../../services/task-api'
import { emptyTaskColumns, useTaskStore } from '../../store/task-store'
import type { TaskStatus } from '../../types'

import styles from './kanban-board.module.css'

/** All 5 logical columns per ui-spec §5.5. */
const BOARD_STATUSES = ['todo', 'in_progress', 'review', 'done', 'rejected', 'conflict'] as const satisfies readonly TaskStatus[]

export type KanbanBoardProps = {
  projectId: string
  /** True when the latest PLAN document has status === 'approved'. */
  planApproved?: boolean
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

export function KanbanBoard({ projectId, planApproved = false }: KanbanBoardProps) {
  const columns = useTaskStore((s) => s.columns)
  const setColumns = useTaskStore((s) => s.setColumns)
  const clearTaskAgentRuns = useTaskStore((s) => s.clearTaskAgentRuns)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const { sensors, collisionDetection, onDragEnd } = useKanban(projectId)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await getTasks(projectId)
        if (!cancelled) {
          clearTaskAgentRuns()
          setColumns(groupedResponseToTaskColumns(data))
        }
      } catch (err) {
        if (!cancelled) {
          setError(loadErrorMessage(err))
          clearTaskAgentRuns()
          setColumns(emptyTaskColumns())
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, setColumns, clearTaskAgentRuns])

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
    <DndContext sensors={sensors} collisionDetection={collisionDetection} onDragEnd={onDragEnd}>
      <div className={styles.board}>
        {BOARD_STATUSES.map((status) => (
          <KanbanColumn
            key={status}
            column={{ status, tasks: columns[status] }}
            taskCardSortableDisabled={status !== 'todo'}
            isWip={status === 'in_progress'}
            planApproved={planApproved}
          />
        ))}
      </div>
    </DndContext>
  )
}
