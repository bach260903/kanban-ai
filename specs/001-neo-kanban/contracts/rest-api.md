# REST API Contract: Neo-Kanban

**Base URL**: `http://localhost:8000`
**API version prefix**: `/api/v1`
**Auth**: All endpoints (except `/health`) require `Authorization: Bearer <jwt_token>` header.
**Content-Type**: `application/json` for all request/response bodies.
**Date**: 2026-05-11

---

## Common Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success with body |
| 201 | Resource created |
| 202 | Accepted — background job started (returns `agent_run_id`) |
| 204 | Success, no body |
| 400 | Bad request / validation error |
| 401 | Missing or invalid JWT |
| 404 | Resource not found |
| 409 | Conflict — e.g., WIP limit exceeded, duplicate project name |
| 422 | Unprocessable entity — schema validation failure |
| 500 | Server error |

---

## Health

### `GET /health`

Returns service liveness. No auth required.

**Response 200**
```json
{ "status": "ok" }
```

---

## Projects

### `GET /api/v1/projects`

List all projects.

**Response 200**
```json
[
  {
    "id": "uuid",
    "name": "My App",
    "description": "Short description",
    "primary_language": "python",
    "status": "active",
    "updated_at": "2026-05-11T10:00:00Z"
  }
]
```

---

### `POST /api/v1/projects`

Create a project.

**Request body**
```json
{
  "name": "My App",
  "description": "Optional description",
  "primary_language": "python"
}
```

**Validation**:
- `name`: required, 1–255 chars, must be unique
- `primary_language`: required, one of `python`, `javascript`, `typescript`

**Response 201**
```json
{
  "id": "uuid",
  "name": "My App",
  "description": "Optional description",
  "primary_language": "python",
  "constitution": "",
  "status": "active",
  "created_at": "2026-05-11T10:00:00Z",
  "updated_at": "2026-05-11T10:00:00Z"
}
```

**Response 409** — duplicate name
```json
{ "detail": "Project name 'My App' already exists." }
```

---

### `GET /api/v1/projects/{project_id}`

Get full project detail.

**Response 200** — full project schema (same as POST 201 response)

**Response 404**
```json
{ "detail": "Project not found." }
```

---

### `PUT /api/v1/projects/{project_id}`

Update project metadata (not constitution — use constitution endpoint).

**Request body** (all fields optional)
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

**Response 200** — updated project schema

---

### `DELETE /api/v1/projects/{project_id}`

Archive project (sets `status = archived`). Does not delete rows.

**Response 204**

---

### `GET /api/v1/projects/{project_id}/constitution`

Get constitution content.

**Response 200**
```json
{
  "project_id": "uuid",
  "content": "# My Constitution\n\n..."
}
```

---

### `PUT /api/v1/projects/{project_id}/constitution`

Save constitution content.

**Request body**
```json
{
  "content": "# My Constitution\n\n..."
}
```

**Response 200**
```json
{
  "project_id": "uuid",
  "content": "# My Constitution\n\n...",
  "updated_at": "2026-05-11T10:05:00Z"
}
```

---

## Documents (SPEC / PLAN)

### `GET /api/v1/projects/{project_id}/documents`

List documents. Optionally filter by type.

**Query params**: `?type=SPEC` or `?type=PLAN`

**Response 200**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "type": "SPEC",
    "status": "draft",
    "version": 1,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### `GET /api/v1/projects/{project_id}/documents/{doc_id}`

Get document with full content.

**Response 200**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "type": "SPEC",
  "content": "# Feature Spec\n\n...",
  "status": "draft",
  "version": 1,
  "created_at": "...",
  "updated_at": "..."
}
```

---

### `PUT /api/v1/projects/{project_id}/documents/{doc_id}`

Manual edit of document content. Does **not** change `status` or increment `version`.

**Request body**
```json
{
  "content": "# Updated Spec\n\n..."
}
```

**Response 200** — updated document schema

---

### `POST /api/v1/projects/{project_id}/documents/{doc_id}/approve`

PO approves the document (HIL checkpoint).

- `SPEC` approve → unlocks `generate-plan`
- `PLAN` approve → triggers `TASK_BREAKDOWN` automatically

**Request body**: empty `{}`

**Response 200**
```json
{
  "id": "uuid",
  "status": "approved",
  "updated_at": "..."
}
```

**Response 400** — if document is not in `draft` or `revision_requested` state
```json
{ "detail": "Document must be in draft or revision_requested state to approve." }
```

---

### `POST /api/v1/projects/{project_id}/documents/{doc_id}/revise`

PO requests revision with feedback.

**Request body**
```json
{
  "feedback": "Please add more detail about error handling in section 3."
}
```

**Validation**: `feedback` required, non-empty.

**Response 200**
```json
{
  "id": "uuid",
  "status": "revision_requested",
  "feedback_id": "uuid",
  "agent_run_id": "uuid",
  "updated_at": "..."
}
```

The response includes `agent_run_id` so the frontend can poll for progress.

---

## Agent Triggers

### `POST /api/v1/projects/{project_id}/generate-spec`

Trigger Architect Agent to generate SPEC.md from Intent.

**Request body**
```json
{
  "intent": "Build a user authentication system with JWT and refresh tokens."
}
```

**Validation**: `intent` required, 10–5000 chars.

**Response 202**
```json
{
  "agent_run_id": "uuid",
  "status": "running",
  "message": "SPEC generation started."
}
```

**Response 400** — if a SPEC already exists and is approved
```json
{
  "detail": "An approved SPEC already exists. Generating a new SPEC will replace it. Confirm with ?force=true."
}
```

---

### `POST /api/v1/projects/{project_id}/generate-plan`

Trigger Architect Agent to generate PLAN.md.

**Precondition**: Project's SPEC document must have `status = approved`.

**Request body**: empty `{}`

**Response 202**
```json
{
  "agent_run_id": "uuid",
  "status": "running",
  "message": "PLAN generation started."
}
```

**Response 400** — if SPEC is not approved
```json
{ "detail": "SPEC must be approved before generating PLAN." }
```

---

### `GET /api/v1/agent-runs/{run_id}`

Poll agent run status.

**Response 200**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "task_id": "uuid or null",
  "agent_type": "architect",
  "status": "awaiting_hil",
  "input_artifacts": ["projects/uuid/constitution.md"],
  "output_artifacts": ["documents/uuid"],
  "started_at": "...",
  "completed_at": null,
  "result": null
}
```

---

## Tasks (Kanban)

### `GET /api/v1/projects/{project_id}/tasks`

List all tasks for project, grouped by status.

**Response 200**
```json
{
  "todo": [ { "id": "uuid", "title": "...", "description": "...", "priority": 0 } ],
  "in_progress": [],
  "review": [],
  "done": [],
  "rejected": [],
  "conflict": []
}
```

---

### `GET /api/v1/projects/{project_id}/tasks/{task_id}`

Get single task detail.

**Response 200**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "title": "Implement user login endpoint",
  "description": "Create POST /auth/login that validates credentials and returns JWT",
  "status": "in_progress",
  "priority": 1,
  "created_at": "...",
  "updated_at": "..."
}
```

---

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/move`

Move task to a new Kanban column.

**Request body**
```json
{
  "to": "in_progress"
}
```

**Valid `to` values**: `in_progress` (from `todo`), `review` (system only), `done` (system only)

**Notes**:
- PO may only move `todo → in_progress`. Other forward transitions are system-controlled.
- Moving to `in_progress` enforces WIP = 1 and triggers Coder Agent.

**Response 200**
```json
{
  "task_id": "uuid",
  "from_status": "todo",
  "to_status": "in_progress",
  "agent_run_id": "uuid"
}
```

**Response 409** — WIP limit exceeded
```json
{ "detail": "WIP limit reached: one task is already In Progress. Complete it before starting another." }
```

---

### `GET /api/v1/projects/{project_id}/tasks/{task_id}/diff`

Get the latest diff for a task (available when task is in `review` status).

**Response 200**
```json
{
  "id": "uuid",
  "task_id": "uuid",
  "original_content": "def login():\n    pass\n",
  "modified_content": "def login(credentials: LoginRequest) -> TokenResponse:\n    ...\n",
  "content": "--- a/src/auth.py\n+++ b/src/auth.py\n...",
  "files_affected": ["src/auth.py"],
  "review_status": "pending",
  "created_at": "..."
}
```

**Response 404** — no diff available yet
```json
{ "detail": "No diff available. Agent may still be running." }
```

---

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/approve`

PO approves code diff. Task → Done.

**Request body**: empty `{}`

**Response 200**
```json
{
  "task_id": "uuid",
  "status": "done",
  "diff_id": "uuid",
  "updated_at": "..."
}
```

---

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/reject`

PO rejects code diff with feedback. Task → In Progress (Agent retries).

**Request body**
```json
{
  "feedback": "The error handling is incomplete. Handle the case where the user does not exist."
}
```

**Response 200**
```json
{
  "task_id": "uuid",
  "status": "in_progress",
  "feedback_id": "uuid",
  "agent_run_id": "uuid",
  "updated_at": "..."
}
```

---

## Audit Logs

### `GET /api/v1/projects/{project_id}/audit-logs`

Paginated immutable audit log.

**Query params**: `?page=1&page_size=50&task_id=<uuid>` (all optional)

**Response 200**
```json
{
  "total": 142,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": "uuid",
      "agent_id": "coder-v1",
      "agent_version": "1.0.0",
      "action_type": "write_file",
      "action_description": "Writing implementation to src/auth.py",
      "timestamp": "2026-05-11T10:30:00Z",
      "input_refs": ["tasks/uuid"],
      "output_refs": ["src/auth.py"],
      "result": "success",
      "project_id": "uuid",
      "task_id": "uuid"
    }
  ]
}
```

---

## Phase 2 Endpoints

### Pause & Steer

#### `POST /api/v1/tasks/{task_id}/pause`

Signal agent to pause after its current step.

**Request body**: empty `{}`

**Response 200**
```json
{
  "task_id": "uuid",
  "state": "paused",
  "paused_at": "2026-05-11T10:31:00Z"
}
```

**Response 400** — task not in `in_progress` state
```json
{ "detail": "Task is not currently in_progress." }
```

---

#### `POST /api/v1/tasks/{task_id}/resume`

Resume paused agent with optional steering instructions.

**Request body**
```json
{
  "steering_instructions": "Focus on adding proper error handling for the database calls."
}
```

**Response 200**
```json
{
  "task_id": "uuid",
  "state": "running",
  "resumed_at": "2026-05-11T10:35:00Z"
}
```

---

#### `GET /api/v1/tasks/{task_id}/pause-state`

Get current pause state.

**Response 200**
```json
{
  "task_id": "uuid",
  "state": "paused",
  "steering_instructions": null,
  "paused_at": "2026-05-11T10:31:00Z",
  "resumed_at": null
}
```

---

### Memory Management

#### `GET /api/v1/projects/{project_id}/memory`

List all memory entries for project, ordered by `entry_timestamp` ascending.

**Response 200**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "task_id": "uuid",
    "entry_timestamp": "2026-05-11T10:00:00Z",
    "summary": "Implemented JWT login endpoint",
    "files_affected": ["src/auth.py", "src/models/user.py"],
    "lessons_learned": "Use python-jose for JWT; always validate expiry before returning token.",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

#### `PUT /api/v1/projects/{project_id}/memory/{entry_id}`

PO updates a memory entry.

**Request body** (all fields optional)
```json
{
  "summary": "Updated summary",
  "lessons_learned": "Updated lessons"
}
```

**Response 200** — updated entry schema

---

#### `DELETE /api/v1/projects/{project_id}/memory/{entry_id}`

Delete a memory entry. Immediately excluded from next agent context build.

**Response 204**

---

### Codebase Map

#### `GET /api/v1/projects/{project_id}/codebase-map`

Get the latest codebase map. If none exists, triggers a fresh scan synchronously (≤ 10 s for 500 files).

**Response 200** — codebase map JSON (schema defined in `plan.md` Codebase Map section)

**Response 400** — project `primary_language` is not `python`, `javascript`, or `typescript`
```json
{ "detail": "Codebase mapping only supports python, javascript, and typescript." }
```

---

### Git Branch + Inline Comments

#### `GET /api/v1/tasks/{task_id}/branch`

Get branch status.

**Response 200**
```json
{
  "task_id": "uuid",
  "branch_name": "task/3f4a1b2c",
  "status": "active",
  "created_at": "...",
  "merged_at": null
}
```

---

#### `GET /api/v1/tasks/{task_id}/comments`

List all inline comments for the task's current diff.

**Response 200**
```json
[
  {
    "id": "uuid",
    "task_id": "uuid",
    "diff_id": "uuid",
    "file_path": "src/auth.py",
    "line_number": 42,
    "comment_text": "This needs error handling for the None case.",
    "created_at": "..."
  }
]
```

---

#### `POST /api/v1/tasks/{task_id}/comments`

Add an inline comment on a diff line.

**Request body**
```json
{
  "file_path": "src/auth.py",
  "line_number": 42,
  "comment_text": "This needs error handling for the None case."
}
```

**Validation**: `file_path` must be in `diffs.files_affected`; `line_number` ≥ 1.

**Response 201** — created comment schema

---

#### `DELETE /api/v1/tasks/{task_id}/comments/{comment_id}`

Remove an inline comment.

**Response 204**
