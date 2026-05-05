# Kanban AI Multi-Agent

Nền tảng quản lý công việc Kanban tích hợp AI đa tác tử (multi-agent), hỗ trợ lập kế hoạch, giám sát tiến độ, gợi ý phân công và báo cáo.

## Tổng quan

Đây là monorepo gồm các thành phần:

- `frontend`: Next.js 14, Tailwind, dnd-kit, giao diện Kanban + AI assistant
- `backend`: FastAPI, SQLAlchemy, WebSocket, API auth/boards/tasks/agent
- `agents`: logic tác tử (orchestrator, planner, assigner, monitor, reporter, executor)
- `evaluation`: bộ dữ liệu và script benchmark/eval
- `docs`: tài liệu kiến trúc, quyết định công nghệ, checklist kiểm thử

## Tính năng nổi bật

- Quản lý board Kanban: cột, task, kéo thả, comment, phân công
- Quản lý thành viên theo UID cho từng dự án
- Hồ sơ người dùng + kỹ năng để AI gợi ý phân công
- Trợ lý AI đa tác tử:
  - `Planner`: phân rã mục tiêu thành subtask
  - `Assigner`: gợi ý người phù hợp
  - `Monitor`: phát hiện tắc nghẽn, quá hạn, task chất lượng thấp
  - `Reporter`: tạo báo cáo tổng hợp
  - `Executor`: thao tác task theo lệnh
- Lưu lịch sử chạy AI (`agent_runs`, `agent_run_steps`) + realtime qua WebSocket

## Yêu cầu môi trường

- Windows + PowerShell
- Node.js 18+
- Python 3.14 (backend)
- (Tuỳ chọn benchmark) Python 3.12 cho CrewAI
- API key LLM: `GROQ_API_KEY`

## Cài đặt nhanh

```powershell
cd d:\kanban
copy .env.example .env
```

Điền key trong `.env`:

```env
GROQ_API_KEY=your_key_here
```

## Chạy dự án local

### Backend

```powershell
cd d:\kanban\backend
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

### Frontend

```powershell
cd d:\kanban\frontend
copy .env.example .env.local
npm install
npm run dev
```

Mở: <http://localhost:3000>

## Luồng sử dụng đề xuất

1. Đăng ký/đăng nhập
2. Tạo board và thêm thành viên bằng UID
3. Tạo task, set hạn chót, phân công
4. Dùng AI để:
   - phân rã mục tiêu
   - gợi ý người phụ trách
   - quét tắc nghẽn
   - tạo báo cáo

## Kiểm thử nhanh

### Kiểm tra Groq key

```powershell
cd d:\kanban
python evaluation\scripts\verify_groq.py
```

### Build frontend

```powershell
cd d:\kanban
npm run build --workspace=frontend
```

### Eval planner end-to-end

```powershell
cd d:\kanban\evaluation\scripts
python seed_fixtures.py --api http://127.0.0.1:8000
python run_eval.py planner --api http://127.0.0.1:8000
python aggregate_eval.py
```

Kết quả ở `evaluation/results/<timestamp>/report.md`.

## Cấu trúc thư mục

```text
backend/
  app/
    routers/
    services/
    models.py
    schemas.py

agents/
  src/agents/
  src/tools/
  src/graph.py

frontend/
  src/app/
  src/components/
  src/lib/

evaluation/
  datasets/
  judge/
  scripts/

docs/
```

## Lưu ý bảo mật & đóng góp

- Không commit file chứa secret (`.env`, `.env.local`)
- Không commit artifacts local (venv, build cache, database local)
- Trước khi push, chạy lint/build để đảm bảo ổn định

---

Nếu bạn cần checklist release/public repo chuẩn (README badges, changelog, license, contribution guide), có thể bổ sung thêm ở bước tiếp theo.
