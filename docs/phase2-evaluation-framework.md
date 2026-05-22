# Phase 2.4 — Evaluation Framework

> Đặt khung đánh giá **trước khi viết agent** để tránh “tự đánh giá tự khen”. Phase 5 sẽ chạy thật; Phase 2 chốt **metrics**, **dataset format**, **judge prompt**.

---

## A. Metrics catalog

### A.1 Theo nhiệm vụ agent

| Nhiệm vụ | Metric chính | Metric phụ |
|----------|---------------|-------------|
| **Planner** (task breakdown) | F1 trên các subtask khớp gold (semantic match qua judge) | ROUGE-L, BERTScore, # subtasks vs gold |
| **Assigner** | Top-1 accuracy (đúng người), nDCG@3 | Skill-coverage rate, fairness (Gini workload) |
| **Monitor** | Precision/Recall trên alerts có gold | False-alert rate |
| **Reporter** | ROUGE-L vs gold summary, BERTScore | Hallucination rate (judge), độ dài / token |
| **Executor** | Exact-match tool call (tool name + arg keys) | Tool success rate (HTTP 2xx), revert rate |

### A.2 Theo hệ thống

| Nhóm | Metric | Đơn vị |
|------|--------|--------|
| **System** | Autonomy rate = 1 − tỷ lệ run cần can thiệp người dùng | % |
| **System** | Success rate = run kết thúc đúng intent + không error | % |
| **Latency** | P50, P95, P99 end-to-end | ms |
| **Cost** | tokens_in + tokens_out → USD theo bảng giá pin | USD/run |
| **Trust** | Hallucination rate (judge phát hiện claim không có evidence) | % |

> Tất cả metric system tính theo **`agent_runs`** trong DB (Phase 2.2 đã thiết kế bảng này).

---

## B. Dataset

### B.1 Cấu trúc thư mục

```
evaluation/
  datasets/
    planner/         # 50–100 mẫu
      001.json
      002.json
      ...
      _README.md
    assigner/        # 50 mẫu
    monitor/         # 50 mẫu
    reporter/        # 30–50 mẫu
    executor/        # 30 mẫu
  results/           # output mỗi lần chạy benchmark (gitignore)
  judge/
    rubric_planner.md
    rubric_assigner.md
    ...
```

### B.2 Schema mẫu — Planner

```jsonc
// evaluation/datasets/planner/001.json
{
  "id": "planner-001",
  "input": {
    "board_seed": "b_login_v1",     // tham chiếu fixture board (xem B.3)
    "goal_text": "Triển khai luồng đăng nhập email + password với JWT"
  },
  "gold": {
    "subtasks": [
      {"title": "Thiết kế bảng users + migration", "est_hours": 2, "skills": ["sql", "alembic"]},
      {"title": "Endpoint POST /auth/register", "est_hours": 3, "skills": ["fastapi", "pydantic"]},
      {"title": "Endpoint POST /auth/login + JWT", "est_hours": 3, "skills": ["fastapi", "jwt"]},
      {"title": "Frontend form login + lưu token", "est_hours": 4, "skills": ["nextjs", "react"]},
      {"title": "Test e2e luồng login", "est_hours": 2, "skills": ["pytest"]}
    ],
    "min_overlap_f1": 0.6,
    "max_subtasks": 8
  },
  "notes": "Chấp nhận biến thể title; judge so theo intent + skill"
}
```

### B.3 Fixture board

- Tạo file `evaluation/datasets/_fixtures/boards.json` chứa các board mẫu (users, skills, tasks hiện có).
- Trước khi chạy benchmark: script `evaluation/scripts/seed_fixtures.py` tải fixture vào DB sandbox riêng (`DATABASE_URL=sqlite+aiosqlite:///./eval.db`).

### B.4 Quy mô đề xuất

| Dataset | # mẫu Phase 2 (kick-off) | # mẫu Phase 5 (final) | Nguồn |
|---------|--------------------------|------------------------|--------|
| Planner | 10 (gold tay) | 50–100 (mở rộng + LLM-augmented + người review) | Tay + sinh tự động + lọc |
| Assigner | 10 | 50 |
| Monitor | 10 | 50 |
| Reporter | 5 | 30 |
| Executor | 10 | 30 |

> **Quy tắc gold**: 10 mẫu đầu phải do người gắn nhãn tay; sinh tự động chỉ được thêm vào **sau khi judge khớp ≥80% với người trên 10 mẫu này**.

---

## C. LLM-as-a-judge

### C.1 Quy tắc chống "self-judge bias"

- **Judge model ≠ generator model**. Ví dụ: generator = `llama-3.3-70b-versatile` (Groq) thì judge = `gpt-4o-mini` (hoặc ngược lại).
- Judge nhận **rubric văn bản tiếng Anh ngắn**, không thấy được prompt gốc — chỉ thấy input + gold + prediction.
- Mỗi sample chấm 2 lần (judge khác nhau hoặc judge cùng model nhưng khác temperature seed) → trung bình + report std.

### C.2 Rubric template — Planner

```text
You are an expert evaluator of project task breakdowns.

INPUT GOAL:
{goal_text}

GOLD SUBTASKS (reference, may differ in wording):
{gold_subtasks}

PREDICTED SUBTASKS:
{predicted_subtasks}

Rate the prediction on a 0–5 integer scale for EACH dimension:
1. coverage   — how well it covers the gold subtasks (semantic match, not exact words)
2. correctness — feasibility/coherence of each subtask
3. ordering   — whether dependencies make sense
4. estimation — whether est_hours look reasonable

Then output a JSON object exactly:
{
  "coverage": <int 0..5>,
  "correctness": <int 0..5>,
  "ordering": <int 0..5>,
  "estimation": <int 0..5>,
  "missing": ["<gold subtask titles not covered>"],
  "extras":  ["<predicted subtasks that are clearly off-topic>"],
  "notes": "<one short sentence>"
}
Do NOT include any text outside the JSON.
```

> Lưu chi tiết tại `evaluation/judge/rubric_planner.md` (Phase 3 sẽ copy ra). Tương tự cho 4 dataset còn lại.

### C.3 Aggregation

- F1 semantic = harmonic mean của precision/recall trên `missing`/`extras` so với `gold` (gold size).
- Score tổng = bình quân 4 chiều, làm tròn 1 số sau dấu phẩy.
- Hallucination rate = % run có `extras ≠ []` mà không justified bởi context.

---

## D. Pipeline batch evaluation (kế hoạch Phase 5)

```
evaluation/scripts/
  seed_fixtures.py          # nạp DB sandbox
  run_eval.py               # chạy 1 dataset, ghi kết quả
  aggregate_eval.py         # tổng hợp + báo cáo bảng/Markdown
```

`run_eval.py` lấy mỗi sample → POST `/agent/<endpoint>` → đọc `agent_runs` → judge → ghi `evaluation/results/{ts}/{dataset}.jsonl`.

---

## E. Ablation studies (cố định ngay, để code không nợ)

| ID | Biến | A | B | Đo cái gì |
|----|------|---|---|-----------|
| AB-1 | Multi-agent | Single agent (1 prompt làm tất cả) | Hierarchical (như Phase 2.1) | Success rate, latency, cost |
| AB-2 | RAG | Không gọi `search_similar_tasks` | Có | F1 Planner, hallucination |
| AB-3 | LLM | `gpt-4o-mini` | `llama-3.3-70b-versatile` | Mọi metric ở §A |
| AB-4 | Judge | Cùng model với generator | Khác model | Bias score (Δ điểm) |

---

## F. Definition of Done — Phase 2.4

- [x] Catalog metric đầy đủ.
- [x] Cấu trúc `evaluation/datasets/` chốt.
- [x] Rubric Planner mẫu (4 rubric còn lại làm đầu Phase 5).
- [x] Ablation studies pin sẵn.
- [ ] 10 mẫu gold đầu tiên cho Planner (kick-off Phase 5; ghi nhớ).
