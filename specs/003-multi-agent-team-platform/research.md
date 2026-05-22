# Research: Platform Expansion — Multi-Agent Review, Team Management & Integrations

**Feature**: 003-multi-agent-team-platform
**Date**: 2026-05-20
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Decision 1 — JWT Authentication Library

**Decision**: `python-jose[cryptography]` + custom `AuthService` (không dùng fastapi-users)

**Rationale**: Dự án đã có `user.py` model và migration `003_add_users` — scaffold auth đã có sẵn.
`python-jose` nhẹ, không có magic black-box như fastapi-users, phù hợp với style code hiện tại
(explicit services). Tránh thêm framework trên framework.

**Alternatives considered**:
- `fastapi-users`: quá opinionated, khó tùy chỉnh role/permission logic
- `authlib`: phù hợp OAuth2 nhưng overengineered cho email/password MVP

**Dependencies**: `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`

---

## Decision 2 — Reviewer Agent: LLM Backend

**Decision**: Dùng cùng AI backend đang cấu hình cho project (không hardcode backend riêng).
Reviewer Agent tái sử dụng `ChatGroq` / `ChatOpenAI` / CLI coder pattern — chỉ khác prompt.

**Rationale**: Per spec assumption. Tránh yêu cầu user cấu hình thêm API key. Reviewer prompt
khác hoàn toàn với coder prompt nên không ảnh hưởng chất lượng.

**Reviewer prompt strategy**:
```
Role: "You are a code reviewer. Analyze the following git diff..."
Output: JSON với { score, suggestion, comments: [{file, line, content, severity}] }
```

**Alternatives considered**:
- Dùng Claude Code mặc định: gây phụ thuộc API key ANTHROPIC ngay cả khi project dùng Groq

---

## Decision 3 — Test Runner Auto-Detection

**Decision**: Detect bằng file presence trong sandbox directory:
1. `conftest.py` hoặc `pytest.ini` hoặc `pyproject.toml` → `pytest -v --tb=short --timeout=60`
2. `package.json` với key `scripts.test` → `npm test -- --watchAll=false`
3. Không tìm thấy → skip test step, ghi `test_runner: "none"` trong ReviewReport

**Rationale**: Zero config cho user. Sandbox là local directory nên file system check đủ nhanh.
Timeout riêng 60 giây per test run (trong giới hạn 5 phút tổng của Reviewer Agent).

---

## Decision 4 — Security Scan Pattern

**Decision**: Regex pattern matching trên diff lines (không dùng SAST tool ngoài):

```python
SECRET_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{6,}', 'hardcoded password'),
    (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][A-Za-z0-9_\-]{20,}', 'hardcoded API key'),
    (r'(?i)(secret|token)\s*=\s*["\'][A-Za-z0-9_\-]{20,}', 'hardcoded secret/token'),
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID'),
    (r'(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}', 'Bearer token in code'),
]
```

Chỉ scan lines bắt đầu bằng `+` trong diff (dòng được thêm vào).

**Rationale**: Đủ để catch lỗi phổ biến. Không cần Semgrep/Bandit ở MVP — tránh thêm
dependency phức tạp.

---

## Decision 5 — Webhook Delivery: Retry Mechanism

**Decision**: `asyncio` background task + Redis queue (có sẵn trong project):
- Khi trigger webhook: tạo `WebhookDelivery` record, đẩy vào Redis queue
- Background worker (`webhook_worker.py`) pull từ queue, gửi HTTP POST
- Exponential backoff: 5s → 30s → 120s (3 attempts)
- Sau 3 attempts: mark `status = "failed"`, không retry nữa

**Rationale**: Redis đã có trong tech stack (dùng cho WebSocket pub/sub). Tránh thêm Celery
chỉ cho webhook delivery. Pattern tương tự event_publisher.py hiện tại.

---

## Decision 6 — Circular Dependency Detection

**Decision**: DFS (Depth-First Search) với visited set, chạy tại thời điểm add dependency:

```python
def has_cycle(task_id, new_dep_id, all_deps) -> bool:
    """Returns True nếu thêm new_dep_id vào task_id tạo vòng lặp"""
    visited = set()
    stack = [new_dep_id]
    while stack:
        current = stack.pop()
        if current == task_id:
            return True
        if current not in visited:
            visited.add(current)
            stack.extend(all_deps.get(current, []))
    return False
```

**Rationale**: O(V+E) — đủ nhanh với số task điển hình per project (< 100). Không cần
topological sort library ngoài.

---

## Decision 7 — WIP Limit: Per-Developer Enforcement

**Decision**: Check trong `kanban_service.py` → `move_task_to_in_progress()`:
```python
in_progress_count = await task_service.count_in_progress_for_user(session, user_id, project_id)
if in_progress_count >= 1 and not override:
    raise WIPLimitExceeded(user_id)
```

`override=True` cho phép Leader/Owner bypass. `user_id` lấy từ JWT token trong request context.

**Rationale**: WIP enforcement ở service layer (không phải graph layer) — nhất quán với cách
WIP = 1 per project đang hoạt động trong `kanban_service.py`.

**Constitution update**: Nguyên tắc III cần update: "WIP = 1 per Developer" thay vì "WIP = 1 per project".
Đây là intentional extension, cần ghi vào amendment.

---

## Decision 8 — GitHub PR Integration

**Decision**: `PyGithub>=2.0.0` library. Cấu hình per-project (repo name + PAT). Gọi sau khi
PO Approve, trong `diff_service.py`:

```python
from github import Github
g = Github(project.github_pat)
repo = g.get_repo(project.github_repo)
pr = repo.create_pull(title=task.title, body=diff_content, head=branch_name, base="main")
```

PAT được mã hoá AES-256 trong DB (Nguyên tắc VI).

**Rationale**: PyGithub là wrapper REST API GitHub thuần Python, stable, không cần ghapi.

---

## Decision 9 — Analytics Queries

**Decision**: On-the-fly SQL aggregation queries với proper indexes, không dùng materialized views.
Queries chạy trên bảng `agent_runs`, `audit_logs`, `tasks` — đã có sẵn.

```sql
-- Avg completion time per backend
SELECT project.coding_backend, AVG(EXTRACT(EPOCH FROM (updated_at - started_at))) as avg_seconds
FROM agent_runs WHERE status = 'done' AND project_id = :pid
GROUP BY project.coding_backend;
```

**Rationale**: MVP scope — không đủ data volume để justify materialized views. Index trên
`(project_id, status, created_at)` đủ.

---

## Decision 10 — Reviewer LangGraph Integration

**Decision**: Thêm `reviewer_node` vào graph AFTER coder_node/cli_coder_node, trước `interrupt()`:

```
coder_node (hoặc cli_coder_node)
    → reviewer_node (mới)
    → interrupt() [HIL checkpoint]
```

`reviewer_node` luôn chạy (không conditional routing). Nếu lỗi → emit `REVIEW_ERROR` event → pass through.

**Rationale**: Đơn giản nhất — reviewer luôn chạy, lỗi không block task. Consistent với FR-008.

---

## Resolution Summary

| # | NEEDS CLARIFICATION | Resolution |
|---|---------------------|------------|
| 1 | JWT library | python-jose + custom AuthService |
| 2 | Reviewer LLM backend | Same as project's coding_backend |
| 3 | Test runner detection | File presence check (conftest.py / package.json) |
| 4 | Security scan approach | Regex patterns on diff + lines |
| 5 | Webhook retry | asyncio + Redis queue, 3 attempts backoff |
| 6 | Circular dep detection | DFS with visited set at add-time |
| 7 | WIP per-developer | Service-layer check in kanban_service |
| 8 | GitHub PR library | PyGithub 2.0 |
| 9 | Analytics | On-the-fly SQL with indexes |
| 10 | Reviewer graph position | After coder_node, before interrupt() |
