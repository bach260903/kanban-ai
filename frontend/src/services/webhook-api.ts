import { api } from './api'

export interface WebhookItem {
  id: string
  url: string
  events: string[]
  enabled: boolean
  created_at: string
}

export interface TestWebhookResult {
  delivered: boolean
  http_status: number | null
  response_time_ms: number
  response_body: string | null
}

export interface DeliveryItem {
  id: string
  event_type: string
  status: 'pending' | 'success' | 'failed' | 'retrying' | string
  http_status: number | null
  response_body: string | null
  attempts: number
  last_attempt_at: string | null
  created_at: string
}

export async function listWebhooks(projectId: string): Promise<WebhookItem[]> {
  const res = await api.get<WebhookItem[]>(`/api/v1/projects/${projectId}/webhooks`)
  return res.data
}

export async function createWebhook(
  projectId: string,
  data: { url: string; secret?: string; events: string[] },
): Promise<WebhookItem> {
  const res = await api.post<WebhookItem>(`/api/v1/projects/${projectId}/webhooks`, data)
  return res.data
}

export async function patchWebhook(
  projectId: string,
  id: string,
  data: Partial<{ enabled: boolean; events: string[]; url: string; secret: string }>,
): Promise<WebhookItem> {
  const res = await api.patch<WebhookItem>(`/api/v1/projects/${projectId}/webhooks/${id}`, data)
  return res.data
}

export async function deleteWebhook(projectId: string, id: string): Promise<void> {
  await api.delete(`/api/v1/projects/${projectId}/webhooks/${id}`)
}

export async function testWebhook(projectId: string, id: string): Promise<TestWebhookResult> {
  const res = await api.post<TestWebhookResult>(
    `/api/v1/projects/${projectId}/webhooks/${id}/test`,
  )
  return res.data
}

export async function getWebhookDeliveries(
  projectId: string,
  id: string,
): Promise<DeliveryItem[]> {
  const res = await api.get<DeliveryItem[]>(
    `/api/v1/projects/${projectId}/webhooks/${id}/deliveries`,
  )
  return res.data
}
