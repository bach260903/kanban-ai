# Data Model: Neo-Kanban

**Phase**: 1 (core) + Phase 2 (additions marked)
**Date**: 2026-05-11

---

## Entity Relationship Overview

```
projects ──────────────────────────────────────────────────────────
   │                                                               │
   ├──< documents (type: SPEC | PLAN)                             │
   │      └──< feedbacks (reference_type: document)               │
   │                                                               │
   ├──< tasks ─────────────────────────────────────────────────┐  │
   │      ├──< agent_runs                                       │  │
   │      │      └──< stream_events          [Phase 2]         │  │
   │      ├──< diffs                                           │  │
   │      │      └──< inline_comments        [Phase 2]         │  │
   │      ├──< feedbacks (reference_type: task)                │  │
   │      ├── agent_pause_states (1:1)       [Phase 2]         │  │
   │      └── task_branches (1:1)            [Phase 2]         │  │
   │                                                            │  │
   ├──< audit_logs                                             │  │
   ├──< memory_entries                       [Phase 2]         │  │
   └──< codebase_maps                        [Phase 2]         │  │
                                                               │  │
   ← project_id on all child tables ─────────────────────────────┘
```

---

## Phase 1 Entities

### `projects`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, default gen_random_uuid() | Project identifier |
| `name` | VARCHAR(255) | UNIQUE NOT NULL | Project name (must be unique across system) |
| `description` | TEXT | nullable | Short description |
| `primary_language` | VARCHAR(50) | NOT NULL | e.g., `python`, `typescript` |
| `constitution` | TEXT | NOT NULL, default `''` | Markdown constitution text |
| `status` | VARCHAR(20) | NOT NULL, default `active`, CHECK IN (`active`,`archived`) | Project lifecycle status |
| `created_at` | TIMESTAMPTZ | NOT NULL, default NOW() | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default NOW() | Last modification timestamp |

**Indexes**: `UNIQUE(name)`
**Triggers**: `updated_at` auto-updated on any row change

---

### `documents`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Document identifier |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project |
| `type` | VARCHAR(10) | NOT NULL, CHECK IN (`SPEC`,`PLAN`) | Document kind |
| `content` | TEXT | NOT NULL, default `''` | Markdown content |
| `status` | VARCHAR(30) | NOT NULL, default `draft`, CHECK IN (`draft`,`approved`,`revision_requested`) | Approval lifecycle |
| `version` | INTEGER | NOT NULL, default 1 | Incremented on each agent regeneration |
| `created_at` | TIMESTAMPTZ | NOT NULL, default NOW() | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default NOW() | — |

**Business rules**:
- Only one `PLAN` document may be `approved` per project at a time (enforced at service layer).
- `version` increments when Agent regenerates after `revision_requested`.
- Manual PO edits update `content` without changing `status` or incrementing `version`.
- Transition `draft → approved` unlocks the next workflow step; `approved → revision_requested`
  re-locks it and triggers Agent re-generation.

---

### `tasks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Task identifier |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project |
| `title` | VARCHAR(500) | NOT NULL | Task title |
| `description` | TEXT | nullable | Detailed task description |
| `status` | VARCHAR(20) | NOT NULL, default `todo`, CHECK IN (`todo`,`in_progress`,`review`,`done`,`rejected`,`conflict`) | Kanban position |
| `priority` | INTEGER | NOT NULL, default 0 | Lower number = higher priority (display order) |
| `created_at` | TIMESTAMPTZ | NOT NULL | — |
| `updated_at` | TIMESTAMPTZ | NOT NULL | — |

**WIP constraint** (DB-level, atomic):
```sql
CONSTRAINT one_in_progress_per_project
    EXCLUDE USING btree (project_id WITH =)
    WHERE (status = 'in_progress')
```

**Valid state transitions** (enforced by `kanban_service.py`):

```
todo          → in_progress   (PO drags task; triggers Coder Agent)
in_progress   → review        (Agent completes coding)
review        → done          (PO approves diff)
review        → in_progress   (PO rejects diff; Agent retries)
in_progress   → rejected      (PO manually cancels; system use only)
in_progress   → conflict      (merge conflict detected; Phase 2)
```

Backward transitions other than `review → in_progress` are **forbidden** at the API layer.

---

### `agent_runs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Run identifier |
| `task_id` | UUID | FK → tasks.id ON DELETE SET NULL, nullable | Associated task (null for SPEC/PLAN runs) |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project |
| `agent_type` | VARCHAR(20) | NOT NULL, CHECK IN (`architect`,`coder`,`reviewer`) | Which agent ran |
| `agent_version` | VARCHAR(20) | NOT NULL, default `1.0.0` | Agent version for audit trail |
| `status` | VARCHAR(20) | NOT NULL, default `running`, CHECK IN (`running`,`success`,`failure`,`awaiting_hil`,`paused`) | Run lifecycle |
| `input_artifacts` | TEXT[] | NOT NULL, default `{}` | Paths or DB IDs of inputs read |
| `output_artifacts` | TEXT[] | NOT NULL, default `{}` | Paths or DB IDs of outputs written |
| `started_at` | TIMESTAMPTZ | NOT NULL | — |
| `completed_at` | TIMESTAMPTZ | nullable | Null while running |
| `result` | JSONB | nullable | Structured result payload |

---

### `diffs`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Diff identifier |
| `task_id` | UUID | FK → tasks.id ON DELETE CASCADE | Owning task |
| `agent_run_id` | UUID | FK → agent_runs.id ON DELETE SET NULL, nullable | Producing run |
| `content` | TEXT | NOT NULL | Unified diff format |
| `original_content` | TEXT | NOT NULL | Full original file(s) text (for Monaco DiffEditor) |
| `modified_content` | TEXT | NOT NULL | Full modified file(s) text (for Monaco DiffEditor) |
| `files_affected` | TEXT[] | NOT NULL, default `{}` | List of file paths |
| `review_status` | VARCHAR(10) | NOT NULL, default `pending`, CHECK IN (`pending`,`approved`,`rejected`) | Review decision |
| `created_at` | TIMESTAMPTZ | NOT NULL | — |

---

### `feedbacks`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Feedback identifier |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project |
| `reference_type` | VARCHAR(10) | NOT NULL, CHECK IN (`document`,`task`) | What the feedback targets |
| `reference_id` | UUID | NOT NULL | ID of the referenced document or task |
| `content` | TEXT | NOT NULL | PO's feedback text |
| `created_at` | TIMESTAMPTZ | NOT NULL | — |

---

### `audit_logs` — Immutable

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Log entry identifier |
| `agent_id` | VARCHAR(100) | NOT NULL | e.g., `architect-v1`, `coder-v1`, `system` |
| `agent_version` | VARCHAR(20) | NOT NULL | Agent version |
| `action_type` | VARCHAR(100) | NOT NULL | e.g., `generate_spec`, `write_file`, `approve_task` |
| `action_description` | TEXT | NOT NULL | Human-readable action description |
| `timestamp` | TIMESTAMPTZ | NOT NULL | UTC timestamp of the action |
| `input_refs` | TEXT[] | NOT NULL, default `{}` | Input artifact paths / DB record IDs |
| `output_refs` | TEXT[] | NOT NULL, default `{}` | Output artifact paths / state changes |
| `result` | VARCHAR(15) | NOT NULL, CHECK IN (`success`,`failure`,`awaiting_hil`) | Outcome |
| `project_id` | UUID | FK → projects.id ON DELETE SET NULL, nullable | For filtering |
| `task_id` | UUID | FK → tasks.id ON DELETE SET NULL, nullable | For filtering |

**Immutability enforcement**:
```sql
CREATE RULE audit_logs_no_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE audit_logs_no_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
```
At service layer, `audit_service.py` only exposes `write_pending_log()` (INSERT) and
`finalise_log()` (UPDATE — but this is permitted internally before the DB rule fires, as
finalise uses a direct session bypass). **Never expose an update/delete endpoint for audit_logs.**

---

## Phase 2 Entities

### `stream_events` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Event identifier |
| `task_id` | UUID | FK → tasks.id ON DELETE CASCADE | Owning task |
| `agent_run_id` | UUID | FK → agent_runs.id ON DELETE SET NULL, nullable | Producing run |
| `event_type` | VARCHAR(20) | NOT NULL, CHECK IN (`THOUGHT`,`TOOL_CALL`,`TOOL_RESULT`,`ACTION`,`ERROR`,`STATUS_CHANGE`) | Event kind |
| `content` | TEXT | NOT NULL | JSON-encoded event payload |
| `sequence_number` | INTEGER | NOT NULL | Monotonically increasing per task |
| `timestamp` | TIMESTAMPTZ | NOT NULL | UTC timestamp |

**Unique constraint**: `UNIQUE(task_id, sequence_number)` — prevents duplicate sequence numbers.

**Usage**: Written by `event_publisher.py` before publishing to Redis. Used by `ws_handler.py`
for `CATCH_UP` replay on reconnect.

---

### `agent_pause_states` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | — |
| `task_id` | UUID | UNIQUE FK → tasks.id ON DELETE CASCADE | One pause record per task |
| `agent_run_id` | UUID | FK → agent_runs.id | The run being paused |
| `state` | VARCHAR(10) | NOT NULL, default `running`, CHECK IN (`running`,`paused`) | Current pause state |
| `steering_instructions` | TEXT | nullable | PO's instructions set on Resume |
| `paused_at` | TIMESTAMPTZ | nullable | When PO triggered Pause |
| `resumed_at` | TIMESTAMPTZ | nullable | When PO triggered Resume |
| `updated_at` | TIMESTAMPTZ | NOT NULL | — |

**Note**: The Redis key `pause:{task_id}` is the authoritative live signal. This table is the
persistent record for audit and resume instruction retrieval.

---

### `memory_entries` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Entry identifier |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project (memories are project-scoped) |
| `task_id` | UUID | FK → tasks.id ON DELETE SET NULL, nullable | Source task |
| `entry_timestamp` | TIMESTAMPTZ | NOT NULL | Time the lesson was recorded (used in MEMORY.md) |
| `summary` | TEXT | NOT NULL | One-line summary of what was implemented |
| `files_affected` | TEXT[] | NOT NULL, default `{}` | Files changed in the related task |
| `lessons_learned` | TEXT | NOT NULL | Specific lessons for Agent to act on |
| `created_at` | TIMESTAMPTZ | NOT NULL | DB insert time |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Updated by PO edits |

**MEMORY.md generation**: `memory_service.export_memory_file(project_id)` queries all entries
ordered by `entry_timestamp ASC` and renders them to the MEMORY.md format defined in `plan.md`.
The file is written to `{sandbox_root}/{project_id}/MEMORY.md` and read by `context_builder.py`.

---

### `codebase_maps` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Map identifier |
| `project_id` | UUID | FK → projects.id ON DELETE CASCADE | Owning project |
| `task_id` | UUID | FK → tasks.id ON DELETE SET NULL, nullable | Task that triggered this scan |
| `map_json` | JSONB | NOT NULL | Full codebase map (schema defined in `plan.md`) |
| `language` | VARCHAR(20) | NOT NULL | `python` \| `javascript` \| `typescript` |
| `file_count` | INTEGER | NOT NULL, default 0 | Number of files scanned |
| `generated_at` | TIMESTAMPTZ | NOT NULL | Scan timestamp |

**Freshness**: `codebase_mapper.py` always generates a new map at the start of each task. The
`GET /codebase-map` endpoint returns the latest row for the project. There is no TTL-based
invalidation — stale maps are overwritten by the next task's scan.

---

### `task_branches` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | — |
| `task_id` | UUID | UNIQUE FK → tasks.id ON DELETE CASCADE | One branch per task |
| `branch_name` | VARCHAR(255) | NOT NULL | e.g., `task/3f4a1b2c` |
| `status` | VARCHAR(10) | NOT NULL, default `active`, CHECK IN (`active`,`merged`,`conflict`) | Branch lifecycle |
| `created_at` | TIMESTAMPTZ | NOT NULL | When the branch was created |
| `merged_at` | TIMESTAMPTZ | nullable | When the squash merge completed |

**Branch naming**: `task/{task_id[:8]}` (first 8 chars of UUID, lowercase).

---

### `inline_comments` [Phase 2]

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK | Comment identifier |
| `task_id` | UUID | FK → tasks.id ON DELETE CASCADE | Owning task |
| `diff_id` | UUID | FK → diffs.id ON DELETE SET NULL, nullable | Which diff the comment applies to |
| `file_path` | VARCHAR(1000) | NOT NULL | e.g., `src/models/user.py` |
| `line_number` | INTEGER | NOT NULL | Line number within the unified diff (not absolute file line) |
| `comment_text` | TEXT | NOT NULL | PO's comment |
| `created_at` | TIMESTAMPTZ | NOT NULL | — |

**Feedback format sent to Agent**: When PO submits Reject, the API collects all
`inline_comments` for the current `diff_id` and passes them as:
```json
{
  "text_feedback": "General comment from PO",
  "inline_comments": [
    { "file_path": "src/x.py", "line_number": 42, "comment_text": "This needs error handling" }
  ]
}
```

---

## Alembic Migration Files

### `001_initial_schema.py` (Phase 1)

Creates: `projects`, `documents`, `tasks`, `agent_runs`, `diffs`, `feedbacks`, `audit_logs`.
Also creates the `EXCLUDE` constraint and the `NO UPDATE / NO DELETE` rules on `audit_logs`.

### `002_phase2_schema.py` (Phase 2)

Adds: `stream_events`, `agent_pause_states`, `memory_entries`, `codebase_maps`,
`task_branches`, `inline_comments`.
Also adds `original_content` and `modified_content` columns to `diffs`.

---

## Index Strategy

```sql
-- Phase 1 indexes
CREATE INDEX idx_documents_project_type ON documents (project_id, type);
CREATE INDEX idx_tasks_project_status   ON tasks (project_id, status);
CREATE INDEX idx_agent_runs_task        ON agent_runs (task_id);
CREATE INDEX idx_audit_logs_project     ON audit_logs (project_id, timestamp DESC);
CREATE INDEX idx_audit_logs_task        ON audit_logs (task_id, timestamp DESC);

-- Phase 2 indexes
CREATE INDEX idx_stream_events_task_seq ON stream_events (task_id, sequence_number);
CREATE INDEX idx_memory_entries_project ON memory_entries (project_id, entry_timestamp);
CREATE INDEX idx_codebase_maps_project  ON codebase_maps (project_id, generated_at DESC);
```

---

## Enum Reference

| Table | Column | Valid Values |
|-------|--------|-------------|
| `projects` | `status` | `active`, `archived` |
| `documents` | `type` | `SPEC`, `PLAN` |
| `documents` | `status` | `draft`, `approved`, `revision_requested` |
| `tasks` | `status` | `todo`, `in_progress`, `review`, `done`, `rejected`, `conflict` |
| `agent_runs` | `agent_type` | `architect`, `coder`, `reviewer` |
| `agent_runs` | `status` | `running`, `success`, `failure`, `awaiting_hil`, `paused` |
| `diffs` | `review_status` | `pending`, `approved`, `rejected` |
| `feedbacks` | `reference_type` | `document`, `task` |
| `audit_logs` | `result` | `success`, `failure`, `awaiting_hil` |
| `stream_events` | `event_type` | `THOUGHT`, `TOOL_CALL`, `TOOL_RESULT`, `ACTION`, `ERROR`, `STATUS_CHANGE` |
| `agent_pause_states` | `state` | `running`, `paused` |
| `task_branches` | `status` | `active`, `merged`, `conflict` |
