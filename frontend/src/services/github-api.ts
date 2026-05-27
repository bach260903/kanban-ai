import { isAxiosError } from 'axios'

import { api } from './api'

export interface GitHubConfig {
  repo_full_name: string
  default_base_branch: string
  enabled: boolean
}

export interface GitHubConfigUpsert {
  repo_full_name: string
  pat: string
  default_base_branch?: string
}

export async function getGitHubConfig(projectId: string): Promise<GitHubConfig | null> {
  try {
    const res = await api.get<GitHubConfig>(`/api/v1/projects/${projectId}/github`)
    return res.data
  } catch (err: unknown) {
    if (isAxiosError(err) && err.response?.status === 404) return null
    throw err
  }
}

export async function upsertGitHubConfig(
  projectId: string,
  data: GitHubConfigUpsert,
): Promise<GitHubConfig> {
  const res = await api.put<GitHubConfig>(`/api/v1/projects/${projectId}/github`, {
    default_base_branch: 'main',
    ...data,
  })
  return res.data
}
