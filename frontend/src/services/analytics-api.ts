import api from './api'

export type ProjectDashboard = {
  id: string
  name: string
  primary_language: string
  task_counts: Record<string, number>
  stale_count: number
  member_count: number
}

export type DashboardResponse = {
  projects: ProjectDashboard[]
}

export type BackendMetric = {
  agent_type: string
  avg_seconds: number
  first_approve_rate: number
  error_count: number
}

export type MemberMetric = {
  display_name: string
  tasks_done: number
  tasks_in_progress: number
}

export type ErrorBreakdownItem = {
  action_type: string
  count: number
}

export type AnalyticsResponse = {
  period: string
  by_backend: BackendMetric[]
  by_member: MemberMetric[]
  reviewer_avg_score: number | null
  error_breakdown: ErrorBreakdownItem[]
}

export type AnalyticsRange = '7d' | '30d' | 'custom'

export async function getDashboard(opts?: { signal?: AbortSignal }): Promise<DashboardResponse> {
  const { data } = await api.get<DashboardResponse>('/api/v1/dashboard', {
    signal: opts?.signal,
  })
  return data
}

export async function getProjectAnalytics(
  projectId: string,
  range: AnalyticsRange,
  fromDate?: string,
  toDate?: string,
  opts?: { signal?: AbortSignal },
): Promise<AnalyticsResponse> {
  const params: Record<string, string> = { range }
  if (fromDate) params.from_date = fromDate
  if (toDate) params.to_date = toDate
  const { data } = await api.get<AnalyticsResponse>(
    `/api/v1/projects/${projectId}/analytics`,
    { params, signal: opts?.signal },
  )
  return data
}
