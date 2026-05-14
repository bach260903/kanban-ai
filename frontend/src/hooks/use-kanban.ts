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
import { moveTask as moveTaskOnServer } from '../services/task-api'
import { useTaskStore } from '../store/task-store'
import type { TaskColumns } from '../store/task-store'
import type { AgentRunStatus, TaskStatus } from '../types'

const BOARD_STATUSES = ['todo', 'in_progress', 'review', 'done'] as const satisfies readonly TaskStatus[]

const SORTABLE_PREFIX = 'sortable-'

const POLL_MS = 3000

function isTerminalAgentStatus(status: AgentRunStatus): boolean {
  return status === 'success' || status === 'failure'
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

function moveConflictMessage(err: unknown): string {
  if (isAxiosError(err) && err.response?.status === 409) {
    const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    return 'Cannot move task: another task may already be in progress (WIP limit).'
  }
  return ''
}

export type UseKanbanResult = {
  sensors: ReturnType<typeof useSensors>
  collisionDetection: CollisionDetection
  onDragEnd: (event: DragEndEvent) => void
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
              if (isTerminalAgentStatus(run.status)) clearPoller(taskId)
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
            if (isTerminalAgentStatus(run.status)) clearPoller(taskId)
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
  }, [clearAllPollers, clearPoller])

  const onDragEnd = useCallback(
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

      void moveTaskOnServer(projectId, taskId, 'in_progress')
        .then((res) => {
          if (res.agent_run_id) {
            setTaskAgentRun(taskId, res.agent_run_id, 'running')
          }
        })
        .catch((err: unknown) => {
          useTaskStore.getState().setColumns(snapshot)
          const msg409 = moveConflictMessage(err)
          if (msg409) showErrorToast(msg409)
        })
    },
    [columns, projectId, setTaskAgentRun],
  )

  return {
    sensors,
    collisionDetection: closestCorners,
    onDragEnd,
  }
}
