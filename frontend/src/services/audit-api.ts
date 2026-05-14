import api from './api'

const prefix = (projectId: string) => `/api/v1/projects/${projectId}/audit-logs`

export type AuditLogRow = {
  id: string
  agent_id: string
  agent_version: string
  action_type: string
  timestamp: string
  result: string
}

export type AuditLogsPage = {
  items: AuditLogRow[]
  total: number
  offset: number
  limit: number
}

export async function getAuditLogs(
  projectId: string,
  params?: { offset?: number; limit?: number },
): Promise<AuditLogsPage> {
  const { data } = await api.get<AuditLogsPage>(prefix(projectId), {
    params: { offset: params?.offset ?? 0, limit: params?.limit ?? 50 },
  })
  return data
}
