import type { AgentRun, Document, DocumentType, ISODateTime, UUID } from '../types'

import api from './api'

const PROJECTS_PREFIX = '/api/v1/projects'
const AGENT_RUNS_PREFIX = '/api/v1/agent-runs'

/** Row from ``GET /api/v1/projects/{id}/documents`` (no body content). */
export type DocumentListItem = {
  id: UUID
  project_id: UUID
  type: DocumentType
  status: Document['status']
  version: number
  created_at: ISODateTime
  updated_at: ISODateTime
}

export type GenerateSpecPayload = {
  intent: string
  /** When true, replaces an approved SPEC after server confirmation (see API contract). */
  force?: boolean
}

export type GenerateSpecResponse = {
  agent_run_id: UUID
  intent_id: UUID
  document_id: UUID
  status: string
  message: string
}

/**
 * Per-(projectId, type) cache:
 * - `inflight`: dedupes concurrent fetches inside the React StrictMode double-mount window
 *   so SPEC/PLAN only hit the API once per navigation.
 * - `result` + `fetchedAt`: short TTL cache. Callers can pass ``forceRefresh: true`` to bust.
 */
type DocumentCacheKey = string
const documentListInflight = new Map<DocumentCacheKey, Promise<DocumentListItem[]>>()
const documentListCache = new Map<
  DocumentCacheKey,
  { data: DocumentListItem[]; fetchedAt: number }
>()
const DOCUMENT_LIST_STALE_MS = 30_000

function documentListKey(projectId: string, type?: DocumentType): DocumentCacheKey {
  return `${projectId}:${type ?? '*'}`
}

export function invalidateDocuments(projectId: string, type?: DocumentType): void {
  if (type) {
    documentListCache.delete(documentListKey(projectId, type))
    documentListInflight.delete(documentListKey(projectId, type))
    return
  }
  for (const key of Array.from(documentListCache.keys())) {
    if (key.startsWith(`${projectId}:`)) documentListCache.delete(key)
  }
  for (const key of Array.from(documentListInflight.keys())) {
    if (key.startsWith(`${projectId}:`)) documentListInflight.delete(key)
  }
}

export async function getDocuments(
  projectId: string,
  type?: DocumentType,
  options?: { signal?: AbortSignal; forceRefresh?: boolean },
): Promise<DocumentListItem[]> {
  const key = documentListKey(projectId, type)

  if (!options?.forceRefresh) {
    const cached = documentListCache.get(key)
    if (cached && Date.now() - cached.fetchedAt < DOCUMENT_LIST_STALE_MS) {
      if (options?.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return cached.data
    }
    const inflight = documentListInflight.get(key)
    if (inflight) {
      const data = await inflight
      if (options?.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
      return data
    }
  }

  // NOTE: We deliberately do NOT pass the consumer's `signal` into axios.
  // The cache + inflight map are shared across components, so a single
  // aborted caller (e.g. React StrictMode's first-pass cleanup) must not
  // cancel the network request that every other caller depends on. The
  // caller can still bail by checking `signal.aborted` after we return.
  const promise = (async () => {
    const { data } = await api.get<DocumentListItem[]>(
      `${PROJECTS_PREFIX}/${projectId}/documents`,
      {
        params: type != null ? { type } : undefined,
      },
    )
    documentListCache.set(key, { data, fetchedAt: Date.now() })
    return data
  })()

  documentListInflight.set(key, promise)
  try {
    const data = await promise
    if (options?.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    return data
  } finally {
    if (documentListInflight.get(key) === promise) {
      documentListInflight.delete(key)
    }
  }
}

export async function getDocument(projectId: string, documentId: string): Promise<Document> {
  const { data } = await api.get<Document>(`${PROJECTS_PREFIX}/${projectId}/documents/${documentId}`)
  return data
}

export async function updateDocument(
  projectId: string,
  documentId: string,
  content: string,
  options?: { force?: boolean },
): Promise<Document> {
  const { data } = await api.put<Document>(`${PROJECTS_PREFIX}/${projectId}/documents/${documentId}`, {
    content,
  }, {
    params: options?.force === true ? { force: true } : undefined,
  })
  invalidateDocuments(projectId)
  return data
}

export async function generateSpec(
  projectId: string,
  payload: GenerateSpecPayload,
): Promise<GenerateSpecResponse> {
  const { data } = await api.post<GenerateSpecResponse>(
    `${PROJECTS_PREFIX}/${projectId}/generate-spec`,
    { intent: payload.intent },
    {
      params: payload.force === true ? { force: true } : undefined,
    },
  )
  invalidateDocuments(projectId, 'SPEC')
  return data
}

export type GeneratePlanResponse = {
  agent_run_id: UUID
  document_id: UUID
  status: string
  message: string
}

export async function generatePlan(projectId: string): Promise<GeneratePlanResponse> {
  const { data } = await api.post<GeneratePlanResponse>(`${PROJECTS_PREFIX}/${projectId}/generate-plan`, {})
  invalidateDocuments(projectId, 'PLAN')
  return data
}

export type DocumentApproveResponse = {
  id: UUID
  status: Document['status']
  updated_at: ISODateTime
  /** Present when approving SPEC triggers automatic PLAN generation. */
  plan_agent_run_id?: UUID | null
  plan_generation_started?: boolean
}

export type DocumentReviseResponse = {
  id: UUID
  status: Document['status']
  feedback_id: UUID
  agent_run_id: UUID
  updated_at: ISODateTime
}

export async function approveDocument(
  projectId: string,
  documentId: string,
): Promise<DocumentApproveResponse> {
  const { data } = await api.post<DocumentApproveResponse>(
    `${PROJECTS_PREFIX}/${projectId}/documents/${documentId}/approve`,
    {},
  )
  invalidateDocuments(projectId)
  return data
}

export async function reviseDocument(
  projectId: string,
  documentId: string,
  feedback: string,
): Promise<DocumentReviseResponse> {
  const { data } = await api.post<DocumentReviseResponse>(
    `${PROJECTS_PREFIX}/${projectId}/documents/${documentId}/revise`,
    { feedback },
  )
  invalidateDocuments(projectId)
  return data
}

export async function getAgentRun(runId: string): Promise<AgentRun> {
  const { data } = await api.get<AgentRun>(`${AGENT_RUNS_PREFIX}/${runId}`)
  return data
}
