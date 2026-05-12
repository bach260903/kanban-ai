/** Phase 1 domain types — aligned with `data-model.md` and API JSON (UUID + ISO-8601 strings). */

export type UUID = string

export type ISODateTime = string

export type PrimaryLanguage = 'python' | 'javascript' | 'typescript'

export type ProjectStatus = 'active' | 'archived'

export interface Project {
  id: UUID
  name: string
  description: string | null
  primary_language: PrimaryLanguage
  constitution: string
  status: ProjectStatus
  created_at: ISODateTime
  updated_at: ISODateTime
}

export type DocumentType = 'SPEC' | 'PLAN'

export type DocumentStatus = 'draft' | 'approved' | 'revision_requested'

export interface Document {
  id: UUID
  project_id: UUID
  type: DocumentType
  content: string
  status: DocumentStatus
  version: number
  created_at: ISODateTime
  updated_at: ISODateTime
}

export type TaskStatus =
  | 'todo'
  | 'in_progress'
  | 'review'
  | 'done'
  | 'rejected'
  | 'conflict'

export interface Task {
  id: UUID
  project_id: UUID
  title: string
  description: string | null
  status: TaskStatus
  priority: number
  created_at: ISODateTime
  updated_at: ISODateTime
}

export type AgentType = 'architect' | 'coder' | 'reviewer'

export type AgentRunStatus = 'running' | 'success' | 'failure' | 'awaiting_hil' | 'paused'

export interface AgentRun {
  id: UUID
  task_id: UUID | null
  project_id: UUID
  agent_type: AgentType
  agent_version: string
  status: AgentRunStatus
  input_artifacts: string[]
  output_artifacts: string[]
  started_at: ISODateTime
  completed_at: ISODateTime | null
  result: Record<string, unknown> | null
}

export type DiffReviewStatus = 'pending' | 'approved' | 'rejected'

export interface Diff {
  id: UUID
  task_id: UUID
  agent_run_id: UUID | null
  content: string
  original_content: string
  modified_content: string
  files_affected: string[]
  review_status: DiffReviewStatus
  created_at: ISODateTime
}

export type FeedbackReferenceType = 'document' | 'task'

export interface Feedback {
  id: UUID
  project_id: UUID
  reference_type: FeedbackReferenceType
  reference_id: UUID
  content: string
  created_at: ISODateTime
}

export type AuditLogResult = 'success' | 'failure' | 'awaiting_hil'

export interface AuditLog {
  id: UUID
  agent_id: string
  agent_version: string
  action_type: string
  action_description: string
  timestamp: ISODateTime
  input_refs: string[]
  output_refs: string[]
  result: AuditLogResult
  project_id: UUID | null
  task_id: UUID | null
}
