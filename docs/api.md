# Neo-Kanban — Tài liệu API

**Base URL**: `http://localhost:8000`  
**Prefix**: `/api/v1`  
**Content-Type**: `application/json`

---

## Xác thực (Authentication)

Tất cả endpoint (trừ `/health`) yêu cầu JWT trong header:

```
Authorization: Bearer <jwt_token>
```

WebSocket không hỗ trợ custom header trên trình duyệt — truyền token qua query param:

```
ws://localhost:8000/ws/tasks/{task_id}/stream?token=<jwt_token>
```

---

## Authentication

### `POST /api/v1/auth/register`

Tạo tài khoản mới. Không cần JWT.

**Request body**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "display_name": "Nguyen Van A"
}
```

| Field | Bắt buộc | Ràng buộc |
|-------|----------|-----------|
| `email` | ✅ | Email hợp lệ, tối đa 320 ký tự, phải unique |
| `password` | ✅ | Tối thiểu 8 ký tự |
| `display_name` | ✅ | Tối đa 200 ký tự |

**Response 201**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Nguyen Van A",
  "created_at": "2026-05-17T10:00:00Z"
}
```

**Response 400** — email đã được đăng ký
```json
{ "detail": "Email already registered" }
```

---

### `POST /api/v1/auth/login`

Đăng nhập và lấy JWT token. Không cần JWT.

**Request body**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response 200**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Response 401** — sai email hoặc password
```json
{ "detail": "Invalid email or password" }
```

> **Lưu ý:** Token hết hạn sau 7 ngày (mặc định). Lưu token vào `localStorage` với key `neo_kanban_jwt` để frontend tự động attach vào mọi request.

---

## Mã lỗi chung

| Code | Ý nghĩa |
|------|---------|
| `200` | Thành công, có body |
| `201` | Tạo tài nguyên thành công |
| `202` | Accepted — agent đã được kích hoạt (trả về `agent_run_id`) |
| `204` | Thành công, không có body |
| `400` | Dữ liệu đầu vào không hợp lệ |
| `401` | Thiếu hoặc sai JWT |
| `404` | Không tìm thấy tài nguyên |
| `409` | Conflict — vượt WIP limit, tên project trùng |
| `422` | Lỗi validate schema (Pydantic) |
| `500` | Lỗi server |

---

## Health

### `GET /health`

Kiểm tra trạng thái service. Không cần auth.

**Response 200**
```json
{ "status": "ok" }
```

---

## Projects

### `GET /api/v1/projects`

Lấy danh sách tất cả project.

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

Tạo project mới.

**Request body**
```json
{
  "name": "My App",
  "description": "Optional description",
  "primary_language": "python"
}
```

| Field | Bắt buộc | Ràng buộc |
|-------|----------|-----------|
| `name` | ✅ | 1–255 ký tự, phải unique |
| `primary_language` | ✅ | `python` \| `javascript` \| `typescript` |
| `description` | ❌ | — |

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

**Response 409** — tên project đã tồn tại
```json
{ "detail": "Project name 'My App' already exists." }
```

---

### `GET /api/v1/projects/{project_id}`

Lấy chi tiết một project.

**Response 200** — schema giống POST 201

**Response 404**
```json
{ "detail": "Project not found." }
```

---

### `PUT /api/v1/projects/{project_id}`

Cập nhật metadata project (không dùng cho constitution — xem endpoint riêng).

**Request body** (tất cả optional)
```json
{
  "name": "Updated Name",
  "description": "Updated description"
}
```

**Response 200** — project schema đã cập nhật

---

### `DELETE /api/v1/projects/{project_id}`

Archive project (`status = archived`). Không xóa dữ liệu.

**Response 204**

---

### `GET /api/v1/projects/{project_id}/constitution`

Lấy nội dung constitution.

**Response 200**
```json
{
  "project_id": "uuid",
  "content": "# My Constitution\n\n..."
}
```

---

### `PUT /api/v1/projects/{project_id}/constitution`

Lưu nội dung constitution.

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

Lấy danh sách document. Filter theo type nếu cần.

**Query params**: `?type=SPEC` hoặc `?type=PLAN`

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

Lấy document kèm nội dung đầy đủ.

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

Chỉnh sửa thủ công nội dung document. Không thay đổi `status` hay tăng `version`.

**Request body**
```json
{
  "content": "# Updated Spec\n\n..."
}
```

**Response 200** — document schema đã cập nhật

---

### `POST /api/v1/projects/{project_id}/documents/{doc_id}/approve`

PO phê duyệt document (HIL checkpoint).

- SPEC approve → mở khóa `generate-plan`
- PLAN approve → tự động kích hoạt `TASK_BREAKDOWN`

**Request body**: `{}`

**Response 200**
```json
{
  "id": "uuid",
  "status": "approved",
  "updated_at": "..."
}
```

**Response 400** — document không ở trạng thái `draft` hoặc `revision_requested`
```json
{ "detail": "Document must be in draft or revision_requested state to approve." }
```

---

### `POST /api/v1/projects/{project_id}/documents/{doc_id}/revise`

PO yêu cầu chỉnh sửa lại document kèm phản hồi.

**Request body**
```json
{
  "feedback": "Please add more detail about error handling in section 3."
}
```

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

`agent_run_id` dùng để frontend poll tiến trình.

---

## Agent Triggers

### `POST /api/v1/projects/{project_id}/generate-spec`

Kích hoạt Architect Agent sinh SPEC.md từ Intent.

**Request body**
```json
{
  "intent": "Build a user authentication system with JWT and refresh tokens."
}
```

| Field | Ràng buộc |
|-------|-----------|
| `intent` | Bắt buộc, 10–5000 ký tự |

**Response 202**
```json
{
  "agent_run_id": "uuid",
  "intent_id": "uuid",
  "document_id": "uuid",
  "status": "running",
  "message": "SPEC generation started."
}
```

**Response 400** — SPEC đã được approve
```json
{
  "detail": "An approved SPEC already exists. Generating a new SPEC will replace it. Confirm with ?force=true."
}
```

---

### `POST /api/v1/projects/{project_id}/generate-plan`

Kích hoạt Architect Agent sinh PLAN.md.

**Điều kiện**: SPEC phải có `status = approved`.

**Request body**: `{}`

**Response 202**
```json
{
  "agent_run_id": "uuid",
  "status": "running",
  "message": "PLAN generation started."
}
```

**Response 400**
```json
{ "detail": "SPEC must be approved before generating PLAN." }
```

---

### `GET /api/v1/agent-runs/{run_id}`

Poll trạng thái một agent run.

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

**Các giá trị `status`**: `running` | `awaiting_hil` | `success` | `failure`

---

## Tasks (Kanban Board)

### `GET /api/v1/projects/{project_id}/tasks`

Lấy tất cả task của project, phân nhóm theo cột Kanban.

**Response 200**
```json
{
  "todo": [
    { "id": "uuid", "title": "...", "description": "...", "priority": 0 }
  ],
  "in_progress": [],
  "review": [],
  "done": [],
  "rejected": [],
  "conflict": []
}
```

---

### `GET /api/v1/projects/{project_id}/tasks/{task_id}`

Lấy chi tiết một task.

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

Di chuyển task sang cột Kanban mới.

**Request body**
```json
{
  "to": "in_progress"
}
```

| Chuyển từ | Chuyển đến | Ai thực hiện |
|-----------|-----------|--------------|
| `todo` | `in_progress` | PO (kéo thẻ) |
| `in_progress` | `review` | Hệ thống (agent xong) |
| `review` | `done` | Hệ thống (sau approve) |
| `review` | `in_progress` | Hệ thống (sau reject) |

> Di chuyển sang `in_progress` áp dụng WIP = 1 và tự động kích hoạt Coder Agent.

**Response 200**
```json
{
  "task_id": "uuid",
  "from_status": "todo",
  "to_status": "in_progress",
  "agent_run_id": "uuid"
}
```

**Response 409** — vượt WIP limit
```json
{ "detail": "WIP limit reached: one task is already In Progress. Complete it before starting another." }
```

---

### `GET /api/v1/projects/{project_id}/tasks/{task_id}/diff`

Lấy diff mới nhất của task (chỉ có khi task ở trạng thái `review`).

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

**Response 404**
```json
{ "detail": "No diff available. Agent may still be running." }
```

---

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/approve`

PO phê duyệt code diff. Task → Done.

**Request body**: `{}`

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

PO từ chối code diff kèm phản hồi. Task → In Progress (Agent thử lại).

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

Lấy audit log phân trang (bất biến — không thể xóa/sửa).

**Query params**

| Param | Mặc định | Mô tả |
|-------|---------|-------|
| `page` | `1` | Trang hiện tại |
| `page_size` | `50` | Số bản ghi mỗi trang |
| `task_id` | — | Filter theo task |

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

## Phase 2 — Pause & Steer

> Đường dẫn chính để pause/resume là qua WebSocket message. Các REST endpoint này phục vụ test automation và client không dùng WebSocket.

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/pause`

Yêu cầu agent dừng sau bước hiện tại.

**Request body**: `{}`

**Response 200**
```json
{
  "task_id": "uuid",
  "state": "paused",
  "paused_at": "2026-05-11T10:31:00Z"
}
```

**Response 400** — task không đang `in_progress`
```json
{ "detail": "Task is not currently in_progress." }
```

---

### `POST /api/v1/projects/{project_id}/tasks/{task_id}/resume`

Resume agent đang bị pause, kèm hướng dẫn điều chỉnh nếu cần.

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

### `GET /api/v1/projects/{project_id}/tasks/{task_id}/pause-state`

Lấy trạng thái pause hiện tại.

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

## Phase 2 — Memory

### `GET /api/v1/projects/{project_id}/memory`

Lấy tất cả memory entries của project, sắp xếp theo `entry_timestamp` tăng dần.

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

### `PUT /api/v1/projects/{project_id}/memory/{entry_id}`

PO cập nhật một memory entry.

**Request body** (tất cả optional)
```json
{
  "summary": "Updated summary",
  "lessons_learned": "Updated lessons"
}
```

**Response 200** — entry schema đã cập nhật

---

### `DELETE /api/v1/projects/{project_id}/memory/{entry_id}`

Xóa một memory entry. Không ảnh hưởng đến context đã build trước đó.

**Response 204**

---

## Phase 2 — Codebase Map

### `GET /api/v1/projects/{project_id}/codebase-map`

Lấy codebase map mới nhất. Nếu chưa có, tự động quét đồng bộ (≤ 10 giây cho 500 files).

**Response 200** — codebase map JSON

**Response 400** — ngôn ngữ không được hỗ trợ
```json
{ "detail": "Codebase mapping only supports python, javascript, and typescript." }
```

---

## Phase 2 — Git Branch & Inline Comments

### `GET /api/v1/tasks/{task_id}/branch`

Lấy trạng thái branch của task.

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

### `GET /api/v1/tasks/{task_id}/comments`

Lấy tất cả inline comment cho diff hiện tại của task.

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

### `POST /api/v1/tasks/{task_id}/comments`

Thêm inline comment trên một dòng của diff.

**Request body**
```json
{
  "file_path": "src/auth.py",
  "line_number": 42,
  "comment_text": "This needs error handling for the None case."
}
```

**Validation**: `file_path` phải nằm trong `diffs.files_affected`; `line_number` ≥ 1.

**Response 201** — comment schema vừa tạo

---

### `DELETE /api/v1/tasks/{task_id}/comments/{comment_id}`

Xóa một inline comment.

**Response 204**

---

## WebSocket — Thought Stream

**Endpoint**: `ws://localhost:8000/ws/tasks/{task_id}/stream?token=<jwt_token>`

### Vòng đời kết nối

```
Client                          Server
  │──── WS connect ────────────►│  xác thực JWT, kiểm tra task status = in_progress
  │◄─── CONNECTED ──────────────│
  │
  │  [tùy chọn] gửi CATCH_UP nếu bị ngắt kết nối trước đó
  │──── CATCH_UP ───────────────►│  replay events bị miss
  │◄─── event stream ───────────│
  │
  │──── PAUSE ──────────────────►│  agent dừng sau bước hiện tại
  │◄─── STATUS_CHANGE (PAUSED) ─│
  │
  │──── RESUME ─────────────────►│  agent tiếp tục
  │◄─── event stream ───────────│
  │◄─── STREAM_END ─────────────│  agent hoàn thành
  │──── WS close ───────────────►│
```

---

### Server → Client: Stream Events

Tất cả stream event dùng cùng envelope:

```json
{
  "event_type": "THOUGHT | TOOL_CALL | TOOL_RESULT | ACTION | ERROR | STATUS_CHANGE",
  "sequence_number": 1,
  "timestamp": "2026-05-11T10:30:00.123Z",
  "task_id": "uuid",
  "agent_run_id": "uuid",
  "content": {}
}
```

#### `THOUGHT` — suy luận nội bộ của agent

```json
{
  "event_type": "THOUGHT",
  "content": {
    "reasoning": "I need to check whether the user model already has a verify_password method."
  }
}
```

#### `TOOL_CALL` — agent sắp gọi tool (trước khi chạy)

```json
{
  "event_type": "TOOL_CALL",
  "content": {
    "tool_name": "read_file",
    "call_id": "tc-001",
    "arguments": { "path": "src/models/user.py" }
  }
}
```

#### `TOOL_RESULT` — kết quả tool (sau khi chạy xong)

```json
{
  "event_type": "TOOL_RESULT",
  "content": {
    "tool_name": "read_file",
    "call_id": "tc-001",
    "success": true,
    "result": "class User:\n    ...",
    "result_truncated": false
  }
}
```

#### `ACTION` — hành động có side effect (ghi file, git, sandbox)

```json
{
  "event_type": "ACTION",
  "content": {
    "action_type": "write_file",
    "description": "Writing updated user model with verify_password method",
    "target": "src/models/user.py",
    "audit_log_id": "uuid"
  }
}
```

#### `ERROR` — lỗi trong quá trình chạy

```json
{
  "event_type": "ERROR",
  "content": {
    "error_type": "SandboxEscapeError",
    "message": "Attempted path traversal: ../../etc/passwd",
    "recoverable": false,
    "step": "CODING"
  }
}
```

#### `STATUS_CHANGE` — LangGraph chuyển node

```json
{
  "event_type": "STATUS_CHANGE",
  "content": {
    "from": "CODING",
    "to": "REVIEWING",
    "reason": "Agent completed implementation; diff stored."
  }
}
```

---

### Server → Client: Control Messages (không lưu DB)

#### `CONNECTED`
```json
{
  "type": "CONNECTED",
  "task_id": "uuid",
  "agent_run_id": "uuid",
  "latest_sequence": 41
}
```

#### `STREAM_END`
```json
{
  "type": "STREAM_END",
  "task_id": "uuid",
  "final_status": "success",
  "event_count": {
    "THOUGHT": 12, "TOOL_CALL": 8, "TOOL_RESULT": 8,
    "ACTION": 3, "ERROR": 0, "STATUS_CHANGE": 2
  }
}
```

#### `ERROR` (connection-level)
```json
{
  "type": "ERROR",
  "code": "UNAUTHORIZED | TASK_NOT_ACTIVE | TASK_NOT_FOUND",
  "message": "Invalid or expired JWT token."
}
```

---

### Client → Server Messages

#### `CATCH_UP` — replay events bị miss sau khi reconnect
```json
{ "type": "CATCH_UP", "last_sequence": 41 }
```

#### `PAUSE` — yêu cầu dừng
```json
{ "type": "PAUSE", "timestamp": "2026-05-11T10:31:00Z" }
```

#### `RESUME` — tiếp tục kèm hướng dẫn
```json
{
  "type": "RESUME",
  "steering_instructions": "Focus on writing unit tests for the new function.",
  "timestamp": "2026-05-11T10:35:00Z"
}
```

---

### Reconnect (TypeScript)

```typescript
function connectWithReconnect(taskId: string, lastSequence: number) {
  const ws = new WebSocket(
    `ws://localhost:8000/ws/tasks/${taskId}/stream?token=${jwt}`
  );

  ws.onopen = () => {
    if (lastSequence > 0) {
      ws.send(JSON.stringify({ type: "CATCH_UP", last_sequence: lastSequence }));
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.sequence_number !== undefined) {
      lastSequence = msg.sequence_number;
    }
    // dispatch to UI...
  };

  ws.onclose = (event) => {
    if (!event.wasClean && agentStillRunning) {
      setTimeout(() => connectWithReconnect(taskId, lastSequence), 1000);
    }
  };
}
```

---

### Redis Channels

| Channel | Mô tả |
|---------|-------|
| `task:{task_id}:events` | Live event stream cho task |
| `pause:{task_id}` | Pause flag (tồn tại = paused; xóa = resumed) |
