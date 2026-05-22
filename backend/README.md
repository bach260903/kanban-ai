# Backend

Python **3.11+**. Load `.env` từ **repo root** (`kanban-ai/.env`).

## Khởi động (development)

```powershell
cd backend
# Dùng venv trong repo root (đã tạo sẵn)
.\..\venv\Scripts\activate   # hoặc .\..\..\.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

- Swagger UI: `http://localhost:8000/docs`
- Health: `GET /health`

## Database migration

Trước khi chạy lần đầu, chạy migration để tạo schema:

```powershell
cd backend
& "..\\.venv\Scripts\alembic.exe" upgrade head
```

### Migrations hiện có

| File | Nội dung |
|------|---------|
| `001_initial_schema` | projects, documents, tasks, agent_runs, diffs, feedbacks, audit_logs, intents |
| `002_phase2_schema` | stream_events, agent_pause_states, memory_entries, codebase_maps, task_branches, inline_comments |
| `003_add_users` | Bảng `users` (email, hashed_password, display_name) — dùng cho auth |

## API (v1)

Base URL: `http://localhost:8000/api/v1`

**Không cần auth:**

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/auth/register` | Tạo tài khoản mới |
| POST | `/auth/login` | Đăng nhập → JWT token |

**Cần Bearer token:**

| Method | Path | Mô tả |
|--------|------|-------|
| GET/POST | `/projects` | Danh sách / tạo project |
| GET/PUT/DELETE | `/projects/{id}` | Chi tiết / cập nhật / archive |
| GET/PUT | `/projects/{id}/constitution` | Đọc / lưu constitution |
| GET/POST | `/projects/{id}/documents` | Documents (SPEC/PLAN) |
| POST | `/projects/{id}/generate-spec` | Kích hoạt agent sinh SPEC |
| POST | `/projects/{id}/generate-plan` | Kích hoạt agent sinh PLAN |
| GET/POST/DELETE | `/projects/{id}/tasks/...` | Kanban tasks |
| GET | `/agent-runs/{run_id}` | Poll trạng thái agent |
| GET/PUT/DELETE | `/projects/{id}/memory/...` | Memory entries |

Xem chi tiết tại [docs/api.md](../docs/api.md).

## Cấu hình môi trường (`.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| `DATABASE_URL` | ✅ | PostgreSQL asyncpg URL |
| `REDIS_URL` | ✅ | Redis URL |
| `JWT_SECRET` | ✅ | Secret key ký JWT (HS256) |
| `JWT_EXPIRE_MINUTES` | ❌ | Thời gian hết hạn token (mặc định 10080 = 7 ngày) |
| `GROQ_API_KEY` | ✅ | API key Groq LLM |
| `GROQ_MODEL` | ❌ | Model ID (mặc định `llama-3.3-70b-versatile`) |
| `SANDBOX_ROOT` | ✅ | Thư mục sandbox cho agent |

**Password hashing** dùng `bcrypt` (tương thích Python 3.14 + bcrypt 4.x).

## CORS

Backend cho phép các origin sau (development):
- `http://localhost:5173` (Vite default)
- `http://localhost:3000`
- `http://127.0.0.1:5173`
- `http://127.0.0.1:3000`
