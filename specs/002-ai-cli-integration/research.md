# Research: AI CLI Integration — Vibe Coding Backends

**Phase 0 Output** | Date: 2026-05-18 | Plan: [plan.md](plan.md) | Spec: [spec.md](spec.md)

---

## 1. Claude Code CLI

### 1.1 CLI Interface

| Aspect | Detail |
|---|---|
| Binary | `claude` (Anthropic) |
| Install | `npm install -g @anthropic-ai/claude-code` hoặc download từ claude.ai |
| Non-interactive mode | `claude --print -p "prompt"` → prints output, exits |
| Working directory | CLI reads/writes files relative to CWD (set sandbox dir as CWD) |
| Auth | `ANTHROPIC_API_KEY` env var; hoặc token từ `claude auth login` |
| Streaming | stdout is streaming per line |
| Exit code | 0 = success, non-zero = error |

### 1.2 Integration Decision

**Decision**: Invoke `claude --print -p "{system_prompt}\n\n{task_description}"` với CWD = sandbox dir.

**Rationale**:
- `--print` mode là non-interactive, phù hợp cho server-side automation
- Claude Code tự xử lý file reads/writes trong CWD — không cần `file_tools` của Neo-Kanban
- Output (dạng conversation) stream qua stdout → pipe vào WebSocket event publisher

**Alternative rejected**: Claude SDK trực tiếp — không tận dụng được file editing capabilities của Claude Code CLI.

**Diff generation**: Sau khi CLI exit, chạy `git diff HEAD` trong sandbox → sinh Diff record.

### 1.3 Prompt Design

```
System context:
- Constitution
- Task title + description
- MEMORY.md (nếu có)
- Codebase map tóm tắt

Task instruction:
"Implement the task. Make all necessary file changes in the current directory.
When done, summarize what files you changed."
```

---

## 2. OpenAI Integration

### 2.1 CLI vs SDK Decision

**Decision**: Dùng **OpenAI Python SDK** (không phải CLI binary).

**Rationale**:
- `openai` CLI binary chủ yếu cho API exploration, không phải agentic coding
- Python SDK cho phép dùng Function Calling với `file_tools` và `sandbox_tools` — giữ cùng ReAct pattern như Groq
- Không cần cài thêm binary trong môi trường server

**Approach**: Thay thế `ChatGroq` bằng `ChatOpenAI` từ `langchain-openai` trong coder_node khi backend = `openai`.

### 2.2 Configuration

| Env var | Default | Mô tả |
|---|---|---|
| `OPENAI_API_KEY` | — | Required |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `OPENAI_BASE_URL` | — | Tuỳ chọn, cho compatible endpoints |

### 2.3 Integration Pattern

```python
# Trong coder_node — switch dựa trên project.coding_backend
if backend == "openai":
    llm = ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)
elif backend == "groq":
    llm = ChatGroq(model=settings.groq_model, api_key=settings.groq_api_key)
```

Không cần thay đổi tools hay graph structure — chỉ swap LLM provider.

---

## 3. Gemini CLI

### 3.1 CLI Interface

| Aspect | Detail |
|---|---|
| Binary | `gemini` (Google AI CLI) |
| Install | `npm install -g @google/gemini-cli` |
| Non-interactive | `gemini -p "prompt"` |
| Auth | `GOOGLE_AI_API_KEY` hoặc `gcloud auth application-default login` |
| CWD awareness | CLI có thể đọc files từ CWD (cần xác nhận) |
| Streaming | stdout streaming |

### 3.2 Integration Decision

**Decision**: Invoke `gemini -p "{prompt}"` với CWD = sandbox dir, tương tự Claude Code approach.

**Rationale**:
- Google Gemini CLI hỗ trợ file access trong CWD
- Pattern giống Claude Code → cùng `CLICoderRunner` class, chỉ khác command

**Alternative**: Gemini Python SDK (`google-generativeai`) + LangChain Gemini adapter — phức tạp hơn cần thiết cho MVP; để sau.

---

## 4. Architecture: CLICoderRunner

### 4.1 Thiết kế

```
coding_backend
    ├── groq        → coder_node (LangGraph ReAct loop) — UNCHANGED
    ├── claude_code → CLICoderRunner(cmd="claude --print -p ...")
    └── gemini      → CLICoderRunner(cmd="gemini -p ...")
    └── openai      → coder_node (ReAct loop, swap ChatGroq → ChatOpenAI)
```

### 4.2 CLICoderRunner (mới)

```python
# backend/app/agent/nodes/cli_coder_node.py
async def run_cli_coder(state, cmd_template, event_publisher) -> dict:
    prompt = build_cli_prompt(state)         # từ context_builder
    cmd = cmd_template.format(prompt=shlex.quote(prompt))
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=PIPE, stderr=PIPE,
        cwd=sandbox_dir,
    )
    # Stream stdout lines as THOUGHT events
    async for line in proc.stdout:
        await event_publisher.publish(task_id, "THOUGHT", line.decode())
    await asyncio.wait_for(proc.wait(), timeout=600)  # 10 min
    # After exit → git diff → Diff record → interrupt()
```

### 4.3 Routing trong graph.py

Thêm `cli_coder_node` song song với `coder_node`:
```python
def route_coder(state) -> str:
    backend = state["coding_backend"]
    if backend in ("claude_code", "gemini"):
        return "cli_coder_node"
    return "coder_node"  # groq + openai dùng ReAct loop
```

---

## 5. Data Model Changes

### 5.1 DB Migration

Thêm column vào `projects` table:
```sql
ALTER TABLE projects ADD COLUMN coding_backend VARCHAR(20)
  NOT NULL DEFAULT 'groq'
  CHECK (coding_backend IN ('groq', 'claude_code', 'openai', 'gemini'));
```

Migration: `backend/alembic/versions/004_add_coding_backend.py`

### 5.2 ORM

```python
# backend/app/models/project.py — thêm field
class CodingBackend(str, enum.Enum):
    groq = "groq"
    claude_code = "claude_code"
    openai = "openai"
    gemini = "gemini"

coding_backend: Mapped[CodingBackend] = mapped_column(
    SQLAlchemyEnum(CodingBackend), nullable=False, default=CodingBackend.groq
)
```

---

## 6. Config Changes

```python
# backend/app/config.py — thêm các settings mới
openai_api_key: str | None = Field(default=None)
openai_model: str = Field(default="gpt-4o-mini")
openai_base_url: str | None = Field(default=None)

google_ai_api_key: str | None = Field(default=None)
gemini_model: str = Field(default="gemini-2.0-flash")

claude_code_path: str = Field(default="claude")   # path to binary
gemini_cli_path: str = Field(default="gemini")    # path to binary
```

---

## 7. Dependency Changes

```
# backend/requirements.txt additions
langchain-openai>=0.3.0   # for OpenAI backend
```

Không cần thêm dependency cho Claude Code và Gemini — dùng `asyncio.create_subprocess_shell`.

---

## 8. Resolved Unknowns

| Question | Resolution |
|---|---|
| OpenAI CLI binary? | Không dùng — dùng Python SDK + LangChain |
| Claude Code streaming? | stdout line-by-line → WebSocket THOUGHT events |
| Gemini CWD support? | `gemini -p "prompt"` reads CWD files — confirmed từ Google CLI docs |
| Diff generation cho CLI backends? | `git diff HEAD` sau khi CLI exit, xử lý qua GitService.diff() hiện tại |
| Per-project backend storage? | Column `coding_backend` trên bảng `projects`, migration 004 |
| Graph routing | Conditional edge dựa trên `state["coding_backend"]` |
| Timeout | `asyncio.wait_for(proc.wait(), timeout=600)` — đồng nhất với Groq timeout |
| Error handling | CLI exit code ≠ 0 → `ERROR` event + task → `rejected` + audit log |
