# Kanban AI

Nền tảng quản lý công việc Kanban tích hợp AI đa tác tử — lập kế hoạch, phân rã task, giám sát tiến độ và sinh code tự động.

## Stack

| Lớp | Công nghệ |
|---|---|
| Frontend | React 18 + TypeScript + Vite, Zustand, dnd-kit, Monaco Editor |
| Backend | FastAPI (Python 3.11), SQLAlchemy async, Alembic |
| Database | PostgreSQL 16 |
| Cache / Pub-Sub | Redis 7 |
| AI | LangChain + LangGraph; Groq (llama-3.3-70b) + Google Gemini, tự động failover khi một nhà cung cấp hết quota |
| Realtime | WebSocket |
| CI/CD | Pipeline test → lint → build → preview_deploy với AI self-healing, tích hợp GitHub |

## Yêu cầu

- Docker & Docker Compose
- Node.js 18+
- Python 3.11
- [Groq API key](https://console.groq.com/keys) và/hoặc [Google AI Studio key](https://aistudio.google.com/apikey) — nên có cả hai để bật auto-failover

## Cài đặt

### 1. Clone và tạo file môi trường

```powershell
git clone <repo-url>
cd kanban-ai
copy .env.example .env
```

Mở `.env` và điền các giá trị bắt buộc:

```env
POSTGRES_PASSWORD=your_secure_password
JWT_SECRET=replace_with_a_long_random_string

# LLM — đặt ít nhất một nhà cung cấp; có cả hai để bật auto-failover
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...
GOOGLE_MODEL=gemini-2.5-flash
LLM_AUTO_FAILOVER=true

# Chọn nhà cung cấp cho từng agent (google | groq)
ARCHITECT_LLM_PROVIDER=groq   # SPEC / PLAN / task breakdown
CODER_LLM_PROVIDER=groq       # Coder agent
REVIEW_LLM_PROVIDER=groq      # Reviewer agent
```

> Khi một nhà cung cấp hết quota (429), hệ thống tự chuyển sang nhà cung cấp còn lại
> cho request đó nếu `LLM_AUTO_FAILOVER=true` và cả hai key đều được cấu hình.

### 2. Khởi động backend bằng Docker (khuyến nghị)

Lệnh này dựng cả PostgreSQL, Redis và Backend:

```powershell
docker compose up -d --build
```

> **Vì sao chạy backend trong Docker?** Coder agent và pipeline CI/CD thực thi
> `git`, `node`/`npm`, `ruff`, `pytest`, `python` ngay trong môi trường backend.
> Container Linux đã có sẵn các công cụ này; chạy backend trực tiếp trên Windows
> thường thiếu chúng và sẽ làm hỏng phần CI/CD + sinh code. Mã backend được
> bind-mount nên vẫn **hot-reload** khi bạn sửa file.

Đợi healthy (khoảng 10–15 giây), kiểm tra:

```powershell
docker compose ps
```

Chạy migration database (lần đầu, hoặc sau khi có migration mới):

```powershell
docker compose exec backend alembic upgrade head
```

- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 3. Chạy Frontend

Mở terminal mới:

```powershell
cd frontend
```

Tạo file biến môi trường:

```powershell
copy .env.example .env.local
```

Cài dependencies (bao gồm Tailwind CSS v3):

```powershell
npm install
npm install -D tailwindcss@^3 autoprefixer tw-animate-css
```

Khởi động dev server:

```powershell
npm run dev
```

Mở trình duyệt: http://localhost:5173

## Tài liệu API

Xem đầy đủ tại [docs/api.md](docs/api.md), bao gồm:
- REST endpoints (Projects, Documents, Tasks, Audit Logs)
- Agent triggers (generate-spec, generate-plan)
- WebSocket Thought Stream protocol (Phase 2)
- Pause & Steer, Memory, Codebase Map (Phase 2)

Swagger UI tương tác: http://localhost:8000/docs (khi backend đang chạy)

---

## Chạy backend ngoài Docker (tùy chọn — chỉ dev API nhẹ)

Chỉ nên dùng khi bạn **không** đụng tới coder agent / CI-CD, vì các bước
test/lint/build cần `git`, `node`/`npm`, `ruff`, `pytest` cài sẵn trên máy.

```powershell
# Chỉ chạy hạ tầng trong Docker
docker compose up -d postgres redis

cd backend
python -m venv .venv          # hoặc: uv venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # hoặc: uv pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

> ⚠️ Khi chạy kiểu này, đặt `SANDBOX_ROOT` trong `.env` về một đường dẫn local hợp lệ
> (vd `./sandbox`), khác với `/sandbox` mà container dùng.

## Cấu trúc thư mục

```
kanban-ai/
├── backend/
│   ├── app/
│   │   ├── agent/          # LangGraph multi-agent nodes
│   │   ├── api/v1/         # REST endpoints
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── websocket/      # WebSocket handler
│   │   └── main.py
│   ├── alembic/            # Database migrations
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/     # atoms / molecules / organisms
│       ├── hooks/
│       ├── pages/
│       ├── services/       # API clients
│       └── store/          # Zustand stores
├── specs/                  # Feature specs & design docs
├── docker-compose.yml
└── .env.example
```

## Biến môi trường quan trọng

| Biến | Mô tả | Mặc định |
|---|---|---|
| `POSTGRES_USER` | PostgreSQL user | `neo_kanban` |
| `POSTGRES_PASSWORD` | PostgreSQL password | *(bắt buộc đặt)* |
| `POSTGRES_DB` | Tên database | `neo_kanban` |
| `DATABASE_URL` | SQLAlchemy connection string | xem `.env.example` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET` | Secret ký JWT | *(bắt buộc đặt)* |
| `GROQ_API_KEY` | Groq API key | *(đặt ít nhất 1 provider)* |
| `GROQ_MODEL` | Model Groq sử dụng | `llama-3.3-70b-versatile` |
| `GOOGLE_API_KEY` | Google AI Studio key (Gemini) | *(tùy chọn — cần cho failover)* |
| `GOOGLE_MODEL` | Model Gemini sử dụng | `gemini-2.5-flash` |
| `LLM_AUTO_FAILOVER` | Tự chuyển provider khi gặp 429 | `true` |
| `ARCHITECT_LLM_PROVIDER` | Provider cho SPEC/PLAN/breakdown | `groq` |
| `CODER_LLM_PROVIDER` | Provider cho Coder agent | `groq` |
| `REVIEW_LLM_PROVIDER` | Provider cho Reviewer agent | `groq` |
| `SANDBOX_ROOT` | Thư mục sandbox của agent | `/sandbox` (Docker) |

## Chạy test

Trong Docker (khớp với môi trường chạy thật):

```powershell
docker compose exec backend pytest
```

Hoặc local (nếu đã tạo venv ở phần tùy chọn trên):

```powershell
cd backend
.\.venv\Scripts\activate
pytest
```

## Lưu ý

- Không commit `.env` hoặc bất kỳ file chứa secret
- Không commit thư mục `.venv/`, `__pycache__/`, `node_modules/`
- Trước khi push, chạy `npm run build` và `pytest` để đảm bảo không bị lỗi
