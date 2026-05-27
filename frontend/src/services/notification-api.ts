import { api } from './api'

export interface NotificationItem {
  id: string
  type: string
  content: string
  reference_type: string | null
  reference_id: string | null
  project_id: string | null
  is_read: boolean
  created_at: string
}

export interface NotificationListResponse {
  total_unread: number
  items: NotificationItem[]
}

export async function getNotifications(params?: {
  unread_only?: boolean
  limit?: number
}): Promise<NotificationListResponse> {
  const res = await api.get<NotificationListResponse>('/api/v1/notifications', { params })
  return res.data
}

export async function markRead(id: string): Promise<void> {
  await api.patch(`/api/v1/notifications/${id}/read`)
}

export async function markAllRead(): Promise<{ marked: number }> {
  const res = await api.post<{ marked: number }>('/api/v1/notifications/read-all')
  return res.data
}
