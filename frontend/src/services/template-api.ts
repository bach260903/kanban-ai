import api from './api'

export type TemplateResponse = {
  id: string
  name: string
  title_template: string
  description_template: string
  scope: string
  project_id: string | null
  created_by: string | null
  created_at: string
}

export type TemplateCreatePayload = {
  name: string
  title_template: string
  description_template: string
  scope: 'project' | 'global'
  project_id?: string | null
}

export async function listTemplates(
  scope?: string,
  projectId?: string,
): Promise<TemplateResponse[]> {
  const params: Record<string, string> = {}
  if (scope) params.scope = scope
  if (projectId) params.project_id = projectId
  const { data } = await api.get<TemplateResponse[]>('/api/v1/templates', { params })
  return data
}

export async function createTemplate(payload: TemplateCreatePayload): Promise<TemplateResponse> {
  const { data } = await api.post<TemplateResponse>('/api/v1/templates', payload)
  return data
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await api.delete(`/api/v1/templates/${templateId}`)
}
