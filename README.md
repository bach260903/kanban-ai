# Kanban AI

Nền tảng quản lý công việc Kanban tích hợp AI đa tác tử — lập kế hoạch, phân rã task, giám sát tiến độ và sinh code tự động.

## Stack

| Lớp | Công nghệ |
|---|---|
| Frontend | React 18 + TypeScript + Vite, Zustand, dnd-kit, Monaco Editor |
| Backend | FastAPI (Python 3.11), SQLAlchemy async, Alembic |
| Database | PostgreSQL 16 |
| Cache / Pub-Sub | Redis 7 |
| AI | LangChain + LangGraph + Groq (llama-3.3-70b-versatile) |
| Realtime | WebSocket |

## Yêu cầu

- Docker & Docker Compose
- Node.js 18+
- Python 3.11
- [Groq API key](https://console.groq.com/keys)

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
GROQ_API_KEY=gsk_...
```

### 2. Khởi động PostgreSQL và Redis qua Docker

```powershell
docker compose up -d postgres redis
```

Đợi healthy (khoảng 10–15 giây), kiểm tra:

```powershell
docker compose ps
```

### 3. Chạy Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Chạy migration database:

```powershell
alembic upgrade head
```

Khởi động API server:

```powershell
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 4. Chạy Frontend

Mở terminal mới:

```powershell
cd frontend
npm install
npm run dev
```

Mở trình duyệt: http://localhost:5173

## Chạy toàn bộ bằng Docker (tùy chọn)

```powershell
docker compose up --build
```

Backend sẽ chạy trên cổng 8000. Frontend vẫn cần chạy riêng bằng `npm run dev`.

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
| `GROQ_API_KEY` | Groq API key | *(bắt buộc đặt)* |
| `GROQ_MODEL` | Model Groq sử dụng | `llama-3.3-70b-versatile` |

## Chạy test

```powershell
cd backend
.\.venv\Scripts\activate
pytest
```

## Lưu ý

- Không commit `.env` hoặc bất kỳ file chứa secret
- Không commit thư mục `.venv/`, `__pycache__/`, `node_modules/`
- Trước khi push, chạy `npm run build` và `pytest` để đảm bảo không bị lỗi
