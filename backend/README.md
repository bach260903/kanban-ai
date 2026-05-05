# Backend

Python **3.11+** (3.14 OK). Load `.env` from **repo root** (`d:\kanban\.env`).

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- Docs: `http://localhost:8000/docs`
- Health: `GET /health`

## API (v0.2)

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/register` | no |
| POST | `/api/auth/login` | no |
| GET | `/api/boards` | Bearer |
| POST | `/api/boards` | Bearer |
| GET/PATCH/DELETE | `/api/boards/{id}` | Bearer |
| POST/PATCH/DELETE | `/api/boards/{id}/columns/...` | Bearer |
| POST/PATCH/DELETE | `/api/boards/{id}/tasks/...` | Bearer |

SQLite file: `backend/dev.db` (created on startup).

**Password hashing** uses `bcrypt` (not `passlib`) for compatibility with Python 3.14 + bcrypt 4.x.
