import api from './api'

const prefix = (projectId: string) => `/api/v1/projects/${projectId}/memory`

export type MemoryEntry = {
  id: string
  project_id: string
  task_id: string | null
  entry_timestamp: string
  summary: string
  files_affected: string[]
  lessons_learned: string
  created_at: string
  updated_at: string
}

export type MemoryEntryUpdatePayload = {
  summary?: string
  lessons_learned?: string
}

export async function listMemoryEntries(projectId: string): Promise<MemoryEntry[]> {
  const { data } = await api.get<MemoryEntry[]>(prefix(projectId))
  return data
}

export async function updateMemoryEntry(
  projectId: string,
  entryId: string,
  body: MemoryEntryUpdatePayload,
): Promise<MemoryEntry> {
  const { data } = await api.put<MemoryEntry>(`${prefix(projectId)}/${entryId}`, body)
  return data
}

export async function deleteMemoryEntry(projectId: string, entryId: string): Promise<void> {
  await api.delete(`${prefix(projectId)}/${entryId}`)
}
