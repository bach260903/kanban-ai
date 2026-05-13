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

export async function getDocuments(
  projectId: string,
  type?: DocumentType,
): Promise<DocumentListItem[]> {
  const { data } = await api.get<DocumentListItem[]>(`${PROJECTS_PREFIX}/${projectId}/documents`, {
    params: type != null ? { type } : undefined,
  })
  return data
}

export async function getDocument(projectId: string, documentId: string): Promise<Document> {
  const { data } = await api.get<Document>(`${PROJECTS_PREFIX}/${projectId}/documents/${documentId}`)
  return data
}

export async function updateDocument(
  projectId: string,
  documentId: string,
  content: string,
): Promise<Document> {
  const { data } = await api.put<Document>(`${PROJECTS_PREFIX}/${projectId}/documents/${documentId}`, {
    content,
  })
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
  return data
}

export async function getAgentRun(runId: string): Promise<AgentRun> {
  const { data } = await api.get<AgentRun>(`${AGENT_RUNS_PREFIX}/${runId}`)
  return data
}
