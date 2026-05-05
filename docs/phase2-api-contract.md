# Phase 2.3 — API Contract

> Hợp đồng giữa **frontend** ↔ **backend** ↔ **agent harness**. Backend = FastAPI, OpenAPI sinh tự động tại `/openapi.json` & UI tại `/docs`.

---

## A. Quy ước chung

- Base URL dev: `http://localhost:8000/api`.
- Auth: `Authorization: Bearer <jwt>`. JWT phát hành ở `POST /api/auth/login`.
- Lỗi: trả `{"detail": "..."}` (FastAPI default) + status code.
- Tất cả id dùng **UUID v4** (string trên dây).
- Datetime ISO-8601 UTC (ví dụ `2026-05-03T12:34:56Z`).

---

## B. REST endpoints — đã có (Phase 1)

> Định nghĩa runtime, đã chạy. Dùng OpenAPI làm spec gốc; bảng dưới chỉ liệt kê để dễ đối chiếu.

| Method | Path | Body / Query | Response | Phase 1 |
|--------|------|---------------|-----------|---------|
| POST | `/auth/register` | `UserCreate` | `UserOut` | ✅ |
| POST | `/auth/login` | `LoginRequest` | `TokenResponse` | ✅ |
| GET | `/boards` |  | `List[BoardOut]` | ✅ |
| POST | `/boards` | `BoardCreate` | `BoardDetailOut` (kèm 3 cột mặc định) | ✅ |
| GET | `/boards/{id}` |  | `BoardDetailOut` | ✅ |
| PATCH | `/boards/{id}` | `BoardUpdate` | `BoardOut` | ✅ |
| DELETE | `/boards/{id}` |  | 204 | ✅ |
| POST | `/boards/{id}/columns` | `ColumnCreate` | `ColumnOut` | ✅ |
| PATCH | `/boards/{id}/columns/{column_id}` | `ColumnUpdate` | `ColumnOut` | ✅ |
| DELETE | `/boards/{id}/columns/{column_id}` |  | 204 | ✅ |
| POST | `/boards/{id}/tasks` | `TaskCreate` | `TaskOut` | ✅ |
| PATCH | `/boards/{id}/tasks/{task_id}` | `TaskUpdate` | `TaskOut` | ✅ |
| DELETE | `/boards/{id}/tasks/{task_id}` |  | 204 | ✅ |

---

## C. REST endpoints — sẽ thêm Phase 3

### C.1 Comments & Skills

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/boards/{id}/tasks/{task_id}/comments` | — | `List[CommentOut]` |
| POST | `/boards/{id}/tasks/{task_id}/comments` | `{body}` | `CommentOut` |
| GET | `/skills` | — | `List[SkillOut]` |
| POST | `/skills` | `{name}` | `SkillOut` |
| GET | `/users/{id}/skills` | — | `List[UserSkillOut]` |
| PUT | `/users/{id}/skills` | `List[{skill_id, level}]` | `List[UserSkillOut]` |
| GET | `/users/{id}/workload?board_id=` | — | `WorkloadOut` |

### C.2 Activity log

| Method | Path | Query | Response |
|--------|------|-------|----------|
| GET | `/boards/{id}/activity` | `since=ISO`, `until=ISO`, `limit=100` | `List[ActivityLogOut]` |

### C.3 AI / Agent

| Method | Path | Body | Response |
|--------|------|------|----------|
| POST | `/agent/chat` | `AgentChatRequest` | `AgentRunOut` (id để theo dõi qua WS) |
| POST | `/agent/breakdown` | `{board_id, goal_text, target_column_id?}` | `AgentRunOut` (intent đã pin = `plan`) |
| POST | `/agent/suggest-assignee` | `{board_id, task_id}` | `AgentRunOut` (intent = `assign`) |
| POST | `/agent/monitor` | `{board_id}` | `AgentRunOut` (intent = `monitor`) |
| POST | `/agent/report` | `{board_id, since, until}` | `AgentRunOut` (intent = `report`) |
| GET | `/agent/runs/{run_id}` | — | `AgentRunDetailOut` (kèm steps) |
| GET | `/boards/{id}/agent/runs?limit=20` | — | `List[AgentRunOut]` |

#### `AgentChatRequest`

```jsonc
{
  "board_id": "uuid",
  "message": "Hãy tách task 'Triển khai login' thành subtasks",
  "thread_id": "optional-uuid",       // null => server tạo mới
  "intent_hint": null,                  // optional gợi ý router
  "context": { "task_id": "uuid?" }     // optional
}
```

#### `AgentRunOut`

```jsonc
{
  "run_id": "uuid",
  "thread_id": "uuid",
  "status": "queued | running | done | error",
  "intent": "plan | assign | monitor | report | execute | end",
  "ws_topic": "agent.run.{run_id}",
  "started_at": "ISO"
}
```

#### `AgentRunDetailOut` thêm

```jsonc
{
  "...": "AgentRunOut fields",
  "finished_at": "ISO?",
  "latency_ms": 4321,
  "tokens_in": 1234, "tokens_out": 456, "cost_usd": 0.0021,
  "result": {
    "plan":   [/* TaskDraft[] */],
    "assignments": [/* AssignmentDecision[] */],
    "alerts": [/* AlertItem[] */],
    "report_md": "string?"
  },
  "steps": [
    {
      "step_index": 0,
      "node": "orchestrator",
      "input_summary": "...",
      "output_summary": "intent=plan",
      "latency_ms": 412
    }
  ]
}
```

> **Quan trọng:** REST chỉ trả `AgentRunOut` ngay lập tức (status=`queued`). Frontend subscribe WebSocket bằng `ws_topic` để xem trace + kết quả.

---

## D. WebSocket — streaming agent

### D.1 Endpoint

`ws://localhost:8000/ws/agent?token=<jwt>`

> JWT đặt ở query (vì WS không cho header dễ dàng từ browser). Hoặc dùng `Sec-WebSocket-Protocol`.

### D.2 Frame format

Mọi frame là JSON `{"type": "...", "data": {...}}`.

#### Client → Server

| `type` | `data` | Ý nghĩa |
|--------|--------|---------|
| `subscribe` | `{topics: ["agent.run.{run_id}", "board.{board_id}"]}` | Lắng nghe |
| `unsubscribe` | `{topics: [...]}` |  |
| `ping` | `{}` | Keep-alive (server trả `pong`) |

#### Server → Client

| `type` | `data` | Khi nào |
|--------|--------|---------|
| `run.started` | `{run_id, intent, started_at}` | Orchestrator nhận message |
| `run.step` | `{run_id, step_index, node, status: "started" \| "finished", input_summary?, output_summary?, latency_ms?}` | Mỗi node bắt đầu/kết thúc |
| `run.token` | `{run_id, node, token}` | (Tuỳ chọn) stream token theo `astream_events` cho Reporter |
| `run.tool` | `{run_id, node, tool, args, result, latency_ms}` | Khi worker gọi tool |
| `run.finished` | `{run_id, status, latency_ms, tokens_in, tokens_out, cost_usd, result}` | Hoàn tất |
| `run.error` | `{run_id, error, recoverable}` | Lỗi |
| `board.changed` | `{board_id, kind: "task.update" \| "task.create" \| ..., entity}` | Khi mutating tool áp DB → WS push, FE invalidate React Query |
| `pong` | `{}` |  |

### D.3 Backpressure & retry

- Frontend phải giới hạn buffer 1000 event; quá thì drop event `run.token`, giữ `run.step`/`run.finished`.
- Server buffer per-connection 5MB; vượt → drop oldest.
- Reconnect: client gửi lại `subscribe`; nếu run đã `done`, server replay event cuối (lookup `agent_runs` + `agent_run_steps`).

---

## E. Validation & error model

| Code | Khi nào | Body |
|------|---------|------|
| 400 | Body sai pydantic | `{detail: [{loc, msg, type}]}` |
| 401 | JWT thiếu/hết hạn | `{detail: "Not authenticated"}` |
| 403 | Không phải owner board | `{detail: "Forbidden"}` |
| 404 | Resource không tồn tại | `{detail: "<X> not found"}` |
| 409 | Vi phạm WIP-limit (Monitor enforce) | `{detail: "WIP limit exceeded for column ..."}` |
| 422 | Tool agent gọi với args không hợp lệ | `{detail: ..., tool: "..."}` |
| 500 | Lỗi không xử lý | `{detail: "Internal server error", trace_id: "..."}` |

---

## F. OpenAPI artifact

- Source of truth: `app.openapi()` của FastAPI. Lưu snapshot vào `docs/openapi.snapshot.json` mỗi lần thêm endpoint (script trong Phase 3).
- Frontend sinh client SDK bằng `openapi-typescript` từ snapshot này — đảm bảo type-safe & versioned.

---

## G. Definition of Done — Phase 2.3

- [x] Liệt kê đầy đủ endpoint hiện tại + endpoint Phase 3.
- [x] Định nghĩa schema cho AI endpoints.
- [x] Định nghĩa frame WebSocket.
- [ ] Snapshot OpenAPI sau Phase 3.1 (`docs/openapi.snapshot.json`).
