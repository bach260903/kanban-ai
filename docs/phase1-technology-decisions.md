# Giai đoạn 1 — Nghiên cứu & quyết định công nghệ

Tài liệu này ghi lại **so sánh**, **lựa chọn** và **lý do** (justification) cho đồ án Multi-Agent Harness + hệ quản lý công việc. Phần benchmark framework có mã chạy thử trong `evaluation/agent_frameworks/`.

---

## 1.1 Benchmark Multi-Agent Frameworks

### Bài toán demo thống nhất (để so sánh)

Hai agent cộng tác giải một bài **đơn giản có kiểm chứng**: cho trước danh sách số, **Agent A** đề xuất cách tính tổng (chiến lược), **Agent B** thực hiện tính toán và đưa ra **một con số cuối**. Đầu ra mong đợi: tổng đúng. Bài toán nhỏ nhưng đủ để đánh giá: luồng điều phối, tool/step, khả năng debug.

### So sánh nhanh

| Tiêu chí | CrewAI | AutoGen (AgentChat) | LangGraph |
|----------|--------|---------------------|-----------|
| **Kiểm soát luồng (control flow)** | Trung bình — hướng “crew/process”, DAG nhiệm vụ; ít explicit state machine như graph | Trung bình–cao — team, round-robin, handoff; phụ thuộc abstraction của team | **Cao** — graph, node/edge, conditional routing, checkpoint, phù hợp supervisor → workers |
| **Debug / quan sát** | Ổn với logging/task output; trace phụ thuộc phiên bản | Ổn; message-based, cần cấu hình client/model | **Tốt** — state rõ ràng, dễ log từng node, phù hợp streaming từng bước cho UI |
| **Cộng đồng / tài liệu** | Lớn, nhiều ví dụ “role + task” | Lớn (Microsoft), ecosystem đổi nhanh theo phiên bản | **Rất gắn LangChain**; tài liệu LangGraph tốt, phù hợp Python + FastAPI |
| **Phù hợp domain (workflow / board / tool)** | Tốt cho pipeline “nhiều vai trò” cố định | Tốt cho hội thoại đa agent, delegate | **Rất tốt** — tool-calling, state schema TypedDict, phân nhánh theo intent (board/AI features) |

### Quyết định

**Chọn LangGraph làm lõi orchestration** cho Agent Harness (supervisor + workers, state chung, recovery).

### Justification (ngắn gọn, dùng được trong báo cáo)

1. **Đồ án cần kiến trúc phân cấp + routing theo intent** (Planner / Assigner / Monitor / Reporter / Executor): LangGraph biểu diễn trực tiếp bằng đồ thị trạng thái, dễ chỉnh điều kiện và vòng lặp retry.
2. **Debug & demo**: state từng bước phù hợp hiển thị “thinking trace” trên frontend; CrewAI/AutoGen khó “bẻ” luồng chi tiết bằng một graph thống nhất bằng mức tương đương.
3. **Tích hợp backend**: toàn bộ stack Python (FastAPI, SQLAlchemy, tools) gắn với một runtime graph thay vì framework hội thoại trừu tượng hóa quá mức.
4. CrewAI và AutoGen **không loại bỏ** — phù hợp prototype nhanh hoặc nhóm agent đàm thoại; với mục tiêu **harness có kiểm soát + đánh giá**, LangGraph phù hợp hơn.

---

## 1.2 Chiến lược LLM

### Thử nghiệm đề xuất (latency + chất lượng)

| Model (pin version) | Vai trò gợi ý | Ghi chú |
|---------------------|----------------|---------|
| **`gpt-4o-mini-2024-07-18`** (OpenAI, cần billing) | Worker / Executor / tool-heavy | Rẻ, nhanh, ổn function calling |
| **`claude-3-5-haiku-20241022`** (Anthropic) | Worker / tóm tắt | Cần API key riêng; ổn văn bản ngắn |
| **`llama-3.3-70b-versatile`** (Groq) | Worker mặc định khi **chưa nạp tiền OpenAI** | Free tier Groq; latency thấp |
| **`gemini-1.5-flash-002`** (Google) | Worker song song để so sánh | Cần Google AI key |

> Báo cáo phải ghi **slug + ngày phát hành** đúng như cột “Model”. Ablation Phase 5 cấm so sánh hai bản khác slug.

Script gợi ý: `evaluation/scripts/llm_latency_smoke.py` (đo thời gian + in vài token; chất lượng định tính + rubric sau này).

### Model routing (Planner vs Worker)

| Thành phần | Gợi ý model | Lý do |
|------------|-------------|--------|
| **Orchestrator / Planner** | Model mạnh hơn hoặc cùng model nhưng **temperature thấp**, prompt chặt | Cần ổn định khi phân nhánh & structured plan |
| **Worker / Executor (tool)** | Model rẻ / nhanh (Groq Llama, GPT-4o-mini) | Khối lượng call lớn; tool schema giữ chất lượng |
| **Reporter** | Model nhanh, ưu tiên tóm tắt | Giảm chi phí |
| **Monitor (hybrid)** | Rule-based + LLM nhẹ khi cần giải thích | Giảm hallucination trên số liệu |

Triển khai: biến môi trường `LLM_ROUTING_JSON` hoặc file cấu hình trong `agents/` (sẽ nối vào code chính sau).

### Embedding

| Lựa chọn | Khi nào dùng |
|----------|----------------|
| **text-embedding-3-small** (OpenAI) | Khi đã có billing; pipeline RAG đơn giản, chất lượng ổn định |
| **bge-m3** (open, local/Ollama/vLLM) | Không phụ thuộc OpenAI; đồ án nhấn mạnh reproducibility |

**Đề xuất đồ án:** dev dùng **bge-m3** hoặc embedding qua `sentence-transformers` để không chặn tiến độ; khi có budget, chạy thêm nhánh **OpenAI embedding** để so sánh (ablation trong Giai đoạn 5).

---

## 1.3 Database Stack

### Relational: PostgreSQL vs SQLite

| | SQLite | PostgreSQL |
|---|--------|------------|
| **Đồ án / demo local** | **Khuyến nghị** — zero-ops, file DB | Overkill nếu chưa deploy |
| **Production / đội nhóm** | Hạn chế đồng thời | **Khuyến nghị** |

**Quyết định:** **SQLite + aiosqlite** cho giai đoạn phát triển; **PostgreSQL** khi triển khai Docker/cloud; Alembic giữ migration tương thích cả hai (URL qua `DATABASE_URL`).

### Vector: ChromaDB vs Qdrant

| | ChromaDB | Qdrant |
|---|----------|--------|
| **Đồ án** | **Đủ tốt** — nhúng process, ít cấu hình | Mạnh hơn khi scale, HA |
| **Ops** | Đơn giản | Cần service riêng |

**Quyết định:** **ChromaDB** (persistent folder) cho đồ án; Qdrant ghi trong báo cáo là hướng nâng cấp.

### ERD sơ bộ

Xem file `docs/erd-phase1.md` (Mermaid) — các thực thể: `users`, `boards`, `columns`, `tasks`, `comments`, `skills`, `user_skills`, `task_assignments`, `activity_log`.

---

## 1.4 Stack ứng dụng

| Lớp | Lựa chọn | Ghi chú |
|-----|----------|---------|
| Backend | **FastAPI** | async, OpenAPI, phù hợp AI |
| Frontend | **Next.js 14** + **Tailwind** + **shadcn/ui** + **dnd-kit** | Board kéo thả, UI thống nhất |
| State | **TanStack Query** (server state) + **Zustand** (UI/client nhẹ) | Tránh nhồi toàn bộ vào một store |

---

## 1.5 Positioning & Novelty (đính kèm Đề cương — Phase 0.3)

| Sản phẩm tham chiếu | Cách họ đưa AI vào | Khoảng trống đồ án nhắm tới |
|----------------------|--------------------|------------------------------|
| **Trello AI / Atlassian Intelligence** | Gợi ý mô tả task, tự sinh card từ ghi chú | Đóng kín, không lộ trace agent; không cá nhân hoá theo workload/skill |
| **Asana Intelligence** | Smart status, smart goals, summary | Tóm tắt tốt nhưng chưa thể hiện *multi-agent reasoning* công khai |
| **ClickUp Brain** | Q&A trên workspace, viết doc | Bias về RAG generative; ít supervisor/worker theo intent |
| **Notion AI** | Tóm tắt trang, chuyển từ note → task | Không có vòng lặp Monitor → Reporter |

**Đặc trưng nổi bật của đồ án (claim novelty cấp luận văn):**

1. **Harness multi-agent có kiểm soát**: graph LangGraph hiển thị **trace từng node** trên UI (không phải đoạn chat đen) → giảng viên/người dùng kiểm tra được điều phối → rõ ràng hơn các sản phẩm thương mại.
2. **Hybrid Monitor**: kết hợp **rule-based** (WIP, due_at, throughput) với **LLM giải thích**, hạn chế hallucination trên số liệu — khác với agent thuần generative.
3. **Skill-aware Assigner**: dùng `user_skills` + workload + retrieval task tương tự (RAG) thay vì chỉ chia tròn — đáp ứng đề cương “cá nhân hoá theo người dùng”.
4. **Evaluation chuẩn học thuật**: bộ 50–100 sample/task + LLM-as-judge + ablation Single vs Multi-Agent — phần lớn sản phẩm đối chuẩn không công bố con số này.

> Đoạn này dùng được nguyên văn cho mục **“Định nghĩa Novelty”** trong Đề cương.

---

## 1.6 Rủi ro & Mitigation (Risk Register)

| Mã | Rủi ro | Khả năng | Tác động | Mitigation |
|----|--------|---------|---------|------------|
| R1 | Hết quota OpenAI/Anthropic giữa kỳ | Trung bình | Cao | Mặc định Groq Llama 3.3 70B; bật flag `LLM_PROVIDER_FALLBACK` đổi provider runtime |
| R2 | CrewAI không cài được trên Python 3.14 | Đã xảy ra | Trung bình | Đã có venv Python **3.12/3.13** riêng cho CrewAI (`requirements-crewai.txt`); báo cáo benchmark 2/3 framework là hợp lệ |
| R3 | LangGraph API thay đổi giữa các minor | Trung bình | Trung bình | Pin version trong `backend/requirements.txt`; sandbox `agents/` có lock riêng |
| R4 | Hallucination khi gọi tool gây sai DB | Trung bình | Cao | Validation layer (Phase 3.2): mọi tool phải qua Pydantic schema + permission check trước khi commit |
| R5 | Latency P95 vượt ngưỡng demo (>8s) | Trung bình | Trung bình | Routing: Planner = model chậm/chính xác, Worker tool-call = model nhanh; cache embedding (Phase 5.4) |
| R6 | Drift dataset đánh giá (tự đánh giá tự khen) | Thấp | Cao | Tách judge model ≠ generator model; thêm rubric tay 10 ví dụ làm “gold” |
| R7 | Rò rỉ key API trong git | Thấp | Rất cao | `.env` đã ignore; CI nên thêm `gitleaks` ở Phase 5 |

---

## 1.7 Definition of Done — Phase 1

| Hạng mục | Bằng chứng (artifact) |
|----------|------------------------|
| 1.1 Benchmark | `evaluation/agent_frameworks/demo_*.py` chạy, output có tổng đúng; bảng so sánh trong tài liệu này |
| 1.2 LLM strategy | `verify_groq.py` OK + `llm_latency_smoke.py` ra ít nhất 1 dòng latency; bảng Model + Routing trong tài liệu |
| 1.3 DB stack | `docs/erd-phase1.md` mermaid render được; `backend/app/models.py` khớp ERD |
| 1.4 Stack | `/api/auth` + `/api/boards` chạy qua được Swagger; `npm run build` frontend OK |
| 0.3 Đề cương | Mục **1.5** & **1.6** đủ để paste vào Đề cương; reading list đánh dấu xong |

---

## Việc cần làm tiếp (chuyển sang Phase 2)

1. Thiết kế kiến trúc multi-agent (roles, tools, hierarchical graph, state schema, memory) — `docs/phase2-agent-architecture.md`.
2. ERD final + vector collections + Alembic baseline — `docs/phase2-database-design.md`.
3. API contract (REST + WebSocket cho streaming agent) — `docs/phase2-api-contract.md`.
4. Evaluation framework (metrics, dataset, judge) — `docs/phase2-evaluation-framework.md`.
5. Skeleton code trong `agents/src/` để Phase 3 nhồi logic vào.
