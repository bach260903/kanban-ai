import type { TaskColumnItem, TaskColumns } from '../store/task-store'
import type { DiffReviewStatus, TaskStatus, UUID } from '../types'

import api from './api'

const PROJECTS = '/api/v1/projects'

function tasksBase(projectId: string): string {
  return `${PROJECTS}/${projectId}/tasks`
}

/** Row inside a grouped column (matches backend ``TaskKanbanItem``). */
export type TaskKanbanListItem = {
  id: UUID
  title: string
  description: string | null
  priority: number
}

/** Response shape of ``GET /api/v1/projects/{project_id}/tasks``. */
export type TasksGroupedResponse = {
  todo: TaskKanbanListItem[]
  in_progress: TaskKanbanListItem[]
  review: TaskKanbanListItem[]
  done: TaskKanbanListItem[]
  rejected: TaskKanbanListItem[]
  conflict: TaskKanbanListItem[]
}

function withStatus(items: TaskKanbanListItem[], status: TaskStatus): TaskColumnItem[] {
  return items.map((row) => ({ ...row, status }))
}

/** Maps API grouped payload into ``taskStore`` column shape (every card carries ``status``). */
export function groupedResponseToTaskColumns(data: TasksGroupedResponse): TaskColumns {
  return {
    todo: withStatus(data.todo, 'todo'),
    in_progress: withStatus(data.in_progress, 'in_progress'),
    review: withStatus(data.review, 'review'),
    done: withStatus(data.done, 'done'),
    rejected: withStatus(data.rejected, 'rejected'),
    conflict: withStatus(data.conflict, 'conflict'),
  }
}

/** Expected body for ``POST .../tasks/{task_id}/move`` (``plan.md``). */
export type TaskMoveBody = {
  to: TaskStatus
}

/** Expected JSON from ``POST .../move`` once T057 is implemented. */
export type TaskMoveResponse = {
  task_id: UUID
  from_status: TaskStatus
  to_status: TaskStatus
  agent_run_id: UUID | null
}

/** Latest diff for a task (``GET .../diff``, T062). */
export type TaskDiffResponse = {
  id: UUID
  task_id: UUID
  original_content: string
  modified_content: string
  files_affected: string[]
  review_status: DiffReviewStatus
}

export async function getTasks(projectId: string): Promise<TasksGroupedResponse> {
  const { data } = await api.get<TasksGroupedResponse>(tasksBase(projectId))
  return data
}

export async function moveTask(
  projectId: string,
  taskId: string,
  to: TaskStatus,
): Promise<TaskMoveResponse> {
  const { data } = await api.post<TaskMoveResponse>(`${tasksBase(projectId)}/${taskId}/move`, {
    to,
  } satisfies TaskMoveBody)
  return data
}

export async function approveTask(projectId: string, taskId: string): Promise<void> {
  await api.post(`${tasksBase(projectId)}/${taskId}/approve`)
}

export async function rejectTask(projectId: string, taskId: string, feedback: string): Promise<void> {
  await api.post(`${tasksBase(projectId)}/${taskId}/reject`, { feedback })
}

export async function getDiff(projectId: string, taskId: string): Promise<TaskDiffResponse> {
  const { data } = await api.get<TaskDiffResponse>(`${tasksBase(projectId)}/${taskId}/diff`)
  return data
}
