import { create } from 'zustand'

import type { TaskStatus, UUID } from '../types'

/** One card in a Kanban column (API list item + ``status`` for optimistic moves). */
export type TaskColumnItem = {
  id: UUID
  title: string
  description: string | null
  priority: number
  status: TaskStatus
}

export type TaskColumns = Record<TaskStatus, TaskColumnItem[]>

const STATUSES: TaskStatus[] = [
  'todo',
  'in_progress',
  'review',
  'done',
  'rejected',
  'conflict',
]

export function emptyTaskColumns(): TaskColumns {
  return Object.fromEntries(STATUSES.map((s) => [s, []])) as TaskColumns
}

export type TaskStore = {
  columns: TaskColumns
  setColumns: (columns: TaskColumns) => void
  moveTask: (taskId: UUID, fromStatus: TaskStatus, toStatus: TaskStatus) => void
}

export const useTaskStore = create<TaskStore>((set) => ({
  columns: emptyTaskColumns(),
  setColumns: (columns) => set({ columns }),
  moveTask: (taskId, fromStatus, toStatus) => {
    if (fromStatus === toStatus) return
    set((state) => {
      const fromList = state.columns[fromStatus]
      const idx = fromList.findIndex((t) => t.id === taskId)
      if (idx === -1) return state
      const task = fromList[idx]!
      const nextFrom = [...fromList.slice(0, idx), ...fromList.slice(idx + 1)]
      const moved: TaskColumnItem = { ...task, status: toStatus }
      const toList = state.columns[toStatus]
      return {
        columns: {
          ...state.columns,
          [fromStatus]: nextFrom,
          [toStatus]: [...toList, moved],
        },
      }
    })
  },
}))
