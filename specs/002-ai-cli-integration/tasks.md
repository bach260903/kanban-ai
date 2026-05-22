# Tasks: AI CLI Integration — Vibe Coding Backends

**Input**: Design documents from `/specs/002-ai-cli-integration/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Scope**: 5 user stories (US-01–US-05), 25 tasks across 6 phases
**Total tasks**: 25 tasks

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependency)
- **[Story]**: Maps task to user story from spec.md (US1–US5)
- Paths follow plan.md layout: `backend/` + `frontend/` under repo root

---

# ══════════════════════════════════════════════
# PHASE 1 — Setup (DB Migration + Config)
# ══════════════════════════════════════════════

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: DB schema change, config settings, and dependency addition — no user-visible change. Unblocks all subsequent phases.

- [X] T001 Write Alembic migration `backend/alembic/versions/004_add_coding_backend.py`: `ALTER TABLE projects ADD COLUMN coding_backend VARCHAR(20) NOT NULL DEFAULT 'groq' CHECK (coding_backend IN ('groq', 'claude_code', 'openai', 'gemini'))`. Include down migration: `ALTER TABLE projects DROP COLUMN coding_backend`.
- [X] T002 [P] Add `CodingBackend` enum and column to `backend/app/models/project.py`: define `class CodingBackend(str, enum.Enum)` with values `groq`, `claude_code`, `openai`, `gemini`; add `coding_backend: Mapped[CodingBackend] = mapped_column(SQLAlchemyEnum(CodingBackend), nullable=False, default=CodingBackend.groq)` to the `Project` model.
- [X] T003 [P] Update `backend/app/config.py`: add `openai_api_key: str | None = Field(default=None)`, `openai_model: str = Field(default="gpt-4o-mini")`, `openai_base_url: str | None = Field(default=None)`, `google_ai_api_key: str | None = Field(default=None)`, `gemini_model: str = Field(default="gemini-2.0-flash")`, `claude_code_path: str = Field(default="claude")`, `gemini_cli_path: str = Field(default="gemini")`.
- [X] T004 [P] Update `backend/.env.example`: append new entries `OPENAI_API_KEY=`, `OPENAI_MODEL=gpt-4o-mini`, `OPENAI_BASE_URL=`, `GOOGLE_AI_API_KEY=`, `GEMINI_MODEL=gemini-2.0-flash`, `CLAUDE_CODE_PATH=claude`, `GEMINI_CLI_PATH=gemini` under a new `# AI CLI Backends` comment section.
- [X] T005 [P] Add `langchain-openai>=0.3.0,<0.4` to `backend/requirements.txt`.

**Checkpoint**: `alembic upgrade head` succeeds; `projects` table has `coding_backend` column with default `groq`; imports in `config.py` and `models/project.py` succeed without errors.

---

# ══════════════════════════════════════════════
# PHASE 2 — Foundational (Agent State + Graph Routing)
# ══════════════════════════════════════════════

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Agent state and graph routing must exist before any backend-specific coder node can be wired. Blocks Phase 4 (US-02/US-03).

**⚠️ CRITICAL**: No coder agent work can begin until this phase is complete.

- [X] T006 Update Pydantic schemas in `backend/app/schemas/project.py`: add `coding_backend: CodingBackend = CodingBackend.groq` to `ProjectCreate` and `ProjectUpdate` schemas; add `coding_backend: CodingBackend` to `ProjectResponse`. Import `CodingBackend` from `app.models.project`.
- [X] T007 [P] Update `backend/app/agent/state.py`: add `coding_backend: str` field to `AgentState` TypedDict with default `"groq"`. This field is propagated from `project.coding_backend` when the graph is launched.
- [X] T008 [P] Update `backend/app/agent/graph.py`: (1) add `from app.agent.nodes import cli_coder_node` stub import (module created in T013); (2) add conditional routing function `def route_coder(state: AgentState) -> str`: returns `"cli_coder_node"` if `state["coding_backend"] in ("claude_code", "gemini")`, else `"coder_node"`; (3) register `cli_coder_node` as a graph node; (4) replace direct edge to `coder_node` with `add_conditional_edges(..., route_coder, {"cli_coder_node": "cli_coder_node", "coder_node": "coder_node"})`. Note: `cli_coder_node` stub must exist before this compiles — create stub file `backend/app/agent/nodes/cli_coder_node.py` with `async def run(state): return state` simultaneously.

**Checkpoint**: `from app.agent.graph import graph` imports without error; `route_coder({"coding_backend": "claude_code"})` returns `"cli_coder_node"`; `route_coder({"coding_backend": "groq"})` returns `"coder_node"`.

---

# ══════════════════════════════════════════════
# PHASE 3 — US-01 + US-05: Backend Selection & Switching
# ══════════════════════════════════════════════

## Phase 3: User Story 1 — Chọn AI CLI Backend (Priority: P1) 🎯 MVP

**Goal**: PO chọn coding backend khi tạo project; backend hiển thị trong header; PO có thể đổi backend bất kỳ lúc nào (US-05).

**Independent Test**: `POST /api/v1/projects` with `coding_backend=claude_code` → 201 with `coding_backend=claude_code`; `PUT /api/v1/projects/{id}` with `coding_backend=openai` → 200, backend updated; `GET /api/v1/backends/available` → lists configured backends. Frontend: create-project form has Backend Selector; project header shows badge.

- [X] T009 [US1] Implement `GET /api/v1/backends/available` endpoint in `backend/app/api/v1/backends.py`: check `settings.groq_api_key`, `settings.openai_api_key`, `settings.google_ai_api_key`, and CLI binary existence via `shutil.which(settings.claude_code_path)` / `shutil.which(settings.gemini_cli_path)`; return `{"available": [...], "unavailable": [{"backend": "...", "reason": "..."}]}`; register router in `backend/app/main.py`.
- [X] T010 [US1] Update `backend/app/api/v1/projects.py`: in `POST /projects` pass `coding_backend` from `ProjectCreate` schema into `ProjectService.create()`; in `PUT /projects/{id}` pass from `ProjectUpdate`; ensure all responses include `coding_backend` field.
- [X] T011 [US1] Update `backend/app/services/project_service.py`: `create()` accepts and persists `coding_backend`; `update()` accepts and updates `coding_backend`; add 400 error if unrecognised value (handled by Pydantic enum, but verify).
- [X] T012 [P] [US1] Update `frontend/src/types/index.ts`: add `coding_backend: 'groq' | 'claude_code' | 'openai' | 'gemini'` to `Project` and `ProjectListItem` interfaces.
- [X] T013 [P] [US1] Create `frontend/src/components/atoms/backend-badge.tsx`: accepts `backend: 'groq' | 'claude_code' | 'openai' | 'gemini'` prop; renders a pill badge with label and colour — `groq` → grey / `"Groq"`, `claude_code` → amber / `"Claude Code"`, `openai` → green / `"OpenAI"`, `gemini` → blue / `"Gemini"`. Re-uses existing `badge.tsx` variant pattern or creates standalone.
- [X] T014 [P] [US1] Create `frontend/src/components/molecules/backend-selector.tsx`: `<select>` dropdown accepting `value: string` and `onChange: (v: string) => void` props; on mount calls `GET /api/v1/backends/available` and disables unavailable options with `title="Not configured"` tooltip; shows all four options regardless.
- [X] T015 [P] [US1] Update `frontend/src/services/project-api.ts`: add `coding_backend?: 'groq' | 'claude_code' | 'openai' | 'gemini'` to `ProjectCreatePayload` and `ProjectUpdatePayload`; add `getAvailableBackends()` function calling `GET /api/v1/backends/available`.
- [X] T016 [US1] Update `frontend/src/pages/project-list.tsx`: import `BackendSelector`; add it to the inline create-project form below the language selector with label "AI Coding Backend"; pass selected value to `createProject()` payload.
- [X] T017 [US1] Update `frontend/src/components/organisms/project-header.tsx`: import `BackendBadge`; render `<BackendBadge backend={project.coding_backend} />` next to the existing language badge.

**Checkpoint**: Create project → choose "Claude Code" → badge appears in header; `PUT /projects/{id}` with `coding_backend=openai` → badge updates on reload; `GET /backends/available` returns correct list based on .env.

---

# ══════════════════════════════════════════════
# PHASE 4 — US-02 + US-03: Vibe Coding Execution + Streaming
# ══════════════════════════════════════════════

## Phase 4: User Story 2 — Vibe Coding Execution (Priority: P1)

**Goal**: PO kéo task vào In Progress với Claude Code/Gemini → CLI chạy trong sandbox → output stream qua WebSocket → diff sinh sau khi CLI kết thúc (US-02). Streaming output hiển thị trong Thought Stream panel (US-03).

**Independent Test**: With `coding_backend = claude_code` and valid `ANTHROPIC_API_KEY`: drag task to In Progress → `claude --print` subprocess starts in sandbox → THOUGHT events appear in Thought Stream within 2 s → after CLI exit, diff record saved → task moves to Review column. With `coding_backend = openai`: same flow via ChatOpenAI ReAct loop.

- [X] T018 [US2] Implement `backend/app/agent/nodes/cli_coder_node.py` (replaces stub from T008):
  - `async def run(state: AgentState) -> AgentState`
  - Determine `backend = state["coding_backend"]`; select command: `claude_code` → `f"{settings.claude_code_path} --print -p {shlex.quote(prompt)}"`, `gemini` → `f"{settings.gemini_cli_path} -p {shlex.quote(prompt)}"`
  - Build `prompt` via `await ContextBuilder.build_coder_context(...)` (existing method)
  - Set env: inject `ANTHROPIC_API_KEY` (claude_code) or `GOOGLE_AI_API_KEY` (gemini) into subprocess env
  - `proc = await asyncio.create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE, cwd=sandbox_dir)`
  - Stream stdout lines → `event_publisher.publish(task_id, "THOUGHT", line)` (line-by-line)
  - Stream stderr lines → `event_publisher.publish(task_id, "ACTION", line)`
  - Wrap with `asyncio.wait_for(proc.wait(), timeout=600.0)`; on `TimeoutError`: set `agent_run.status = "timeout"`, move task to `rejected`, publish `ERROR` event `{"code": "CLI_TIMEOUT", "message": "..."}`, write audit log, return state
  - On exit code ≠ 0: detect `CLI_NOT_FOUND` (exit 127) vs `CLI_AUTH_ERROR` (exit 1 + "auth" in stderr); publish `ERROR`; move task to `rejected`; write audit log
  - On success: call `GitService.diff(sandbox_path)` → create `Diff` record → call `interrupt()`
  - BẮTBUỘC (Principle V): `await audit_service.write_pending_log(session, ...)` BEFORE subprocess start; `await audit_service.finalise_log(...)` after completion or in `except` block
- [X] T019 [P] [US2] Patch `backend/app/agent/nodes/coder_node.py` for OpenAI backend: at the top of the main function body, check `backend = state.get("coding_backend", "groq")`; if `backend == "openai"`, instantiate `ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, base_url=settings.openai_base_url)` and assign to `llm` variable instead of `ChatGroq`. All other ReAct loop logic unchanged.
- [X] T020 [US2] Update `backend/app/services/kanban_service.py` in the `todo → in_progress` dispatch path: load `project = await session.get(Project, task.project_id)`; pass `coding_backend=project.coding_backend` into the initial `AgentState` dict when launching the background agent task.

**Checkpoint**: `coding_backend = claude_code` with valid key → THOUGHT events stream to Thought Stream panel; CLI exit → diff appears in Review column; `coding_backend = openai` → same flow via existing ReAct path.

---

# ══════════════════════════════════════════════
# PHASE 5 — Polish & Hardening
# ══════════════════════════════════════════════

## Phase 5: Hardening & Tests

**Purpose**: Unit tests, integration test, performance validation. Verifies TC-01 → TC-05.

- [X] T021 [P] Write `backend/tests/unit/test_cli_coder_node.py`: mock `asyncio.create_subprocess_shell` — (1) test timeout path: process never exits → `asyncio.wait_for` raises `TimeoutError` → verify task status = `rejected`, `ERROR` event published, audit log finalised; (2) test exit code 127 path → `CLI_NOT_FOUND` error code; (3) test auth error path (exit 1 + stderr contains "auth") → `CLI_AUTH_ERROR`; (4) test success path → `GitService.diff()` called, `Diff` record created, `interrupt()` called.
- [X] T022 [P] Write `backend/tests/unit/test_backend_routing.py`: (1) test `route_coder({"coding_backend": "claude_code"})` == `"cli_coder_node"`; (2) `route_coder({"coding_backend": "gemini"})` == `"cli_coder_node"`; (3) `route_coder({"coding_backend": "groq"})` == `"coder_node"`; (4) `route_coder({"coding_backend": "openai"})` == `"coder_node"`; (5) verify `AgentState` TypedDict has `coding_backend` key.
- [X] T023 Write `backend/tests/integration/test_backend_switch.py` (uses real test DB): (1) create project with `coding_backend=groq` → verify field persisted; (2) `PUT /projects/{id}` with `coding_backend=openai` → verify updated; (3) verify no tasks or documents affected by the change; (4) verify `GET /backends/available` returns correct availability based on test env settings.
- [X] T024 [P] Validate TC-01 — CLI overhead ≤ 500 ms: add timing in `cli_coder_node.py` between `kanban_service` dispatch and `create_subprocess_shell` call; log elapsed time to audit log `input_refs`; write a pytest that asserts time < 500 ms using mocked subprocess.
- [X] T025 [P] Validate TC-03 — timeout = 10 min: in `test_cli_coder_node.py` (add to T021 suite), write test with `asyncio.wait_for` patched to raise `TimeoutError` immediately; assert task transitions to `rejected` and `CLI_TIMEOUT` error event published; assert `audit_service.finalise_log` called with `result="failure"`.

---

## Dependencies & Execution Order

### Cross-Phase Dependencies

```
Phase 1 (Setup) ─────────────────────────────► BLOCKS all feature phases
Phase 2 (Foundational) ──────────────────────► BLOCKS Phase 4 (CLICoderRunner needs routing)
Phase 3 (US-01 Backend Selection) ───────────► can start in parallel with Phase 4 after Phase 1+2
Phase 4 (US-02/US-03 Vibe Coding) ───────────► BLOCKS Phase 5 (tests need implementations)
Phase 5 (Hardening) ─────────────────────────► runs after Phase 3 + Phase 4
```

### Task-Level Dependencies

```
T001 → T002, T003, T004, T005 [P after T001]
T006 → T007, T008 [P after T006]
T007 → T008 (state.py needed before graph routing compiles)
T008 → T009, T018 (routing stub needed before CLICoderRunner can register)
T009 → T010 → T011                    # Backend API sequential
T012, T013, T014, T015 [P] → T016 → T017   # Frontend: types/components before pages
T018 → T019 [P], T020                 # CLICoderRunner before kanban_service dispatch
T018, T019, T020 → T021, T022 [P]    # Implementation before unit tests
T011 → T023                           # project_service before integration test
```

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 in parallel after T001
- **Phase 2**: T007 + T008 in parallel after T006
- **Phase 3**: T012, T013, T014, T015 in parallel (separate atom/molecule files)
- **Phase 4**: T019 in parallel with T020 (different files, both depend on T018)
- **Phase 5**: T021, T022, T024, T025 all in parallel; T023 sequential after T011

---

## Parallel Example: Phase 3 Frontend

```bash
# Step 1: Run in parallel (independent atoms/molecules/services)
Task T012: Update frontend/src/types/index.ts
Task T013: Create frontend/src/components/atoms/backend-badge.tsx
Task T014: Create frontend/src/components/molecules/backend-selector.tsx
Task T015: Update frontend/src/services/project-api.ts

# Step 2: Sequential after Step 1
Task T016: Update frontend/src/pages/project-list.tsx (needs T014, T015)

# Step 3: Sequential after Step 2
Task T017: Update frontend/src/components/organisms/project-header.tsx (needs T013, T012)
```

---

## Implementation Strategy

### MVP First (US-01 + US-02 via Claude Code)

1. Complete **Phase 1** (Setup — migration, config, deps)
2. Complete **Phase 2** (Foundational — state + graph routing)
3. Complete **T009–T011** (Backend API — project CRUD with coding_backend)
4. Complete **T018** (CLICoderRunner — Claude Code path only)
5. Complete **T020** (kanban_service dispatch)
6. **STOP and VALIDATE**: Drag task to In Progress with `claude_code` backend → verify full flow works
7. Add T019 (OpenAI), T013–T017 (Frontend UI), T021–T025 (Tests)

### Full Delivery Order

1. Phase 1 (Setup)
2. Phase 2 (Foundational)  
3. Phase 3 (US-01) + Phase 4 (US-02/03) in parallel
4. Phase 5 (Hardening)

---

## Notes

- **[P]** tasks operate on different files with no inter-dependency — safe to run in parallel
- **[Story]** label maps each task to its user story for traceability to spec.md acceptance criteria
- `coding_backend = groq` path is **unchanged** — zero regression risk for existing projects
- `coding_backend = openai` reuses the existing LangGraph ReAct loop — only the LLM provider swaps
- `coding_backend = claude_code` / `gemini` use the new `CLICoderRunner` subprocess pattern
- Constitution Principle V: `audit_service.write_pending_log()` BEFORE subprocess invocation
- Constitution Principle VI: API keys never stored in DB; passed only via subprocess env dict
- `shlex.quote(prompt)` prevents shell injection from LLM-generated task descriptions
