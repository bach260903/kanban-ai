# Hướng dẫn test đủ Giai đoạn 1 (Phase 1)

Làm lần lượt từ trên xuống. **Repo gốc:** `d:\kanban`. **Biến môi trường:** `GROQ_API_KEY` trong file **`d:\kanban\.env`**.

---

## 0. Chuẩn bị chung

```powershell
cd d:\kanban
python --version
# Groq (đọc từ .env, không in key):
python evaluation\scripts\verify_groq.py
```

**Kỳ vọng:** dòng `OK: Groq response: ...`  
Nếu `FAIL: GROQ_API_KEY missing` → tạo `.env` ở gốc repo, thêm `GROQ_API_KEY=gsk_...`

**Tùy chọn — nạp `.env` vào PowerShell** (`demo_*.py` và `llm_latency_smoke.py` đã tự load `d:\kanban\.env` qua `evaluation/load_repo_env.py`):

```powershell
Get-Content d:\kanban\.env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
    $k = $matches[1].Trim(); $v = $matches[2].Trim().Trim('"')
    Set-Item -Path "env:$k" -Value $v
  }
}
```

---

## 1.1 Benchmark Multi-Agent (CrewAI / AutoGen / LangGraph)

### A) LangGraph + AutoGen — Python 3.11+ (kể cả 3.14)

```powershell
cd d:\kanban\evaluation\agent_frameworks
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
# Đảm bảo GROQ_API_KEY đã set (mục 0)
python demo_langgraph.py
python demo_autogen.py
```

**Kỳ vọng:** in ra plan/answer hoặc stream hội thoại; tổng số `3+5+7+11 = 26` xuất hiện trong output.

### B) CrewAI — cần Python 3.12 hoặc 3.13

```powershell
cd d:\kanban\evaluation\agent_frameworks
py -3.12 -m venv .venv-crewai
.\.venv-crewai\Scripts\activate
python -m pip install -r requirements-crewai.txt
python demo_crewai.py
```

Nếu không có `py -3.12`: cài Python 3.12 hoặc ghi chép trong báo cáo *“CrewAI không chạy trên 3.14, đã benchmark LangGraph + AutoGen”*.

### C) So sánh (ghi vào báo cáo)

Đọc và bổ sung cảm nhận thực tế vào: `docs/phase1-technology-decisions.md` (bảng control flow / debug / community / domain).

---

## 1.2 Chiến lược LLM — smoke latency

```powershell
cd d:\kanban\evaluation\scripts
python -m pip install langchain-groq langchain-openai
# GROQ_API_KEY đã set
python llm_latency_smoke.py
```

**Kỳ vọng:** dòng `groq_llama-3.3-70b: ...s | ...`  
Có `OPENAI_API_KEY` + billing → thêm dòng `openai_gpt-4o-mini`.  
Claude/Gemini: cần key + package (xem comment trong script).

Ghi **P50/P95** đầy đủ là việc Giai đoạn 5; Phase 1 chỉ cần **chạy được + có số latency mẫu**.

---

## 1.3 Database — kiểm tra thiết kế (không cần chạy SQL)

- Mở `docs/erd-phase1.md` — đối chiếu với `backend/app/models.py` (đã implement gần đủ ERD).
- Đọc phần SQLite / Chroma trong `docs/phase1-technology-decisions.md`.

**Kỳ vọng:** hiểu được lựa chọn stack và ERD; không bắt buộc migration Alembic trong Phase 1 nếu đang dùng `create_all` ở backend.

---

## 1.4 Stack — Backend (FastAPI)

```powershell
cd d:\kanban\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Trình duyệt: **http://localhost:8000/docs**

**Checklist Swagger / thủ công:**

1. `POST /api/auth/register` — body JSON: `email`, `password` (≥8 ký tự), `display_name`
2. `POST /api/auth/login` — lấy `access_token`
3. Authorize (Bearer) token
4. `POST /api/boards` — `title`; kiểm tra response có **3 columns** mặc định
5. `GET /api/boards` và `GET /api/boards/{id}`
6. `POST /api/boards/{id}/tasks` — `column_id` lấy từ board detail, `title`
7. `PATCH /api/boards/{id}/tasks/{task_id}` — đổi `column_id` (kéo sang cột khác)

**Kỳ vọng:** 201/200, không 500; sau bước 1 nếu lỗi bcrypt → `python -m pip install -U bcrypt` và dùng code mới (`app/security.py` dùng `bcrypt` trực tiếp).

---

## 1.4 Stack — Frontend (Next.js 14 + shadcn + deps)

Terminal khác:

```powershell
cd d:\kanban\frontend
copy .env.example .env.local
npm install
npm run dev
```

**Kỳ vọng:** http://localhost:3000 mở được.

```powershell
npm run build
```

**Kỳ vọng:** `Compiled successfully` (đã xử lý font/Tailwind trước đó).

*UI board + gọi API:* có thể để **Giai đoạn 4**; Phase 1 chỉ cần chứng minh **build + dev chạy**.

---

## 1.5 Đọc tài liệu nền (Phase 0.2 — tự đánh dấu)

- Paper ReAct, AutoGen; LangGraph ≥3 ví dụ; RAG Naive / Advanced / Agentic.

Không có lệnh test tự động; đánh dấu checklist trong nhật ký đồ án.

---

## Tổng kết Phase 1 “đạt” khi

| Hạng mục | Tiêu chí tối thiểu |
|----------|---------------------|
| 1.1 | `demo_langgraph` + `demo_autogen` chạy; CrewAI chạy hoặc có lý do + venv 3.12 |
| 1.2 | `verify_groq.py` OK; `llm_latency_smoke.py` có ít nhất Groq |
| 1.3 | Đã đọc ERD + doc quyết định DB |
| 1.4 | Backend `/docs` full flow auth + board + task; `npm run build` frontend OK |
| 0.2 | Tự xác nhận đã đọc paper/tutorial RAG |

Chi tiết lỗi Python 3.14 + CrewAI: `evaluation/agent_frameworks/README.md`.
