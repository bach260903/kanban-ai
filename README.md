# Kanban AI Multi-Agent

Monorepo hệ thống quản lý công việc Kanban tích hợp AI đa tác tử.

- `backend`: FastAPI + SQLAlchemy + LangGraph
- `frontend`: Next.js 14 + Tailwind + shadcn + dnd-kit
- `agents`: logic tác tử theo vai trò
- `evaluation`: bộ dữ liệu và script đánh giá
- `docs`: tài liệu thiết kế, checklist kiểm thử

## Tính năng chính

Hệ thống AI hoạt động theo mô hình phân cấp trên board Kanban:

- **Orchestrator**: phân loại ý định câu lệnh người dùng và điều phối worker phù hợp.
- **Planner**: phân rã mục tiêu thành subtask có ước lượng thời gian và kỹ năng.
- **Assigner**: gợi ý người phù hợp dựa trên kỹ năng, tải công việc và dữ liệu lịch sử.
- **Monitor**: phát hiện tắc nghẽn (WIP cao, quá hạn, task treo lâu) bằng luật + LLM.
- **Reporter**: tạo báo cáo markdown (stand-up, tổng kết nhanh).
- **Executor**: thực thi thao tác trên board bằng tool-calling (tạo task, chuyển cột, gán người).

Mỗi lần chạy AI được lưu vào `agent_runs` và `agent_run_steps`, đồng thời stream realtime qua WebSocket để hiển thị trace suy luận trên frontend.

## Yêu cầu môi trường

- Windows + PowerShell (khuyến nghị theo setup hiện tại của dự án)
- Python `3.14` (backend/eval chung) và Python `3.12` (benchmark CrewAI)
- Node.js 18+ và npm
- Biến môi trường `GROQ_API_KEY`

## Thiết lập lần đầu

```powershell
cd d:\kanban
copy .env.example .env
```

Mở file `.env` và điền:

```env
GROQ_API_KEY=gsk_...
```

## Chạy Backend

```powershell
cd d:\kanban\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- Swagger: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- WebSocket agent: `ws://localhost:8000/ws/agent?token=<JWT>`

## Chạy Frontend

```powershell
cd d:\kanban\frontend
copy .env.example .env.local
npm install
npm run dev
```

Truy cập: <http://localhost:3000>

## Luồng sử dụng nhanh

1. Đăng ký tại `/register`, đăng nhập và tạo board.
2. Tạo một số task mẫu, thêm estimate/tags/due date.
3. Cập nhật kỹ năng người dùng ở `/profile`.
4. Tại trang board, dùng các chức năng AI:
   - **Breakdown**: phân rã mục tiêu thành nhiều task.
   - **AI Assistant**: chat hỏi đáp/ra lệnh, xem trace chạy agent trực tiếp.
   - **Monitor**: quét điểm nghẽn của board.
   - **Report**: xuất tóm tắt tình hình dưới dạng markdown.
   - **Suggest Assignee**: gợi ý người phù hợp cho task.

## Kiểm thử và đánh giá

### 1) Kiểm tra Groq key

```powershell
cd d:\kanban
python evaluation\scripts\verify_groq.py
```

Kỳ vọng: in ra `OK: Groq response: ...`

### 2) Benchmark framework agent

#### LangGraph + AutoGen (Python 3.14)

```powershell
cd d:\kanban\evaluation\agent_frameworks
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python demo_langgraph.py
.\.venv\Scripts\python demo_autogen.py
```

#### CrewAI (Python 3.12)

```powershell
cd d:\kanban\evaluation\agent_frameworks
py -3.12 -m venv .venv-crewai
.\.venv-crewai\Scripts\python -m pip install -r requirements-crewai.txt
.\.venv-crewai\Scripts\python -m pip install litellm
.\.venv-crewai\Scripts\python demo_crewai.py
```

### 3) Latency smoke test

```powershell
cd d:\kanban\evaluation\scripts
python llm_latency_smoke.py
```

### 4) Chạy eval planner end-to-end

Yêu cầu backend đang chạy.

```powershell
cd d:\kanban\evaluation\scripts
python seed_fixtures.py --api http://127.0.0.1:8000
python run_eval.py planner --api http://127.0.0.1:8000
python aggregate_eval.py
```

Kết quả nằm trong `evaluation/results/<timestamp>/report.md`.

## Cấu trúc thư mục

```text
backend/
  app/
    routers/      auth, boards, comments, skills, users, activity, agent, ws
    services/     llm.py, vectorstore.py, tool_handlers.py, agent_runner.py, ws_manager.py
    models.py
    schemas.py

agents/
  src/agents/     orchestrator, planner, assigner, monitor, reporter, executor
  src/tools/      registry tool
  src/graph.py

frontend/
  src/app/        trang login, register, boards, profile
  src/components/ board UI + AI UI
  src/lib/        api, auth, websocket, query, type

evaluation/
  datasets/       dữ liệu test planner/assigner/monitor/reporter/executor
  judge/          rubric cho LLM-as-judge
  scripts/        seed_fixtures.py, run_eval.py, aggregate_eval.py

docs/
  tài liệu phase 1/2 và checklist test
```

## Tài liệu tham khảo trong dự án

- `docs/phase1-full-test.md`: checklist test đầy đủ Phase 1
- `docs/phase2-full-test.md`: checklist test Phase 2
- `docs/phase1-technology-decisions.md`: quyết định công nghệ
- `docs/phase2-agent-architecture.md`: kiến trúc multi-agent
- `docs/phase2-api-contract.md`: hợp đồng API/WS
- `docs/phase2-evaluation-framework.md`: framework đánh giá
