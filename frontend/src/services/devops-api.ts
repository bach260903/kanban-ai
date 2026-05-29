import api from './api'

// ── Types ──────────────────────────────────────────────────────────────────────

export type HealthCheckOut = {
  id: string
  deployment_id: string
  project_id: string
  status: 'healthy' | 'degraded' | 'unreachable' | 'unknown'
  http_status: number | null
  latency_ms: number | null
  response_snippet: string | null
  error_message: string | null
  checked_at: string
}

export type IncidentOut = {
  id: string
  deployment_id: string
  project_id: string
  incident_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  description: string
  ai_reasoning: string | null
  risk_score: number | null
  metric_snapshot: Record<string, unknown> | null
  rollback_triggered: boolean
  resolved: boolean
  resolved_at: string | null
  created_at: string
}

export type RollbackEventOut = {
  id: string
  deployment_id: string
  project_id: string
  triggered_by: 'manual' | 'ai_anomaly' | 'health_fail'
  previous_deployment_id: string | null
  status: 'pending' | 'rolling_back' | 'completed' | 'failed' | 'skipped'
  reason: string
  ai_reasoning: string | null
  alert_sent: boolean
  completed_at: string | null
  created_at: string
}

export type RiskAssessmentOut = {
  risk_score: number
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  reasoning: string
  risk_factors: string[]
  blast_radius: string
  safe_to_deploy: boolean
  via_llm: boolean
}

export type DeploymentHealthSummary = {
  deployment_id: string
  project_id: string
  health_status: string | null
  last_checked_at: string | null
  latest_http_status: number | null
  latest_latency_ms: number | null
  consecutive_failures: number
  open_incidents: number
  last_rollback_at: string | null
}

export type AlertConfigOut = {
  discord_webhook_url: string | null
  slack_webhook_url: string | null
  health_check_path: string | null
  alert_on_anomaly: boolean
  monitor_duration_minutes: number
}

export type AlertConfigUpdate = {
  discord_webhook_url?: string | null
  slack_webhook_url?: string | null
  health_check_path?: string | null
  alert_on_anomaly?: boolean
  monitor_duration_minutes?: number
}

// ── API functions ──────────────────────────────────────────────────────────────

export async function getHealthSummary(projectId: string): Promise<DeploymentHealthSummary[]> {
  const res = await api.get(`/api/v1/projects/${projectId}/devops/health-summary`)
  return res.data
}

export async function listIncidents(
  projectId: string,
  options?: { resolved?: boolean; limit?: number }
): Promise<IncidentOut[]> {
  const params: Record<string, unknown> = {}
  if (options?.resolved !== undefined) params.resolved = options.resolved
  if (options?.limit !== undefined) params.limit = options.limit
  const res = await api.get(`/api/v1/projects/${projectId}/devops/incidents`, { params })
  return res.data
}

export async function listRollbacks(
  projectId: string,
  limit = 50
): Promise<RollbackEventOut[]> {
  const res = await api.get(`/api/v1/projects/${projectId}/devops/rollbacks`, { params: { limit } })
  return res.data
}

export async function getAlertConfig(projectId: string): Promise<AlertConfigOut> {
  const res = await api.get(`/api/v1/projects/${projectId}/devops/alert-config`)
  return res.data
}

export async function updateAlertConfig(
  projectId: string,
  update: AlertConfigUpdate
): Promise<AlertConfigOut> {
  const res = await api.put(`/api/v1/projects/${projectId}/devops/alert-config`, update)
  return res.data
}

export async function getHealthChecks(
  deploymentId: string,
  limit = 100
): Promise<HealthCheckOut[]> {
  const res = await api.get(`/api/v1/deployments/${deploymentId}/health-checks`, { params: { limit } })
  return res.data
}

export async function triggerManualRollback(
  deploymentId: string,
  reason: string
): Promise<RollbackEventOut> {
  const res = await api.post(`/api/v1/deployments/${deploymentId}/rollback`, { reason })
  return res.data
}

export async function getRiskAssessment(deploymentId: string): Promise<RiskAssessmentOut> {
  const res = await api.get(`/api/v1/deployments/${deploymentId}/risk-assessment`)
  return res.data
}
