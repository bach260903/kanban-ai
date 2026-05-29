import api from './api'
import { getAuthToken } from './api'

export type PipelineStepOut = {
  id: string
  run_id: string
  step_key: string
  status: 'pending' | 'running' | 'success' | 'failure' | 'skipped'
  attempt: number
  logs: string | null
  ai_reasoning: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  created_at: string
  failure_analyses: FailureAnalysisOut[]
}

export type PipelineRunOut = {
  id: string
  project_id: string
  task_id: string | null
  status: 'queued' | 'running' | 'success' | 'failure' | 'cancelled'
  triggered_by: string | null
  branch_name: string | null
  commit_sha: string | null
  ai_summary: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  steps: PipelineStepOut[]
}

export type DeploymentOut = {
  id: string
  project_id: string
  task_id: string | null
  run_id: string | null
  status: 'pending' | 'deploying' | 'healthy' | 'degraded' | 'rolled_back' | 'skipped'
  environment: string
  provider: string | null
  external_id: string | null
  preview_url: string | null
  branch_name: string | null
  commit_sha: string | null
  deploy_logs: string | null
  error_message: string | null
  risk_score: number | null
  duration_ms: number | null
  deployed_at: string | null
  created_at: string
}

export type FailureAnalysisOut = {
  id: string
  step_id: string
  run_id: string
  root_cause: string
  confidence: number
  fix_strategy: string
  risk_level: 'low' | 'medium' | 'high'
  is_auto_fixable: boolean
  human_approval_required: boolean
  patch_applied: boolean
  patch_summary: string | null
  retry_triggered: boolean
  retry_attempt: number
  approved_by: string | null
  approved_at: string | null
  created_at: string
}

// Pipeline events (SSE)
export type PipelineEvent =
  | { type: 'pipeline_started'; run_id: string; project_id: string }
  | { type: 'step_started'; run_id: string; step_key: string; step_id: string }
  | { type: 'step_completed'; run_id: string; step_key: string; step_id: string; status: string; duration_ms: number; ai_reasoning: string; attempt?: number; was_retry?: boolean }
  | { type: 'pipeline_completed'; run_id: string; status: string; ai_summary: string; preview_url?: string | null }
  | { type: 'pipeline_failed'; run_id: string; status: string; ai_summary: string; preview_url?: string | null }
  | { type: 'pipeline_snapshot'; run_id: string; status: string; preview_url: string | null; steps: Array<{ step_key: string; status: string; duration_ms: number | null; ai_reasoning: string | null; logs: string }> }
  | { type: 'step_analysis_started'; run_id: string; step_key: string; step_id: string }
  | { type: 'step_analysis_complete'; run_id: string; step_key: string; step_id: string; analysis_id: string; root_cause: string; confidence: number; fix_strategy: string; is_auto_fixable: boolean; human_approval_required: boolean; risk_level: string }
  | { type: 'step_fix_started'; run_id: string; step_key: string; step_id: string; analysis_id: string }
  | { type: 'step_fix_complete'; run_id: string; step_key: string; step_id: string; analysis_id: string; patch_summary: string; success: boolean }
  | { type: 'step_retry_started'; run_id: string; step_key: string; step_id: string; attempt: number; reason: string }
  | { type: 'approval_required'; run_id: string; step_key: string; step_id: string; analysis_id: string; root_cause: string; fix_strategy: string }
  | { type: 'ping' }

export async function listPipelineRuns(projectId: string): Promise<PipelineRunOut[]> {
  const { data } = await api.get<PipelineRunOut[]>(`/api/v1/projects/${projectId}/pipeline-runs`)
  return data
}

export async function listTaskPipelineRuns(projectId: string, taskId: string): Promise<PipelineRunOut[]> {
  const { data } = await api.get<PipelineRunOut[]>(`/api/v1/projects/${projectId}/tasks/${taskId}/pipeline-runs`)
  return data
}

export async function getPipelineRun(runId: string): Promise<PipelineRunOut> {
  const { data } = await api.get<PipelineRunOut>(`/api/v1/pipeline-runs/${runId}`)
  return data
}

/** Re-run the pipeline for an existing run (same task, fresh execution). Returns the new run. */
export async function rerunPipelineRun(projectId: string, runId: string): Promise<PipelineRunOut> {
  const { data } = await api.post<PipelineRunOut>(
    `/api/v1/projects/${projectId}/pipeline-runs/${runId}/rerun`,
  )
  return data
}

export async function listDeployments(projectId: string): Promise<DeploymentOut[]> {
  const { data } = await api.get<DeploymentOut[]>(`/api/v1/projects/${projectId}/deployments`)
  return data
}

export async function getDeployment(projectId: string, deploymentId: string): Promise<DeploymentOut> {
  const { data } = await api.get<DeploymentOut>(`/api/v1/projects/${projectId}/deployments/${deploymentId}`)
  return data
}

export async function listRunFailureAnalyses(runId: string): Promise<FailureAnalysisOut[]> {
  const { data } = await api.get<FailureAnalysisOut[]>(`/api/v1/pipeline-runs/${runId}/failure-analyses`)
  return data
}

/**
 * Open an SSE connection to the pipeline run stream.
 * Calls onEvent for each event, onDone when the stream closes.
 * Returns a cleanup function to close the EventSource.
 */
export function subscribePipelineRun(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  onDone?: () => void,
): () => void {
  const token = getAuthToken()
  // Pass token via query param since EventSource doesn't support headers
  const url = `${(import.meta as { env?: Record<string, string> }).env?.VITE_API_URL ?? 'http://localhost:8000'}/api/v1/pipeline-runs/${runId}/stream${token ? `?token=${token}` : ''}`

  const es = new EventSource(url)

  es.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data) as PipelineEvent
      onEvent(parsed)
      if (parsed.type === 'pipeline_completed' || parsed.type === 'pipeline_failed') {
        es.close()
        onDone?.()
      }
    } catch {
      // ignore malformed event
    }
  }

  es.onerror = () => {
    es.close()
    onDone?.()
  }

  return () => es.close()
}
