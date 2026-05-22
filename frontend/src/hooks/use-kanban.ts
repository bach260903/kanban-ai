import {
  closestCorners,
  type CollisionDetection,
  type DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { isAxiosError } from 'axios'
import { useCallback, useEffect, useRef } from 'react'

import { showErrorToast } from '../lib/toast'
import { getAgentRun } from '../services/document-api'
import {
  getTasks,
  groupedResponseToTaskColumns,
  moveTask as moveTaskOnServer,
} from '../services/task-api'
import { useTaskStore } from '../store/task-store'
import type { TaskColumns } from '../store/task-store'
import type { AgentRunStatus, TaskStatus } from '../types'

const BOARD_STATUSES = ['todo', 'in_progress', 'review', 'done'] as const satisfies readonly TaskStatus[]

const SORTABLE_PREFIX = 'sortable-'

const POLL_MS = 2000

/** Coder finished (or failed) — stop polling and refresh Kanban columns from API. */
function isTerminalAgentStatus(status: AgentRunStatus): boolean {
  return (
    status === 'success' ||
    status === 'failure' ||
    status === 'timeout' ||
    status === 'awaiting_hil'
  )
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

function moveErrorMessage(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (err.response?.status === 409) {
      return 'Cannot move task: another task may already be in progress (WIP limit).'
    }
    if (err.response?.status === 400) {
      return 'Invalid move. Drag from To do to In progress only.'
    }
    return err.message || 'Failed to move task.'
  }
  if (err instanceof Error) return err.message
  return 'Failed to move task.'
}

export type UseKanbanResult = {
  sensors: ReturnType<typeof useSensors>
  collisionDetection: CollisionDetection
  onDragEnd: (event: DragEndEvent) => void
  /** Move a To do task to In progress (same as drag-drop). */
  startTask: (taskId: string) => void
}

/**
 * Kanban drag (todo → in_progress only) + optimistic move, 409 toast, agent run tracking + polling (T061).
 */
export function useKanban(projectId: string): UseKanbanResult {
  const columns = useTaskStore((s) => s.columns)
  const setTaskAgentRun = useTaskStore((s) => s.setTaskAgentRun)

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const pollIntervalsRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map())

  const clearPoller = useCallback((taskId: string) => {
    const id = pollIntervalsRef.current.get(taskId)
    if (id != null) {
      clearInterval(id)
      pollIntervalsRef.current.delete(taskId)
    }
  }, [])

  const clearAllPollers = useCallback(() => {
    for (const id of pollIntervalsRef.current.values()) clearInterval(id)
    pollIntervalsRef.current.clear()
  }, [])

  const refreshBoard = useCallback(async () => {
    try {
      const data = await getTasks(projectId)
      useTaskStore.getState().setColumns(groupedResponseToTaskColumns(data))
    } catch {
      /* keep optimistic columns on transient failure */
    }
  }, [projectId])

  useEffect(() => {
    const reconcilePollers = () => {
      const map = useTaskStore.getState().taskAgentByTaskId

      for (const taskId of pollIntervalsRef.current.keys()) {
        const meta = map[taskId]
        if (!meta || isTerminalAgentStatus(meta.status)) clearPoller(taskId)
      }

      for (const [taskId, meta] of Object.entries(map)) {
        if (!meta?.runId || isTerminalAgentStatus(meta.status)) continue
        if (pollIntervalsRef.current.has(taskId)) continue

        const intervalId = setInterval(() => {
          void (async () => {
            const latest = useTaskStore.getState().taskAgentByTaskId[taskId]
            const runId = latest?.runId
            if (!runId) {
              clearPoller(taskId)
              return
            }
            try {
              const run = await getAgentRun(runId)
              useTaskStore.getState().updateTaskAgentRunStatus(taskId, run.status)
              if (isTerminalAgentStatus(run.status)) {
                clearPoller(taskId)
                void refreshBoard()
              }
            } catch {
              /* transient network errors — next tick retries */
            }
          })()
        }, POLL_MS)
        pollIntervalsRef.current.set(taskId, intervalId)

        void (async () => {
          try {
            const run = await getAgentRun(meta.runId)
            useTaskStore.getState().updateTaskAgentRunStatus(taskId, run.status)
            if (isTerminalAgentStatus(run.status)) {
              clearPoller(taskId)
              void refreshBoard()
            }
          } catch {
            /* ignore */
          }
        })()
      }
    }

    reconcilePollers()
    const unsub = useTaskStore.subscribe(reconcilePollers)
    return () => {
      unsub()
      clearAllPollers()
    }
  }, [clearAllPollers, clearPoller, refreshBoard])

  const startTask = useCallback(
    (taskId: string) => {
      const cols = useTaskStore.getState().columns
      const inTodo = cols.todo.some((t) => t.id === taskId)
      if (!inTodo) {
        showErrorToast('Task is no longer in To do.')
        return
      }
      if (cols.in_progress.length >= 1) {
        showErrorToast(
          'WIP limit: finish or move the current In progress task before starting another.',
        )
        return
      }

      const snapshot = cols
      useTaskStore.getState().moveTask(taskId, 'todo', 'in_progress')

      void moveTaskOnServer(projectId, taskId, 'in_progress')
        .then((res) => {
          if (res.agent_run_id) {
            setTaskAgentRun(taskId, res.agent_run_id, 'running')
          }
        })
        .catch((err: unknown) => {
          useTaskStore.getState().setColumns(snapshot)
          showErrorToast(moveErrorMessage(err))
        })
    },
    [projectId, setTaskAgentRun],
  )

  const onDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event
      if (!over) return

      const taskId = String(active.id)
      const containerId = active.data.current?.sortable?.containerId as string | undefined
      const fromStatus = containerId?.startsWith(SORTABLE_PREFIX)
        ? (containerId.slice(SORTABLE_PREFIX.length) as TaskStatus)
        : findColumnForTask(columns, taskId)
      if (!fromStatus) return

      const toStatus = resolveDropTarget(over, columns)
      if (!toStatus) return

      if (fromStatus !== 'todo' || toStatus !== 'in_progress') {
        if (fromStatus === 'todo') {
          showErrorToast('Drop the task on the In progress column to start the Coder Agent.')
        }
        return
      }

      startTask(taskId)
    },
    [columns, startTask],
  )

  return {
    sensors,
    collisionDetection: closestCorners,
    onDragEnd,
    startTask,
  }
}
