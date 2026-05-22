# Hướng dẫn test Giai đoạn 2 (Phase 2)

> Phase 2 là **thiết kế**: bằng chứng đạt = tài liệu đầy đủ + skeleton code chạy được. Không cần LLM cho phần test này.

---

## 0. Vị trí các artifact

| Mục Phase 2 | File |
|-------------|------|
| 2.1 Multi-Agent Architecture | `docs/phase2-agent-architecture.md` |
| 2.2 Database Design | `docs/phase2-database-design.md` |
| 2.3 API Contract | `docs/phase2-api-contract.md` |
| 2.4 Evaluation Framework | `docs/phase2-evaluation-framework.md` |
| Skeleton code | `agents/src/state.py`, `tools/registry.py`, `agents/__init__.py`, `graph.py`, `graph_smoke.py` |

---

## 1. Render Mermaid

Mở 4 file `docs/phase2-*.md` trong VS Code/Cursor (preview Markdown).

**Kỳ vọng:** mọi code-block ```` ```mermaid ```` render thành hình (flowchart Phase 2.1; ERD Phase 2.2). Nếu không thấy hình:

- VS Code: cài extension `Markdown Preview Mermaid Support`.
- Cursor: cài extension cùng tên (compatibility VSCode).

---

## 2. Skeleton agents — compile + invoke

```powershell
cd d:\kanban
# Dùng venv đã có sẵn từ Phase 1 (đã cài langgraph + langchain-core)
.\evaluation\agent_frameworks\.venv\Scripts\python.exe -m agents.src.graph_smoke
```

**Kỳ vọng output:**

```
Tools registered: ['assign_task', 'create_task', 'get_board_activity', 'get_user_skills', 'get_user_workload', 'query_tasks', 'search_similar_tasks', 'update_task_status']
[    plan] -> first_intent_seen=plan | final=end iter=6
[  assign] -> first_intent_seen=assign | final=end iter=6
[ monitor] -> first_intent_seen=monitor | final=end iter=6
[  report] -> first_intent_seen=report | final=end iter=6
[ execute] -> first_intent_seen=execute | final=end iter=6
```

> `iter=6` = `MAX_ITERS` chốt trong `state.py`. Vòng lặp xảy ra do worker stub đẩy state về Orchestrator; Phase 3 thay logic LLM thì sẽ kết thúc đúng intent rồi end.

### Trường hợp lỗi `ImportError: langgraph`

Tạo venv riêng cho `agents/`:

```powershell
cd d:\kanban\agents
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
cd ..
python -m agents.src.graph_smoke
```

---

## 3. State schema khớp tài liệu

Mở `agents/src/state.py` và đối chiếu với `docs/phase2-agent-architecture.md` §E:

- [x] Có `Intent` literal đủ 6 giá trị `plan/assign/monitor/report/execute/end`.
- [x] `AgentState` có đủ các field: `user_message`, `board_id`, `user_id`, `messages`, `intent`, `iter_count`, `plan`, `assignments`, `alerts`, `report_md`, `tool_calls`, `error`.
- [x] Hằng số `MAX_ITERS=6` và `MAX_TOOL_CALLS_PER_NODE=5`.

---

## 4. Tool registry khớp tài liệu

Mở `agents/src/tools/registry.py` đối chiếu §B của `phase2-agent-architecture.md`:

- [x] 8 tool đúng tên: `query_tasks`, `create_task`, `update_task_status`, `assign_task`, `get_user_workload`, `get_user_skills`, `search_similar_tasks`, `get_board_activity`.
- [x] Mỗi tool có `permission ∈ {read, write}` đúng dự kiến.
- [x] Mỗi tool có `input_model` và `output_model` Pydantic.

---

## 5. ERD final — sanity check

Mở `docs/phase2-database-design.md`:

- [x] Có 4 thay đổi so với Phase 1: `tasks.status/est_hours/tags`, `task_dependencies`, `agent_runs`, `agent_run_steps`.
- [x] Bảng index liệt kê đủ 6 index.
- [x] Có mục Alembic baseline (D.2) với 5 bước.

> Phase 2 **không** sửa `backend/app/models.py` để tránh phá flow Phase 1. Việc thêm field + chạy `alembic init` là nhiệm vụ **đầu Phase 3.1**.

---

## 6. API contract — sanity check

Mở `docs/phase2-api-contract.md`:

- [x] Bảng B liệt kê 13 endpoint Phase 1 đã có.
- [x] Bảng C.3 thêm 6 endpoint AI: `/agent/chat`, `/agent/breakdown`, `/agent/suggest-assignee`, `/agent/monitor`, `/agent/report`, `/agent/runs/{id}`.
- [x] WebSocket có schema frame Server→Client với 7 event type.

---

## 7. Evaluation framework — sanity check

Mở `docs/phase2-evaluation-framework.md`:

- [x] Catalog metric đủ 5 nhiệm vụ + 5 metric system.
- [x] Schema dataset Planner mẫu hợp lệ.
- [x] Rubric Planner template có JSON output schema rõ.
- [x] Bảng E có 4 ablation studies.

---

## Tổng kết Phase 2 “đạt” khi

| Hạng mục | Tiêu chí |
|----------|---------|
| 2.1 | `docs/phase2-agent-architecture.md` đủ A→I; `graph_smoke` chạy ra 5 intent + 8 tool |
| 2.2 | `docs/phase2-database-design.md` đủ A→E |
| 2.3 | `docs/phase2-api-contract.md` đủ A→G |
| 2.4 | `docs/phase2-evaluation-framework.md` đủ A→F |

Đạt → bắt đầu Phase 3.1 (Backend & Alembic).
