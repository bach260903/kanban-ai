# REST API Contract: AI CLI Integration (Feature 002)

**Base**: Extends existing `/api/v1` contract from `001-neo-kanban`  
**Date**: 2026-05-18  
**Changes**: Modified endpoints marked with ✏️ — new fields only, no breaking changes

---

## Modified Endpoints

### ✏️ `POST /api/v1/projects` — Create Project

Added optional field `coding_backend` to request body.

**Request body** (new field added):
```json
{
  "name": "My Project",
  "description": "...",
  "primary_language": "python",
  "coding_backend": "claude_code"
}
```

| Field | Type | Required | Default | Values |
|---|---|---|---|---|
| `coding_backend` | string | No | `"groq"` | `groq` \| `claude_code` \| `openai` \| `gemini` |

**Response 201** — same as before, with `coding_backend` included:
```json
{
  "id": "uuid",
  "name": "My Project",
  "coding_backend": "claude_code",
  ...
}
```

---

### ✏️ `PUT /api/v1/projects/{id}` — Update Project

Added optional field `coding_backend` to update payload.

**Request body**:
```json
{
  "coding_backend": "openai"
}
```

**Validation**: `400` if `coding_backend` is not one of the allowed values.  
**Effect**: Next Coder Agent run for this project uses the new backend.

---

### ✏️ `GET /api/v1/projects/{id}` — Get Project

**Response** now includes `coding_backend`:
```json
{
  "id": "uuid",
  "name": "string",
  "coding_backend": "groq | claude_code | openai | gemini",
  ...
}
```

---

### ✏️ `GET /api/v1/projects` — List Projects

Each project item now includes `coding_backend` field.

---

## New Endpoint

### `GET /api/v1/backends/available`

Returns which backends are configured (API key present) on this server.  
**Auth**: JWT required.

**Response 200**:
```json
{
  "available": ["groq", "claude_code"],
  "unavailable": [
    {"backend": "openai", "reason": "OPENAI_API_KEY not set"},
    {"backend": "gemini", "reason": "GOOGLE_AI_API_KEY not set"}
  ]
}
```

This endpoint is used by the frontend Backend Selector to show/disable unavailable options.

---

## Unchanged Endpoints

All other endpoints (`/documents`, `/tasks`, `/agent-runs`, `/ws/tasks/{id}/stream`, etc.) remain unchanged. The `coding_backend` is internal to the server-side Coder Agent dispatch — clients only set it at the project level.

---

## Error Codes (new)

| Code | Condition |
|------|-----------|
| `CLI_NOT_FOUND` | CLI binary not found in PATH or configured path |
| `CLI_AUTH_ERROR` | API key not set or authentication failed |
| `CLI_TIMEOUT` | CLI process exceeded 10-minute limit |

These codes appear in the `error` field of `agent_run` records and in WebSocket `ERROR` events:

```json
{
  "type": "ERROR",
  "content": {
    "code": "CLI_AUTH_ERROR",
    "message": "ANTHROPIC_API_KEY is not set. Configure it in .env to use Claude Code backend.",
    "backend": "claude_code"
  }
}
```
