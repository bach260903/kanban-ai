import type { PrimaryLanguage, Project, ProjectListItem } from '../types'

import api from './api'

const PREFIX = '/api/v1/projects'

export type ProjectCreatePayload = {
  name: string
  description?: string | null
  primary_language: PrimaryLanguage
}

export type ProjectUpdatePayload = {
  name?: string
  description?: string | null
}

export async function listProjects(): Promise<ProjectListItem[]> {
  const { data } = await api.get<ProjectListItem[]>(PREFIX)
  return data
}

export async function createProject(payload: ProjectCreatePayload): Promise<Project> {
  const { data } = await api.post<Project>(PREFIX, payload)
  return data
}

export async function getProject(projectId: string): Promise<Project> {
  const { data } = await api.get<Project>(`${PREFIX}/${projectId}`)
  return data
}

export async function updateProject(projectId: string, body: ProjectUpdatePayload): Promise<Project> {
  const { data } = await api.put<Project>(`${PREFIX}/${projectId}`, body)
  return data
}
