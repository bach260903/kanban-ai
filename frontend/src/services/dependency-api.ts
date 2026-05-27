import api from './api'

const PROJECTS = '/api/v1/projects'

export type DependencyRef = {
  task_id: string
  title: string
  status: string
}

export type TaskDependenciesResponse = {
  task_id: string
  depends_on: DependencyRef[]
  blocked_by: DependencyRef[]
}

export type DependencyGraphNode = {
  id: string
  title: string
  status: string
}

export type DependencyGraphEdge = {
  from: string
  to: string
}

export type DependencyGraphResponse = {
  nodes: DependencyGraphNode[]
  edges: DependencyGraphEdge[]
}

export type DependencyRow = {
  task_id: string
  depends_on_task_id: string
  created_at: string
}

export async function getDeps(
  projectId: string,
  taskId: string,
): Promise<TaskDependenciesResponse> {
  const { data } = await api.get<TaskDependenciesResponse>(
    `${PROJECTS}/${projectId}/tasks/${taskId}/dependencies`,
  )
  return data
}

export async function addDep(
  projectId: string,
  taskId: string,
  dependsOnId: string,
): Promise<DependencyRow> {
  const { data } = await api.post<DependencyRow>(
    `${PROJECTS}/${projectId}/tasks/${taskId}/dependencies`,
    { depends_on_task_id: dependsOnId },
  )
  return data
}

export async function removeDep(
  projectId: string,
  taskId: string,
  depId: string,
): Promise<void> {
  await api.delete(`${PROJECTS}/${projectId}/tasks/${taskId}/dependencies/${depId}`)
}

export async function getGraph(projectId: string): Promise<DependencyGraphResponse> {
  const { data } = await api.get<DependencyGraphResponse>(
    `${PROJECTS}/${projectId}/dependency-graph`,
  )
  return data
}
