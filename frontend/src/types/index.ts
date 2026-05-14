/** Phase 1–2 domain types — aligned with `data-model.md`, API JSON, and Phase 2 contracts (UUID + ISO-8601 strings). */

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

/** Row shape from ``GET /api/v1/projects`` (subset of `Project`). */
export interface ProjectListItem {
  id: UUID
  name: string
  description: string | null
  primary_language: PrimaryLanguage
  status: ProjectStatus
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

export type AgentRunStatus = 'running' | 'success' | 'failure' | 'awaiting_hil' | 'paused' | 'timeout'

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

// --- Phase 2 (US10 thought stream, US11 pause, US12 memory, US14 codebase map, US15 branch, US16 inline comments) ---

/** Persisted / relayed stream rows and ``contracts/websocket-protocol.md`` event_type values. */
export type StreamEventType =
  | 'THOUGHT'
  | 'TOOL_CALL'
  | 'TOOL_RESULT'
  | 'ACTION'
  | 'ERROR'
  | 'STATUS_CHANGE'

/** Envelope for one persisted thought-stream row (``stream_events`` / WS relay). ``content`` is JSON text from the API. */
export interface StreamEvent {
  id?: UUID
  task_id: UUID
  agent_run_id?: UUID | null
  event_type: StreamEventType
  content: string
  sequence_number: number | null
  timestamp: ISODateTime | null
}

/** ``GET /api/v1/projects/{id}/memory`` row (``MemoryEntryResponse`` / T095). */
export interface MemoryEntry {
  id: UUID
  project_id: UUID
  task_id: UUID | null
  entry_timestamp: ISODateTime
  summary: string
  files_affected: string[]
  lessons_learned: string
  created_at: ISODateTime
  updated_at: ISODateTime
}

/** Payload of ``GET /api/v1/projects/{id}/codebase-map`` (``map_json`` from ``codebase_maps`` / T099). */
export type CodebaseMapLanguage = PrimaryLanguage

export interface CodebaseMapFileEntry {
  path: string
  language: string
  size_bytes: number
  symbols: Record<string, unknown>[]
}

export interface CodebaseMap {
  project_id: string
  generated_at: ISODateTime
  language: CodebaseMapLanguage
  root_path: string
  file_count: number
  directory_tree: Record<string, unknown>
  files: CodebaseMapFileEntry[]
}

/** ``GET/POST .../tasks/{id}/comments`` row (``InlineCommentResponse``). */
export interface InlineComment {
  id: UUID
  task_id: UUID
  diff_id: UUID | null
  file_path: string
  line_number: number
  comment_text: string
  created_at: ISODateTime
}

/** ``GET .../tasks/{id}/pause-state`` (``PauseStateResponse`` / T085). */
export interface PauseState {
  task_id: UUID
  is_paused: boolean
  state?: string | null
  steering_instructions?: string | null
  agent_run_id?: UUID | null
  paused_at?: ISODateTime | null
  resumed_at?: ISODateTime | null
}

/** ``GET /api/v1/tasks/{id}/branch`` (``TaskBranchResponse`` / T104). */
export type TaskBranchStatus = 'active' | 'merged' | 'conflict'

export interface TaskBranch {
  task_id: UUID
  branch_name: string
  status: TaskBranchStatus
  created_at: ISODateTime
  merged_at: ISODateTime | null
}
