/**
 * Deployment configuration API client.
 * Extends the base pipeline-api with deployment-specific CRUD.
 */

import api from './api'

export type DeploymentConfigOut = {
  id: string
  project_id: string
  provider: 'vercel' | 'railway' | 'none'
  project_name: string
  team_id: string | null
  base_url: string | null
  enabled: boolean
  created_at: string
  updated_at: string
}

export type DeploymentConfigCreate = {
  provider: 'vercel' | 'railway' | 'none'
  token: string
  project_name: string
  team_id?: string | null
  base_url?: string | null
  enabled?: boolean
}

export type DeploymentConfigTestResult = {
  ok: boolean
  message: string
}

export async function getDeploymentConfig(projectId: string): Promise<DeploymentConfigOut | null> {
  const { data } = await api.get<DeploymentConfigOut | null>(
    `/api/v1/projects/${projectId}/deployment-config`,
  )
  return data ?? null
}

export async function upsertDeploymentConfig(
  projectId: string,
  body: DeploymentConfigCreate,
): Promise<DeploymentConfigOut> {
  const { data } = await api.put<DeploymentConfigOut>(
    `/api/v1/projects/${projectId}/deployment-config`,
    body,
  )
  return data
}

export async function testDeploymentConfig(
  projectId: string,
  body: { provider: string; token: string; project_name: string; team_id?: string | null },
): Promise<DeploymentConfigTestResult> {
  const { data } = await api.post<DeploymentConfigTestResult>(
    `/api/v1/projects/${projectId}/deployment-config/test`,
    body,
  )
  return data
}

export async function deleteDeploymentConfig(projectId: string): Promise<void> {
  await api.delete(`/api/v1/projects/${projectId}/deployment-config`)
}
