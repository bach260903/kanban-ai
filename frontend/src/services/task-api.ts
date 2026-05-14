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
  await api.post(`${tasksBase(projectId)}/${taskId}/approve`, {})
}

export async function getDiff(projectId: string, taskId: string): Promise<TaskDiffResponse> {
  const { data } = await api.get<TaskDiffResponse>(`${tasksBase(projectId)}/${taskId}/diff`)
  return data
}

/** ``GET /api/v1/tasks/{task_id}/branch`` (US15 / T104). */
export type TaskBranchInfo = {
  task_id: UUID
  branch_name: string
  status: 'active' | 'merged' | 'conflict'
  created_at: string
  merged_at: string | null
}

export async function getTaskBranch(taskId: string, signal?: AbortSignal): Promise<TaskBranchInfo> {
  const { data } = await api.get<TaskBranchInfo>(`/api/v1/tasks/${taskId}/branch`, { signal })
  return data
}

/** ``GET/POST /api/v1/tasks/{task_id}/comments`` (US16 / T106–T109). */
export type InlineCommentItem = {
  id: string
  task_id: string
  diff_id: string | null
  file_path: string
  line_number: number
  comment_text: string
  created_at: string
}

/** Fields needed for diff glyphs, ``useInlineComments``, and reject payload (US16 / T110). */
export type InlineCommentListRow = Pick<InlineCommentItem, 'id' | 'file_path' | 'line_number' | 'comment_text'>

/** Body for ``POST .../tasks/{task_id}/reject`` (T064, T111). */
export type TaskRejectBody = {
  feedback: string
  /** When set (including ``[]``), server uses this list instead of loading comments from the DB. */
  inline_comments?: Array<Pick<InlineCommentItem, 'file_path' | 'line_number' | 'comment_text'>>
}

export async function rejectTask(projectId: string, taskId: string, body: TaskRejectBody): Promise<void> {
  await api.post(`${tasksBase(projectId)}/${taskId}/reject`, body)
}

export async function getTaskComments(taskId: string, signal?: AbortSignal): Promise<InlineCommentItem[]> {
  const { data } = await api.get<InlineCommentItem[]>(`/api/v1/tasks/${taskId}/comments`, { signal })
  return data
}

export async function createTaskComment(
  taskId: string,
  body: { file_path: string; line_number: number; comment_text: string },
): Promise<InlineCommentItem> {
  const { data } = await api.post<InlineCommentItem>(`/api/v1/tasks/${taskId}/comments`, body)
  return data
}
