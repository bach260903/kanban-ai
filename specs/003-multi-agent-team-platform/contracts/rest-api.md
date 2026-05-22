# REST API Contracts: Platform Expansion — Feature 003

**Base**: `/api/v1` | **Auth**: Bearer JWT (trừ auth endpoints)
**Date**: 2026-05-20

---

## F-004: Auth & Multi-user

### POST /auth/register
```json
Request:  { "email": "str", "password": "str", "display_name": "str" }
Response: { "access_token": "str", "token_type": "bearer", "user": { "id", "email", "display_name" } }
Errors:   409 email already registered
```

### POST /auth/login
```json
Request:  { "email": "str", "password": "str" }
Response: { "access_token": "str", "token_type": "bearer", "expires_in": 604800 }
Errors:   401 invalid credentials
```

### GET /auth/me
```json
Response: { "id": "uuid", "email": "str", "display_name": "str", "created_at": "iso8601" }
```

### GET /projects/{id}/members
```json
Response: [
  { "user_id": "uuid", "display_name": "str", "email": "str", "role": "owner|leader|developer|viewer", "joined_at": "iso8601" }
]
```

### POST /projects/{id}/members/invite
```json
Request:  { "role": "leader|developer|viewer", "invitee_email": "str|null" }
Response: { "invitation_id": "uuid", "invite_url": "str", "expires_at": "iso8601" }
Errors:   403 only owner can invite
```

### GET /invitations/{token}
```json
Response: { "project_name": "str", "role": "str", "inviter_name": "str", "expires_at": "iso8601" }
Errors:   404 not found | 410 expired
```

### POST /invitations/{token}/accept
```json
Response: { "project_id": "uuid", "role": "str" }
Errors:   410 expired | 409 already member
```

### PATCH /projects/{id}/members/{user_id}
```json
Request:  { "role": "leader|developer|viewer" }
Response: { "user_id": "uuid", "role": "str" }
Errors:   403 only owner/leader can change roles
```

### DELETE /projects/{id}/members/{user_id}
```json
Response: 204 No Content
Errors:   403 cannot remove owner | 400 cannot remove yourself if last owner
```

---

## F-003: Reviewer Agent

### GET /tasks/{id}/review
```json
Response: {
  "id": "uuid",
  "task_id": "uuid",
  "status": "pending|running|complete|error",
  "score": 0-100,
  "suggestion": "approve|needs_changes",
  "test_runner": "pytest|npm_test|none",
  "test_pass": 0,
  "test_fail": 0,
  "comments": [
    { "id": "uuid", "file_path": "str", "line_number": 42, "content": "str", "severity": "info|warning|error" }
  ],
  "error_message": "str|null",
  "created_at": "iso8601",
  "completed_at": "iso8601|null"
}
Errors: 404 no review for this task yet
```

---

## F-005: Task Dependencies

### GET /projects/{id}/tasks/{task_id}/dependencies
```json
Response: {
  "task_id": "uuid",
  "depends_on": [{ "task_id": "uuid", "title": "str", "status": "str" }],
  "blocked_by": [{ "task_id": "uuid", "title": "str", "status": "str" }]
}
```

### POST /projects/{id}/tasks/{task_id}/dependencies
```json
Request:  { "depends_on_task_id": "uuid" }
Response: { "task_id": "uuid", "depends_on_task_id": "uuid", "created_at": "iso8601" }
Errors:   409 circular dependency detected | 404 task not found | 400 same project required
```

### DELETE /projects/{id}/tasks/{task_id}/dependencies/{dep_task_id}
```json
Response: 204 No Content
```

### GET /projects/{id}/dependency-graph
```json
Response: {
  "nodes": [{ "id": "uuid", "title": "str", "status": "str" }],
  "edges": [{ "from": "uuid", "to": "uuid" }]
}
```

## F-005: Task Templates

### GET /templates?scope=project|global&project_id={id}
```json
Response: [{ "id": "uuid", "name": "str", "title_template": "str", "description_template": "str", "scope": "str" }]
```

### POST /templates
```json
Request:  { "name": "str", "title_template": "str", "description_template": "str", "scope": "project|global", "project_id": "uuid|null" }
Response: { "id": "uuid", "name": "str", ... }
Errors:   409 name conflict in project scope
```

### DELETE /templates/{id}
```json
Response: 204 No Content
Errors:   403 only creator or owner/leader
```

---

## F-005: Task Assignment

### PATCH /tasks/{id}/assign
```json
Request:  { "user_id": "uuid|null" }
Response: { "task_id": "uuid", "assigned_to": { "user_id": "uuid", "display_name": "str" } | null }
Errors:   403 developer cannot assign | 404 user not member
```

---

## F-006: Dashboard & Analytics

### GET /dashboard
```json
Response: {
  "projects": [
    {
      "id": "uuid", "name": "str", "coding_backend": "str",
      "task_counts": { "todo": 0, "in_progress": 0, "review": 0, "done": 0 },
      "stale_review_tasks": [{ "task_id": "uuid", "title": "str", "in_review_since": "iso8601" }],
      "members_count": 5
    }
  ]
}
```

### GET /projects/{id}/analytics?range=7d|30d|custom&from=&to=
```json
Response: {
  "period": { "from": "iso8601", "to": "iso8601" },
  "by_backend": [
    { "backend": "groq|claude_code|openai|gemini", "avg_seconds": 0, "first_approve_rate": 0.82, "error_count": 0 }
  ],
  "by_member": [
    { "user_id": "uuid", "display_name": "str", "tasks_done": 0, "tasks_in_progress": 0, "avg_retry": 0 }
  ],
  "reviewer_avg_score": 78.5,
  "error_breakdown": { "CLI_TIMEOUT": 2, "CLI_NOT_FOUND": 0, "CLI_AUTH_ERROR": 1 }
}
```

---

## F-007: Notifications

### GET /notifications?unread_only=true&limit=20&offset=0
```json
Response: {
  "total_unread": 5,
  "items": [
    { "id": "uuid", "type": "str", "content": "str", "reference_type": "task", "reference_id": "uuid", "is_read": false, "created_at": "iso8601" }
  ]
}
```

### PATCH /notifications/{id}/read
```json
Response: 204 No Content
```

### POST /notifications/read-all
```json
Response: { "marked_count": 5 }
```

## F-007: Webhooks

### GET /projects/{id}/webhooks
```json
Response: [{ "id": "uuid", "url": "str", "events": ["task.review","task.done"], "enabled": true }]
```

### POST /projects/{id}/webhooks
```json
Request:  { "url": "str", "secret": "str|null", "events": ["task.review","task.done","agent.error"] }
Response: { "id": "uuid", "url": "str", "events": [...], "enabled": true }
Errors:   403 only owner/leader | 400 invalid event type
```

### DELETE /projects/{id}/webhooks/{webhook_id}
```json
Response: 204 No Content
```

### POST /projects/{id}/webhooks/{webhook_id}/test
```json
Response: { "delivered": true, "http_status": 200, "response_time_ms": 145 }
Errors:   500 delivery failed with details
```

## F-007: GitHub Integration

### GET /projects/{id}/github
```json
Response: { "repo_full_name": "str", "default_base_branch": "str", "enabled": true } | 404 not configured
```

### PUT /projects/{id}/github
```json
Request:  { "repo_full_name": "owner/repo", "pat": "ghp_...", "default_base_branch": "main" }
Response: { "repo_full_name": "str", "default_base_branch": "str", "enabled": true }
Errors:   422 invalid PAT or repo not found
```

---

## Webhook Payload Schema (outbound)

```json
{
  "event": "task.needs_review | task.done | agent.error",
  "timestamp": "iso8601",
  "project": { "id": "uuid", "name": "str" },
  "task": { "id": "uuid", "title": "str" },
  "actor": { "type": "agent|user", "id": "uuid|null", "name": "str" },
  "meta": {}
}
```

HMAC-SHA256 signature trong header `X-NeoKanban-Signature: sha256=<hex>` nếu secret được cấu hình.
