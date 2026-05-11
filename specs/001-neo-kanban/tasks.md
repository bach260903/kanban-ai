# Tasks: Neo-Kanban — AI-Agentic Project Management Platform

**Input**: Design documents from `/specs/001-neo-kanban/`
**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/ ✅

**Scope**: Phase 1 (core agentic loop) + Phase 2 (AI enhancements)
**Total tasks**: 118 tasks across 20 phases (T007a added G7, T008a added G4, T073a added G9)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependency)
- **[Story]**: Maps task to user story from spec.md (US1–US16)
- Paths follow plan.md layout: `backend/` + `frontend/` under repo root

---

# ══════════════════════════════════════════════
# PHASE 1 — Neo-Kanban Core Agentic Loop
# ══════════════════════════════════════════════

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the monorepo skeleton, dev tooling, and Docker environment before any feature work.

- [X] T001 Create repository root structure: `backend/`, `frontend/`, `docker-compose.yml`, `.env.example` per plan.md layout
- [ ] T002 Initialise FastAPI backend skeleton: `backend/app/main.py` (empty router), `backend/app/config.py` (Pydantic Settings reading `.env`), `backend/requirements.txt` with pinned Phase 1 deps including `whatthepatch==1.0.6  # D-04: parse unified diff → Monaco original/modified strings`
- [ ] T003 [P] Initialise React/Vite frontend: run `npm create vite@latest frontend -- --template react-ts`, add deps from plan.md `package.json`, configure `tsconfig.json` strict mode
- [ ] T004 [P] Configure frontend code quality: `frontend/.eslintrc.json` (TypeScript + React Hooks rules), `frontend/.prettierrc`, add `lint` and `format` scripts to `package.json`
- [ ] T005 Write `docker-compose.yml`: PostgreSQL 16 service (port 5432), Redis 7 service (port 6379), env vars from `.env`. Before writing docker-compose.yml, create `backend/Dockerfile` with content: `FROM python:3.11-slim`, `WORKDIR /app`, `COPY requirements.txt .`, `RUN pip install --no-cache-dir -r requirements.txt`, `COPY . .`, `EXPOSE 8000`, `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]`. The docker-compose.yml references this image via `build: ./backend`.
- [ ] T006 [P] Create `backend/.env.example` listing all required vars: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `OPENAI_API_KEY`, `SANDBOX_ROOT`

**Checkpoint**: `docker-compose up` starts PG + Redis; `uvicorn app.main:app` returns 200 on `GET /health`; `npm run dev` serves Vite welcome page.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB schema, ORM models, Pydantic schemas, JWT auth, and audit service must exist before any user story can be built.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T007 Write Alembic migration `backend/alembic/versions/001_initial_schema.py`: create all Phase 1 tables (`projects`, `documents`, `tasks`, `agent_runs`, `diffs`, `feedbacks`, `audit_logs`, `intents`) including the `EXCLUDE USING btree` WIP constraint and the `NO UPDATE / NO DELETE` rules on `audit_logs`. Note: `diffs` table includes `original_content` and `modified_content` TEXT columns (needed for Monaco DiffEditor at T065; see data-model.md and research.md D-04). `intents` table stores persistent Intent records: `id`, `project_id`, `content`, `created_at` with index `idx_intents_project_id`.
- [ ] T007a Create pytest infrastructure: `backend/tests/__init__.py` (empty) and `backend/tests/conftest.py` with fixtures: (1) `async_db_session` — per-function DB session with rollback, no commit; (2) `test_client` — httpx AsyncClient with FastAPI app, overrides DB dependency; (3) `auth_headers` — session-scoped JWT token `{"Authorization": "Bearer <token>"}`; (4) `sample_project` — function-scoped project in test DB. Add to `requirements-dev.txt`: `pytest-asyncio`, `httpx`, `pytest-cov`. Dependency: T007. Verify: `pytest backend/tests/ --collect-only` collects without import or fixture errors.
- [ ] T008 [P] Implement SQLAlchemy async ORM models in `backend/app/models/`: `project.py` (Project), `document.py` (Document with type/status enums)
- [ ] T008a [P] Implement SQLAlchemy async ORM model `backend/app/models/intent.py`: Intent class with fields `id` (UUID PK), `project_id` (UUID FK → projects), `content` (Text), `created_at` (TIMESTAMPTZ). Relationship: Intent belongs_to Project (many-to-one). Export from `backend/app/models/__init__.py`.
- [ ] T009 [P] Implement SQLAlchemy async ORM models in `backend/app/models/`: `task.py` (Task with status enum), `agent_run.py` (AgentRun), `diff.py` (Diff with `original_content` + `modified_content` TEXT columns — see research.md D-04: use `whatthepatch.parse_patch()` to convert git unified diff into `original_content`/`modified_content` strings for Monaco DiffEditor; ensure `whatthepatch==1.0.6` is in requirements.txt from T002), `feedback.py` (Feedback), `audit_log.py` (AuditLog — INSERT-only guard at service layer)
- [ ] T010 Implement all Pydantic v2 schemas in `backend/app/schemas/`: `project.py` (Create/Update/Response), `document.py` (Response/Update/RevisionRequest), `task.py` (Response/Move/RejectRequest), `agent_run.py` (AgentRunResponse)
- [ ] T011 Implement async SQLAlchemy engine + `get_db` async session dependency in `backend/app/database.py`
- [ ] T012 [P] Implement JWT auth middleware in `backend/app/middleware/auth.py`: `HTTPBearer` dependency using `python-jose`, validate expiry + signature, raise HTTP 401 on failure
- [ ] T013 [P] Implement global exception handlers in `backend/app/middleware/error_handlers.py`: map domain exceptions (`WIPLimitError`, `InvalidTransitionError`, `SandboxEscapeError`, `NotFoundError`) → correct HTTP codes (409, 400, 400, 404)
- [ ] T014 Implement `AuditService` in `backend/app/services/audit_service.py`: `write_pending_log(session, ...)` (INSERT with `result="awaiting_hil"`), `finalise_log(session, log_id, result, output_refs)` (UPDATE — the only permitted update path)
- [ ] T015 Wire everything into `backend/app/main.py`: FastAPI app factory, lifespan (open/close DB pool), include routers placeholder, register error handlers, add `GET /health` route

**Checkpoint**: `alembic upgrade head` succeeds; all models import without errors; `GET /health` returns `{"status": "ok"}`.

---

## Phase 3: User Story 1 — Tạo Dự Án Mới (Priority: P1) 🎯 MVP

**Goal**: PO can create a new project with name, description, and primary language. Duplicate names are rejected.

**Independent Test**: `POST /api/v1/projects` with valid body → 201 with project data; same name again → 409.

- [ ] T016 [US1] Implement `ProjectService` in `backend/app/services/project_service.py`: `create()` with uniqueness check (raises `DuplicateNameError` on conflict), `get()`, `list()`, `update()`, `archive()`
- [ ] T017 [US1] Implement Projects API router in `backend/app/api/v1/projects.py`: `GET /`, `POST /`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}` — all `async def`, all guarded by JWT dependency, register in `main.py`
- [ ] T018 [P] [US1] Create Axios API service in `frontend/src/services/api.ts`: base URL from `VITE_API_URL` env, request interceptor to attach `Authorization: Bearer <jwt>`, response interceptor to handle 401 redirect
- [ ] T019 [P] [US1] Define all Phase 1 TypeScript interfaces in `frontend/src/types/index.ts`: `Project`, `Document`, `Task`, `AgentRun`, `Diff`, `Feedback`, `AuditLog`
- [ ] T020 [P] [US1] Create Atom components in `frontend/src/components/atoms/`: `button.tsx` (primary/secondary/danger variants), `badge.tsx` (status colour map), `spinner.tsx` (loading), `text-input.tsx` (controlled)
- [ ] T021 [US1] Implement `projectStore` Zustand store in `frontend/src/store/project-store.ts`: `projects`, `currentProject`, `setProjects()`, `setCurrentProject()`
- [ ] T022 [US1] Implement project API calls in `frontend/src/services/project-api.ts`: `listProjects()`, `createProject()`, `getProject()`, `updateProject()`
- [ ] T023 [US1] Implement `ProjectList` page in `frontend/src/pages/project-list.tsx`: fetch + display project cards, inline create-project form (name required, description optional, language select), show 409 error inline
- [ ] T024 [US1] Implement `App.tsx` with `BrowserRouter` routes: `/projects` → `ProjectList`, `/projects/:id` → `ProjectWorkspace` (stub), `/projects/:id/constitution` → stub; add `frontend/src/main.tsx`

**Checkpoint**: Open browser at `/projects`; create a project; see it in the list; creating duplicate shows error message.

---

## Phase 4: User Story 2 — Xem Danh Sách & Mở Dự Án (Priority: P1)

**Goal**: PO can open any project from the list and see its restored workspace.

**Independent Test**: Create 2 projects; reload page; both appear in list; clicking one navigates to its workspace.

- [ ] T025 [US2] Implement `ProjectWorkspace` page shell in `frontend/src/pages/project-workspace.tsx`: fetch project by `:id` on mount, store in `projectStore`, render `ProjectHeader` + tab placeholders (Kanban, Documents, Constitution)
- [ ] T026 [US2] Implement `ProjectHeader` organism in `frontend/src/components/organisms/project-header.tsx`: display project name + language badge + tab navigation links

**Checkpoint**: Clicking a project card navigates to `/projects/:id` and shows the project name in the header.

---

## Phase 5: User Story 3 — Khai Báo Constitution (Priority: P1)

**Goal**: PO can write and save a Markdown constitution; Agent reads it on every task run.

**Independent Test**: Write constitution → save → reload → constitution appears; verify `GET /constitution` returns saved content.

- [ ] T027 [US3] Implement Constitution API endpoints in `backend/app/api/v1/projects.py`: `GET /{id}/constitution` and `PUT /{id}/constitution` (body: `{"content": "..."}`)
- [ ] T028 [US3] Implement `DocumentEditor` molecule in `frontend/src/components/molecules/document-editor.tsx`: `@monaco-editor/react` in Markdown language mode, controlled value/onChange props
- [ ] T029 [US3] Implement `ConstitutionEditor` page in `frontend/src/pages/constitution-editor.tsx`: load constitution via `GET /constitution`, render `DocumentEditor`, Save button calls `PUT /constitution`, show success toast; add route `/projects/:id/constitution` in `App.tsx`

**Checkpoint**: Navigate to Constitution tab; type rules; Save; reload; rules persist.

---

## Phase 6: User Story 4 — Nhập Intent & Nhận SPEC.md (Priority: P1)

**Goal**: PO submits Intent text; Architect Agent generates SPEC.md; document appears in Draft state.

**Independent Test**: `POST /generate-spec` with intent → 202 with `agent_run_id`; poll `GET /agent-runs/{id}` until status = `awaiting_hil`; `GET /documents?type=SPEC` returns document with content.

- [ ] T030 [US4] Define `AgentState` TypedDict in `backend/app/agent/state.py`: fields: `project_id`, `task_id`, `agent_run_id`, `phase`, `constitution`, `intent`, `spec_content`, `plan_content`, `tasks_list`, `diff_content`, `feedback`, `error`
- [ ] T031 [US4] Implement `ContextBuilder` in `backend/app/agent/context_builder.py`: `build_architect_context(project_id, session)` reads `projects.constitution` from DB + assembles system prompt; returns `{"system": "...", "human": "..."}`
- [ ] T032 [US4] Implement `spec_node` async function in `backend/app/agent/nodes/spec_node.py`: calls LangChain ChatOpenAI with architect context + intent → generates SPEC markdown → saves to `documents` table → calls `interrupt()` → sets `agent_run.status = awaiting_hil`. BẮTBUỘC (Constitution Principle V): Call `audit_service.write_pending_log()` BEFORE each LLM call and BEFORE each file write; call `audit_service.finalise_log()` after completion or in except block on error. TIMEOUT (TC-03): Wrap core logic in `asyncio.wait_for(_generate_spec(state), timeout=60.0)`; on `asyncio.TimeoutError` set `agent_run.status = "timeout"` and publish ERROR event via WebSocket with message "Spec generation exceeded 60-second limit. Please retry."
- [ ] T033 [US4] Implement `file_tools.py` LangChain Tools in `backend/app/tools/file_tools.py`: `read_file(path)`, `write_file(path, content)`, `list_files(directory)` — all validate path is inside `SANDBOX_ROOT/{project_id}/`
- [ ] T034 [US4] Implement `sandbox_tools.py` LangChain Tool in `backend/app/tools/sandbox_tools.py`: `run_command(cmd)` using `asyncio.create_subprocess_shell` with `asyncio.wait_for(timeout=60)`, captures stdout/stderr
- [ ] T035 [US4] Implement LangGraph `StateGraph` skeleton in `backend/app/agent/graph.py`: define nodes (spec_node, plan_node stub, task_breakdown_node stub, coder_node stub), edges, conditional edges for HIL resume, compile with `AsyncPostgresSaver` checkpointer. Add comment `# Nodes imported as stubs — see T044, T048, T058`. ALSO create the following 3 stub files at the same time so graph.py can import without ImportError: (1) `backend/app/agent/nodes/plan_node.py` — `async def run(state: dict) -> dict: """Stub — sẽ được implement đầy đủ ở T044.""" pass`; (2) `backend/app/agent/nodes/task_breakdown_node.py` — `async def run(state: dict) -> dict: """Stub — sẽ được implement đầy đủ ở T048.""" pass`; (3) `backend/app/agent/nodes/coder_node.py` — `async def run(state: dict) -> dict: """Stub — sẽ được implement đầy đủ ở T058.""" pass`. Stubs contain ONLY the function signature + docstring + pass — NO real logic.
- [ ] T036 [US4] Implement `DocumentService` in `backend/app/services/document_service.py`: `create()`, `get_by_type()`, `update_content()`, `approve()` (validates current status), `request_revision()` (writes feedback + sets status)
- [ ] T037 [US4] Implement Documents router + agent endpoints in `backend/app/api/v1/documents.py` and `backend/app/api/v1/agent_runs.py`: `GET /documents`, `GET /documents/{id}`, `PUT /documents/{id}`, `POST /generate-spec` (202 + launch background task), `GET /agent-runs/{id}`; register both routers in `main.py`. Intent persistence: in `POST /generate-spec`, before calling Architect Agent: (a) call `IntentService.create(project_id=project_id, content=intent_text)` to save intent to DB; (b) return `intent_id` in response body: `{"agent_run_id": "...", "intent_id": "...", "document_id": "..."}`. Also add `GET /projects/{id}/intents` endpoint returning Intent list ordered by `created_at DESC`.
- [ ] T038 [US4] Implement `document-api.ts` in `frontend/src/services/document-api.ts`: `getDocuments()`, `getDocument()`, `updateDocument()`, `generateSpec()`, `getAgentRun()`
- [ ] T039 [US4] Implement `use-document.ts` hook in `frontend/src/hooks/use-document.ts`: fetch document, poll `agent_run_id` status every 3 s until terminal state, expose `document`, `agentRun`, `isGenerating`
- [ ] T040 [US4] Implement `DocumentPanel` organism in `frontend/src/components/organisms/document-panel.tsx`: displays document content (read-only Monaco), status badge, loading spinner during generation; add Intent textarea + "Generate SPEC" button when no SPEC exists; wire to `use-document.ts`

**Checkpoint**: Type intent in workspace → click Generate SPEC → spinner shows → SPEC.md content appears in DocumentPanel with "Draft" badge.

---

## Phase 7: User Story 5 — Duyệt SPEC.md (Priority: P1)

**Goal**: PO can Approve SPEC (→ Approved) or Request Revision with feedback (→ Agent regenerates).

**Independent Test**: With SPEC in Draft state — `POST /documents/{id}/approve` → status = `approved`; `POST /documents/{id}/revise` with feedback → status = `revision_requested` and new agent run starts.

- [ ] T041 [US5] Implement document approve + revise endpoints in `backend/app/api/v1/documents.py`: `POST /{id}/approve` (calls `document_service.approve()`, writes audit log), `POST /{id}/revise` (calls `document_service.request_revision()`, launches spec_node with feedback in context)
- [ ] T042 [US5] Handle revision retry in `spec_node`: if `state.feedback` is present, include it in the LangChain prompt; after regeneration, call `interrupt()` again; increment `document.version`
- [ ] T043 [US5] Add Approve / Request Revision action bar to `DocumentPanel` in `frontend/src/components/organisms/document-panel.tsx`: show action bar when `document.status = "draft"` or `"revision_requested"`, Approve button → `POST /approve`, Revision button → textarea for feedback + `POST /revise`

**Checkpoint**: SPEC in Draft → click Approve → badge changes to Approved; click Request Revision with feedback → badge changes to Revision Requested → new SPEC content appears.

---

## Phase 8: User Story 6 — Nhận & Duyệt PLAN.md (Priority: P1)

**Goal**: After SPEC is Approved, PO triggers PLAN.md generation; Agent produces plan; PO approves/revises.

**Independent Test**: SPEC approved → `POST /generate-plan` → 202; poll until PLAN appears; `POST /documents/{plan_id}/approve` → status = `approved`.

- [ ] T044 [US6] Implement `plan_node` async function in `backend/app/agent/nodes/plan_node.py`: reads approved SPEC content from DB + constitution → generates PLAN.md markdown → saves to `documents` table → calls `interrupt()`; handle feedback revision same as spec_node. This file overwrites the stub created at T035; remove stub comment after implementing. BẮTBUỘC (Constitution Principle V): Call `audit_service.write_pending_log()` BEFORE each LLM call and BEFORE each file write; call `audit_service.finalise_log()` after completion or in except block. TIMEOUT (TC-03): Wrap core logic in `asyncio.wait_for(_generate_plan(state), timeout=60.0)`; on `asyncio.TimeoutError` set `agent_run.status = "timeout"` and publish ERROR event via WebSocket.
- [ ] T045 [US6] Implement `POST /generate-plan` endpoint in `backend/app/api/v1/documents.py`: validates SPEC has `status = approved` (returns 400 if not), launches `plan_node` background task, returns 202 with `agent_run_id`
- [ ] T046 [US6] Add PLAN display to `ProjectWorkspace` in `frontend/src/pages/project-workspace.tsx`: Documents tab shows both SPEC and PLAN sections; "Generate PLAN" button appears only when SPEC is approved and no PLAN exists; PLAN DocumentPanel includes approve/revise action bar

**Checkpoint**: After approving SPEC, click Generate PLAN → PLAN appears → approve it → system proceeds to task breakdown.

---

## Phase 9: User Story 7 — Task Tự Động Xuất Hiện Trong To Do (Priority: P1)

**Goal**: Immediately after PO approves PLAN.md, tasks are auto-created in To Do column.

**Independent Test**: Approve PLAN → `GET /tasks` returns tasks in `todo` status with titles matching PLAN sections; no manual input required.

- [ ] T047 [US7] Implement `task_breakdown_node` async function in `backend/app/agent/nodes/task_breakdown_node.py`: receives approved PLAN content → calls LLM to extract structured task list `[{title, description, priority}]` → batch-INSERT into `tasks` table with `status = todo` → no `interrupt()` needed (no HIL here; auto-completes)
- [ ] T048 [US7] Wire `task_breakdown_node` into LangGraph graph: triggered automatically when `plan_node` state is approved (graph edge from PLAN_GENERATION → TASK_BREAKDOWN → IDLE). The `task_breakdown_node.py` file was created as a stub at T035 and implemented at T047; remove stub comment in that file after T047 completes.
- [ ] T049 [US7] Implement `TaskService` in `backend/app/services/task_service.py`: `create_bulk()` (for breakdown), `list_by_project()`, `get()`, `count_in_progress()` (for WIP check)
- [ ] T050 [US7] Implement Tasks router `GET /projects/{id}/tasks` in `backend/app/api/v1/tasks.py`: return tasks grouped by status `{todo: [...], in_progress: [...], review: [...], done: [...], rejected: [], conflict: []}` ; register in `main.py`
- [ ] T051 [US7] Implement `taskStore` Zustand in `frontend/src/store/task-store.ts`: `columns` (keyed by status), `setColumns()`, `moveTask(taskId, fromStatus, toStatus)` (optimistic update)
- [ ] T052 [US7] Implement `task-api.ts` in `frontend/src/services/task-api.ts`: `getTasks()`, `moveTask()`, `approveTask()`, `rejectTask()`, `getDiff()`
- [ ] T053 [US7] Implement `TaskCard` molecule in `frontend/src/components/molecules/task-card.tsx`: display task title, description truncated, priority number, status badge; wrap with `useSortable` from `@dnd-kit/sortable` (drag handle inactive for now)
- [ ] T054 [US7] Implement `KanbanColumn` organism in `frontend/src/components/organisms/kanban-column.tsx`: receives `column` prop (status + tasks list), renders column header + list of `TaskCard`; use `SortableContext` from dnd-kit (not yet connected to drop)
- [ ] T055 [US7] Implement `KanbanBoard` organism in `frontend/src/components/organisms/kanban-board.tsx`: fetch tasks on mount via `getTasks()`, populate `taskStore.columns`, render 4 `KanbanColumn` (To Do, In Progress, Review, Done); add to `ProjectWorkspace` Kanban tab

**Checkpoint**: Approve PLAN → reload Kanban tab → task cards appear in To Do column with correct titles and order.

---

## Phase 10: User Story 8 — Kéo Task Vào In Progress & Kích Hoạt Agent (Priority: P1)

**Goal**: PO drags a task to In Progress; WIP = 1 is enforced; Coder Agent starts.

**Independent Test**: No tasks in In Progress → drag task → moves to In Progress and agent status shows "running". Second drag → 409 error shown. No drag by user = Agent does not start.

- [ ] T056 [US8] Implement `KanbanService` in `backend/app/services/kanban_service.py`: `move_task(task_id, to_status, session)` — validates transition is in allowlist, calls `task_service.count_in_progress()` before `in_progress` move (raises `WIPLimitError` if ≥ 1), dispatches Coder Agent background task on `in_progress` move
- [ ] T057 [US8] Implement `POST /tasks/{id}/move` endpoint in `backend/app/api/v1/tasks.py`: body `{"to": "in_progress"}`, calls `kanban_service.move_task()`, returns `{task_id, from_status, to_status, agent_run_id}`; 409 on WIP limit
- [ ] T058 [US8] Implement `coder_node` async function in `backend/app/agent/nodes/coder_node.py`: reads task description + constitution + file_tools + sandbox_tools → runs LangChain ReAct agent loop → writes files to `SANDBOX_ROOT/{project_id}/` → generates git diff via `git_service.diff()` → saves `Diff` record → calls `interrupt()` for HIL review. This file overwrites the stub created at T035; remove stub comment after implementing. BẮTBUỘC (Constitution Principle V): Call `audit_service.write_pending_log()` BEFORE each LLM call, BEFORE each `read_file`/`write_file` tool call, and BEFORE each `run_terminal` command; call `audit_service.finalise_log()` after each action or in except block — especially `run_terminal` must log the command BEFORE executing it.
- [ ] T059 [US8] Implement `GitService.init_repo()` and `GitService.diff()` in `backend/app/git/git_service.py`: `init_repo(sandbox_path)` initialises a bare git repo; `diff(sandbox_path)` returns unified diff string + list of changed files, plus original and modified file contents
- [ ] T060 [US8] Add drag-and-drop to `KanbanBoard` + `KanbanColumn`: wrap board in `DndContext` from `@dnd-kit/core`, implement `onDragEnd` handler; enable `useSortable` in `TaskCard`; only allow dropping into `in_progress` column from `todo` (other drops are no-ops)
- [ ] T061 [US8] Implement `use-kanban.ts` hook in `frontend/src/hooks/use-kanban.ts`: `onDragEnd` → calls `moveTask(taskId, "in_progress")` → on 409 shows error toast → on success stores `agentRunId` in task store; poll `GET /agent-runs/{id}` every 3 s to update agent status badge on task card

**Checkpoint**: Drag task to In Progress → card moves → spinner badge appears → cannot drag second task (toast shows WIP error).

---

## Phase 11: User Story 9 — Xem Diff & Approve hoặc Reject Code (Priority: P1)

**Goal**: After Agent completes, task moves to Review; PO sees Monaco Diff; can Approve (→ Done) or Reject (→ In Progress).

**Independent Test**: Task in Review → `GET /tasks/{id}/diff` returns diff with original + modified; `POST /approve` → task status = done; `POST /reject` with feedback → task status = in_progress and new agent run starts.

- [ ] T062 [US9] Implement `GET /tasks/{id}/diff` endpoint in `backend/app/api/v1/tasks.py`: returns latest Diff record for task (404 if none), includes `original_content`, `modified_content`, `files_affected`, `review_status`
- [ ] T063 [US9] Implement `POST /tasks/{id}/approve` endpoint in `backend/app/api/v1/tasks.py`: validates task in `review` status, sets `diff.review_status = approved`, calls `kanban_service.move_task(task_id, "done")`, writes audit log
- [ ] T064 [US9] Implement `POST /tasks/{id}/reject` endpoint in `backend/app/api/v1/tasks.py`: validates task in `review`, sets `diff.review_status = rejected`, writes Feedback record, moves task back to `in_progress`, relaunches `coder_node` with feedback in context
- [ ] T065 [US9] Implement `DiffViewer` molecule in `frontend/src/components/molecules/diff-viewer.tsx`: `@monaco-editor/react` `DiffEditor` component in read-only mode, `original` and `modified` props from API response, green/red line highlighting via Monaco options `renderSideBySide: true`. Note: Backend has already handled diff parsing via `whatthepatch` (T009). Frontend only consumes `original_content` and `modified_content` from `GET /tasks/{id}/diff` — no additional parsing needed on the frontend.
- [ ] T066 [US9] Add Review panel to `ProjectWorkspace`: when `taskStore` has a task in `review` status, show modal/side panel with `DiffViewer` + Approve button + Reject section (textarea for feedback + Reject button); wire to `task-api.ts` approve/reject calls

**Checkpoint**: Agent completes → task card moves to Review column → DiffViewer shows coloured diff → Approve → card moves to Done; Reject with feedback → card returns to In Progress → Agent retries.

---

## Phase 12: Phase 1 Polish & Hardening

**Purpose**: Timeout enforcement, error handling, audit log UI, integration tests. Validates TC-01 → TC-07.

- [ ] T067 Enforce task timeout in `coder_node`: wrap full agent loop in `asyncio.wait_for(timeout=600)` (10 min); on timeout, move task to `rejected`, write `ERROR` audit log, return error message to frontend via agent_run status
- [ ] T068 [P] Write unit tests for WIP limit in `backend/tests/unit/test_task_service.py`: test `count_in_progress()` correctly counts, test `move_task()` raises `WIPLimitError` when limit reached, test idempotent approve
- [ ] T069 [P] Write unit tests for Kanban transitions in `backend/tests/unit/test_kanban_transitions.py`: test all valid transitions pass, test all invalid backward transitions raise `InvalidTransitionError`, test `todo → in_progress` triggers agent dispatch
- [ ] T070 Write integration tests in `backend/tests/integration/`: `test_projects_api.py` (CRUD + duplicate name), `test_documents_api.py` (approve gate blocks generate-plan without approved SPEC), `test_tasks_api.py` (WIP limit end-to-end via real DB)
- [ ] T071 Add read-only Audit Log tab to `ProjectWorkspace`: fetch `GET /audit-logs` paginated, display in table with columns: agent, action_type, timestamp, result — no delete/edit controls

**Checkpoint**: All YC-01 → YC-22 manually verified; TC-01 → TC-07 criteria met; unit + integration tests pass.

---

# ══════════════════════════════════════════════
# PHASE 2 — Neo-Kanban AI Enhancements
# ══════════════════════════════════════════════
#
# Prerequisites: Phase 1 fully complete and stable.
# Do not start Phase 2 tasks before Phase 1 checkpoint passes.

---

## Phase 13: User Story 10 — Giám Sát AI Theo Thời Gian Thực (Priority: P1) [Phase 2]

**Goal**: WebSocket infrastructure + Thought Streaming UI — PO sees Agent events (THOUGHT, TOOL_CALL, TOOL_RESULT, ACTION, ERROR, STATUS_CHANGE) in real time.

**Independent Test**: With task In Progress — open WebSocket at `ws://.../ws/tasks/{id}/stream` — receive sequence-numbered events within 2 s of each agent step; disconnect + reconnect with `CATCH_UP` → missed events replayed.

- [ ] T072 [US10] Write Alembic migration `backend/alembic/versions/002_phase2_schema.py`: add tables `stream_events`, `agent_pause_states`, `memory_entries`, `codebase_maps`, `task_branches`, `inline_comments`. Note: `original_content` and `modified_content` columns are already present in `diffs` from migration 001 (T007). T072 only needs to verify schema — do NOT re-add these columns.
- [ ] T073 [P] [US10] Implement SQLAlchemy ORM models for Phase 2 tables in `backend/app/models/`: `stream_event.py`, `agent_pause_state.py`, `memory_entry.py`, `codebase_map.py`, `task_branch.py`, `inline_comment.py`
- [ ] T073a [P] Create stub `backend/app/agent/nodes/reviewer_node.py`: `async def run(state: dict) -> dict: """Reviewer Node — stub. Phase 1 MVP: no-op, passes to DONE state. Full implementation deferred post-MVP. See spec.md US-09.""" return {**state, "review_result": "auto_approved", "reviewer": "stub"}`. Dependency: T035 (graph.py). Priority: Low — does not block MVP.
- [ ] T074 [US10] Implement `EventPublisher` in `backend/app/websocket/event_publisher.py`: `publish(task_id, event_type, content, session)` — assigns next `sequence_number` (SELECT MAX FOR UPDATE), INSERTs to `stream_events`, publishes JSON to Redis channel `task:{task_id}:events`
- [ ] T075 [US10] Implement `EventConsumer` in `backend/app/websocket/event_consumer.py`: async Redis subscriber that reads from `task:{task_id}:events` channel and yields parsed event dicts
- [ ] T076 [US10] Implement WebSocket handler in `backend/app/websocket/ws_handler.py`: authenticate JWT from `?token=` query param, accept connection, send `CONNECTED` message with `latest_sequence`, handle `CATCH_UP` (query DB + replay), relay live events from `EventConsumer`, handle `PAUSE`/`RESUME` client messages, send `STREAM_END` when agent run completes
- [ ] T077 [US10] Register WebSocket router in `backend/app/main.py`: add `app.add_api_websocket_route("/ws/tasks/{task_id}/stream", ws_handler.handle)`
- [ ] T078 [US10] Instrument `coder_node` with event publishing: add `await event_publisher.publish(...)` calls for THOUGHT (before each LLM call), TOOL_CALL (before tool), TOOL_RESULT (after tool), ACTION (before file write/command), ERROR (on exception), STATUS_CHANGE (on state transition) in `backend/app/agent/nodes/coder_node.py`
- [ ] T079 [US10] Also publish STATUS_CHANGE events in `spec_node` and `plan_node` for SPEC_GENERATION and PLAN_GENERATION transitions in `backend/app/agent/nodes/spec_node.py` and `plan_node.py`
- [ ] T080 [US10] Implement WebSocket client in `frontend/src/services/websocket-client.ts`: connect with JWT token, track `lastSequence`, send `CATCH_UP` on reconnect, auto-reconnect with 1 s backoff, expose `onEvent(callback)` and `send(message)` methods
- [ ] T081 [US10] Implement `use-thought-stream.ts` hook in `frontend/src/hooks/use-thought-stream.ts`: subscribes to `websocket-client`, maintains ordered `events[]` array (sorted by `sequence_number`), exposes `events`, `isConnected`, `streamEnded`
- [ ] T082 [US10] Implement `ThoughtStreamPanel` organism in `frontend/src/components/organisms/thought-stream-panel.tsx`: renders scrolling event list; each event shows type label (colour-coded), timestamp, content; auto-scrolls to bottom; shows `STREAM_END` summary badge
- [ ] T083 [US10] Add Thought Stream toggle to `ProjectWorkspace` in `frontend/src/pages/project-workspace.tsx`: slide-in panel that appears when a task is `in_progress`; uses `use-thought-stream.ts`; closeable

**Checkpoint**: Agent runs → Thought Stream panel opens → events appear with type labels in real-time; close browser + reopen → events replay from DB.

---

## Phase 14: User Story 11 — Tạm Dừng & Điều Hướng Lại Agent (Priority: P1) [Phase 2]

**Goal**: PO can pause the Agent mid-run, enter steering instructions, and resume — Agent stops within 1 step.

**Independent Test**: Task in_progress → `POST /tasks/{id}/pause` → within 1 agent step, `agent_run.status = paused`; `POST /tasks/{id}/resume` with instructions → agent continues and next THOUGHT references instructions.

- [ ] T084 [US11] Implement `PauseService` in `backend/app/services/pause_service.py`: `pause(task_id)` — SET Redis key `pause:{task_id}`; INSERT/UPDATE `agent_pause_states` row with `state = paused`, `paused_at = now()`; `resume(task_id, instructions)` — DEL Redis key; UPDATE `agent_pause_states` with `state = running`, `steering_instructions = instructions`, `resumed_at = now()`; `is_paused(task_id)` — check Redis key existence
- [ ] T085 [US11] Implement Pause/Resume/PauseState endpoints in `backend/app/api/v1/`: `POST /tasks/{id}/pause`, `POST /tasks/{id}/resume`, `GET /tasks/{id}/pause-state`; register new `pause_router` in `main.py`. Note: These REST endpoints are test-facing and for non-WebSocket clients. Primary frontend path uses WebSocket messages `{"type": "PAUSE"/"RESUME"}` (T088–T090). In MVP, frontend does NOT call these REST endpoints directly — no frontend consumer task needed for these endpoints.
- [ ] T086 [US11] Add pause check to `coder_node` at each LangGraph node entry in `backend/app/agent/nodes/coder_node.py`: `if await pause_service.is_paused(task_id): raise PauseSignal()` — caught by graph runner, transitions agent_run status to `paused`, publishes `STATUS_CHANGE` event
- [ ] T087 [US11] Inject `steering_instructions` into context in `backend/app/agent/context_builder.py`: `build_coder_context()` reads `agent_pause_states.steering_instructions` from DB; if non-null, appends to system prompt: "Updated instructions from Project Owner: {instructions}"
- [ ] T088 [US11] Handle `PAUSE`/`RESUME` messages in WebSocket handler `backend/app/websocket/ws_handler.py`: on `PAUSE` message → call `pause_service.pause(task_id)`; on `RESUME` message → call `pause_service.resume(task_id, steering_instructions)`
- [ ] T089 [US11] Implement `PauseResumeControls` molecule in `frontend/src/components/molecules/pause-resume-controls.tsx`: Pause button (sends `PAUSE` via websocket-client), steering instruction textarea + Resume button (sends `RESUME`); show/hide based on agent pause state; display 30-min idle warning
- [ ] T090 [US11] Add `PauseResumeControls` to `ThoughtStreamPanel` in `frontend/src/components/organisms/thought-stream-panel.tsx`: show controls when `isConnected && !streamEnded`; wire to `websocket-client.send()`

**Checkpoint**: Agent running → click Pause → agent stops (≤1 step confirmed in Thought Stream) → type steering instructions → Resume → next THOUGHT event references instructions.

---

## Phase 15: User Story 12 — Ghi Bài Học Tự Động Vào Bộ Nhớ (Priority: P2) [Phase 2]

**Goal**: When Task moves to Done, system auto-writes a MEMORY.md entry with all 5 required fields.

**Independent Test**: Approve task → `GET /projects/{id}/memory` returns entry with `timestamp`, `task_id`, `summary`, `files_affected`, `lessons_learned` all non-empty.

- [ ] T091 [US12] Implement `MemoryService.create_entry()` in `backend/app/services/memory_service.py`: takes `project_id`, `task_id`, `diff` record → calls LLM to extract `summary` and `lessons_learned` from diff content → INSERTs `memory_entries` row with all 5 required fields
- [ ] T092 [US12] Implement `MemoryService.export_memory_file()` in `backend/app/services/memory_service.py`: queries all `memory_entries` for project ordered by `entry_timestamp ASC` → renders to MEMORY.md format defined in `plan.md` → writes to `{SANDBOX_ROOT}/{project_id}/MEMORY.md`
- [ ] T093 [US12] Wire `memory_service.create_entry()` + `export_memory_file()` into `kanban_service.move_task()` in `backend/app/services/kanban_service.py`: call both after task status is set to `done` and diff is approved

**Checkpoint**: Approve a task → `GET /memory` shows entry; check `{SANDBOX_ROOT}/{project_id}/MEMORY.md` file exists with correct content.

---

## Phase 16: User Story 13 — Chỉnh Sửa Bộ Nhớ Thủ Công (Priority: P2) [Phase 2]

**Goal**: PO can view, edit, and delete memory entries; deleted entries never appear in Agent context again.

**Independent Test**: Delete an entry → `GET /memory` no longer returns it → trigger new task → `MEMORY.md` file does not contain deleted entry.

- [ ] T094 [US13] Inject MEMORY.md into agent context in `backend/app/agent/context_builder.py`: `build_coder_context()` reads `{SANDBOX_ROOT}/{project_id}/MEMORY.md` if file exists → appends to system prompt under section "## Past Lessons"
- [ ] T095 [US13] Implement Memory CRUD API in `backend/app/api/v1/memory.py`: `GET /projects/{id}/memory`, `GET /projects/{id}/memory/{entry_id}`, `PUT /projects/{id}/memory/{entry_id}` (body: `{summary?, lessons_learned?}`), `DELETE /projects/{id}/memory/{entry_id}` → after each write/delete, call `export_memory_file()` to regenerate `MEMORY.md`; register router in `main.py`
- [ ] T096 [US13] Implement `MemoryEditor` organism in `frontend/src/components/organisms/memory-editor.tsx`: fetch memory entries list, display as expandable cards (title = summary, body = lessons_learned + files_affected), Edit button opens inline form, Delete button with confirmation dialog, optimistic UI removal on delete
- [ ] T097 [US13] Add Memory tab to `ProjectWorkspace` in `frontend/src/pages/project-workspace.tsx`: render `MemoryEditor` under Memory tab

**Checkpoint**: Open Memory tab → see entries → delete one → entry disappears immediately → run another task → deleted lesson not in `MEMORY.md`.

---

## Phase 17: User Story 14 — Phân Tích Cấu Trúc Codebase (Priority: P2) [Phase 2]

**Goal**: Agent receives a structured codebase map (file/class/function list) instead of raw file contents.

**Independent Test**: Task starts → `GET /codebase-map` returns JSON matching schema in `plan.md` with correct file count; Agent THOUGHT events reference correct file paths from the map.

- [ ] T098 [US14] Implement `CodebaseMapper` in `backend/app/services/codebase_mapper.py`: accepts `project_root` + `language` (`python`|`javascript`|`typescript`) → walks directory tree → uses tree-sitter to extract classes + functions + signatures per file → assembles `CodebaseMap` JSON per schema in `plan.md` → stores in `codebase_maps` table → returns JSON
- [ ] T099 [US14] Implement codebase map API in `backend/app/api/v1/codebase.py`: `GET /projects/{id}/codebase-map` — returns latest map from DB if exists; if no map or `?refresh=true`, triggers synchronous scan via `codebase_mapper.py` (≤10 s for 500 files); register router in `main.py`
- [ ] T100 [US14] Inject codebase map into `context_builder` in `backend/app/agent/context_builder.py`: `build_coder_context()` calls `codebase_mapper.run(project_id)` at task start → appends serialised map JSON to system prompt under "## Codebase Structure" (replace raw file reads)
- [ ] T101 [US14] Add `tree-sitter==0.23.0`, `tree-sitter-python==0.23.2`, `tree-sitter-javascript==0.23.0`, `tree-sitter-typescript==0.23.0` to `backend/requirements.txt`; test grammar loading in isolation before wiring

**Checkpoint**: Start task → Thought Stream shows Agent referencing specific file paths + function names from codebase map without hallucinating paths.

---

## Phase 18: User Story 15 — Quản Lý Git Tự Động Theo Task (Priority: P3) [Phase 2]

**Goal**: Auto-create git branch on In Progress; squash-merge on Approve; show Conflict label if merge fails.

**Independent Test**: Drag task to In Progress → `GET /tasks/{id}/branch` returns branch with `status = active`; Approve task → branch status = merged and 1 squash commit on main; introduce conflict manually → status = conflict and task shows "Conflict" label.

- [ ] T102 [US15] Implement `BranchService` in `backend/app/git/branch_service.py`: `create_task_branch(task_id, sandbox_path)` — creates branch `task/{task_id[:8]}`, INSERTs `task_branches` row; `squash_and_merge(task_id, sandbox_path)` — squashes all commits on branch to 1 commit, merges into main; `detect_conflict(task_id)` — catches `GitCommandError` during merge, updates `task_branches.status = conflict`, moves task to `conflict` status
- [ ] T103 [US15] Wire `branch_service` into `kanban_service` in `backend/app/services/kanban_service.py`: on `todo → in_progress` → call `branch_service.create_task_branch()`; on `review → done` (after approve) → call `branch_service.squash_and_merge()` (catches conflict → sets conflict status)
- [ ] T104 [US15] Implement Branch endpoint in `backend/app/api/v1/branches.py`: `GET /tasks/{id}/branch` returns `{task_id, branch_name, status, created_at, merged_at}`; register router in `main.py`
- [ ] T105 [US15] Show branch info + conflict badge in `TaskCard` molecule in `frontend/src/components/molecules/task-card.tsx`: if `task.status = conflict`, show red "Conflict" badge and tooltip "Merge conflict detected — resolve manually"; fetch branch info from `task-api.ts`

**Checkpoint**: Task moves to In Progress → git branch exists; Approve → 1 squash commit on main; conflict scenario → Conflict badge on task card.

---

## Phase 19: User Story 16 — Inline Comment Trên Diff Khi Reject (Priority: P3) [Phase 2]

**Goal**: PO can click on diff lines to add inline comments; Reject sends `{file, line, comment}` list to Agent.

**Independent Test**: Open DiffViewer → click line 42 → comment box appears → type comment → submit Reject → `GET /tasks/{id}/comments` returns comment with correct `file_path`, `line_number`, `comment_text`.

- [ ] T106 [US16] Implement Inline Comments API in `backend/app/api/v1/branches.py` (extend existing file): `GET /tasks/{id}/comments`, `POST /tasks/{id}/comments` (body: `{file_path, line_number, comment_text}`), `DELETE /tasks/{id}/comments/{comment_id}`; validate `file_path` is in current diff's `files_affected`
- [ ] T107 [US16] Extend `POST /tasks/{id}/reject` endpoint in `backend/app/api/v1/tasks.py`: include inline comments in coder_node context — query all `inline_comments` for task + current diff, pass as structured list `{inline_comments: [{file_path, line_number, comment_text}]}` alongside text feedback
- [ ] T108 [US16] Add Monaco line-click to `DiffViewer` in `frontend/src/components/molecules/diff-viewer.tsx`: add `editor.onMouseDown` listener on the modified-side editor instance; on click, extract `lineNumber` + `fileName` from Monaco model → call `onLineClick(file, line)` prop callback
- [ ] T109 [US16] Implement `InlineCommentOverlay` molecule in `frontend/src/components/molecules/inline-comment-overlay.tsx`: rendered as a Monaco decoration overlay — `GlyphMarginWidget` positioned at clicked line; contains textarea + Save + Cancel; on Save calls `POST /comments`; shows saved comments as read-only decorations on diff
- [ ] T110 [US16] Implement `use-inline-comments.ts` hook in `frontend/src/hooks/use-inline-comments.ts`: manages `comments[]` state, exposes `addComment()`, `removeComment()`, `getCommentsForLine()`, `getCommentPayload()` (returns array for reject body)
- [ ] T111 [US16] Wire inline comments into Reject flow in `ProjectWorkspace` in `frontend/src/pages/project-workspace.tsx`: pass `use-inline-comments.getCommentPayload()` alongside text feedback in `POST /reject` body

**Checkpoint**: DiffViewer → click line → comment box appears → save comment → Reject → check Agent's next THOUGHT references the specific file + line + comment text.

---

## Phase 20: Phase 2 Polish & Validation

**Purpose**: Validate all Phase 2 acceptance criteria (TC-08 → TC-14). Performance checks. Final hardening.

- [ ] T112 [P] Validate TC-08: stream event latency ≤ 2 s — measure time from coder_node publish call to frontend event receipt using browser devtools WebSocket inspector; document result
- [ ] T113 [P] Validate TC-09: Pause stops within 1 step — write automated test that sends PAUSE and counts how many events arrive after the signal; assert ≤ 1 additional event
- [ ] T114 [P] Validate TC-10: 100% of Done tasks produce MEMORY.md entry with all 5 fields — run 5 approve cycles; inspect DB and file
- [ ] T115 Validate TC-11: codebase map ≤ 10 s for 500 files — benchmark `CodebaseMapper` with a synthetic 500-file Python project; document result; optimise if needed
- [ ] T116 [P] Validate TC-12 + TC-13: squash commit count = 1 per approve; inline comment `{file, line}` round-trip — end-to-end manual scenario
- [ ] T117 Add Phase 2 Pydantic schemas for new types in `frontend/src/types/index.ts`: `StreamEvent`, `MemoryEntry`, `CodebaseMap`, `InlineComment`, `PauseState`, `TaskBranch`

---

## Dependencies & Execution Order

### Cross-Phase Dependencies

```
Phase 1 (Setup) ──────────────────────────────► must complete before any feature phase
Phase 2 (Foundational) ────────────────────────► BLOCKS all user story phases
Phase 3 (US1 - Projects) ──────────────────────► BLOCKS Phase 4 (US2 depends on projects API)
Phase 3 + Phase 4 + Phase 5 ───────────────────► BLOCK Phase 6 (US4 needs project + constitution)
Phase 6 (US4 - SPEC gen) ──────────────────────► BLOCKS Phase 7 (US5 - SPEC approval)
Phase 7 (US5 - SPEC approve) ──────────────────► BLOCKS Phase 8 (US6 - PLAN gen)
Phase 8 (US6 - PLAN approve) ──────────────────► BLOCKS Phase 9 (US7 - task breakdown)
Phase 9 (US7 - Kanban read) ───────────────────► BLOCKS Phase 10 (US8 - Kanban drag)
Phase 10 (US8 - Agent trigger) ────────────────► BLOCKS Phase 11 (US9 - Diff review)
Phase 11 (US9) + Phase 12 ─────────────────────► BLOCK all Phase 2 work (Phase 1 must be stable)
Phase 13 (US10 - WebSocket) ───────────────────► BLOCKS Phase 14 (US11 - Pause/Steer)
Phase 15 (US12 - Memory write) ────────────────► BLOCKS Phase 16 (US13 - Memory read/edit)
Phase 18 (US15 - Git branch) ──────────────────► BLOCKS Phase 19 (US16 - Inline comments)
```

### Phase 2 Inter-Dependencies

```
T072 (DB migration 002) ──► T073 (models) ──► T074-T076 (WS infra)
T074-T076 (WS infra) ──────────────────────► T080-T083 (WS frontend)
T078-T079 (instrument nodes) needed before T080 (WS client) can receive events
T084 (PauseService) ───────────────────────► T085-T090 (Pause frontend)
T091-T093 (Memory write) ──────────────────► T094-T097 (Memory read + UI)
T098-T101 (Codebase map) ──────────────────► already usable by any subsequent coder_node run
T102-T104 (Git branch) ────────────────────► T105 (branch badge) + T106-T111 (inline comments)
```

### Parallel Opportunities Within Phases

- **Phase 1**: T003 + T004 + T006 in parallel after T001 + T002
- **Phase 2 Foundational**: T008 + T009 in parallel; T012 + T013 in parallel (after T011)
- **Phase 3 (US1)**: T018 + T019 + T020 in parallel; T021 + T022 + T023 in parallel (after API exists)
- **Phase 13 (US10)**: T073 + T074 in parallel (different files); T080 + T081 in parallel (after T076)
- **Phase 20 (Polish)**: T112 + T113 + T114 + T116 in parallel

---

## Parallel Example: Phase 13 (WebSocket Infrastructure)

```bash
# Step 1: Run in parallel (no inter-dependency)
Task T072: Write Alembic migration 002
Task T073: Implement Phase 2 SQLAlchemy models

# Step 2: Run in parallel (all depend on T073)
Task T074: Implement EventPublisher
Task T075: Implement EventConsumer

# Step 3: Sequential (depends on T074 + T075)
Task T076: Implement WebSocket handler

# Step 4: Run in parallel (depends on T076)
Task T080: WebSocket client (frontend)
Task T078: Instrument coder_node with publish calls
Task T079: Instrument spec_node + plan_node
```

---

## Implementation Strategy

### MVP First (Phase 1 Only)

1. Complete **Phase 1** (Setup)
2. Complete **Phase 2** (Foundational — CRITICAL, blocks everything)
3. Complete **Phase 3** (US1 — Create Project)
4. Complete **Phase 4** (US2 — Open Project)
5. Complete **Phase 5** (US3 — Constitution)
6. Complete **Phase 6** (US4 — SPEC generation)
7. Complete **Phase 7** (US5 — SPEC approval)
8. Complete **Phase 8** (US6 — PLAN generation + approval)
9. Complete **Phase 9** (US7 — Task auto-creation)
10. Complete **Phase 10** (US8 — Kanban drag + Agent trigger)
11. Complete **Phase 11** (US9 — Diff + Approve/Reject)
12. Complete **Phase 12** (Polish + validation)
13. **STOP and VALIDATE**: Verify TC-01 → TC-07 pass; full loop from Intent → Done works

### Incremental Phase 2 Delivery

14. Complete **Phase 13** (US10 — Thought Stream) → validate TC-08
15. Complete **Phase 14** (US11 — Pause & Steer) → validate TC-09
16. Complete **Phase 15** (US12 — Memory write) → validate TC-10
17. Complete **Phase 16** (US13 — Memory read/edit) → validate TC-14
18. Complete **Phase 17** (US14 — Codebase map) → validate TC-11
19. Complete **Phase 18** (US15 — Git branching) → validate TC-12
20. Complete **Phase 19** (US16 — Inline comments) → validate TC-13
21. Complete **Phase 20** (Full Phase 2 validation)

---

## Notes

- **[P]** tasks operate on different files with no inter-dependency — safe to run in parallel
- **[Story]** label maps each task to its user story for traceability to spec.md acceptance criteria
- Each user story phase ends with an independently testable **Checkpoint** — stop and verify before proceeding
- Agent-related tasks (T030–T035, T047–T048, T058) require LangGraph setup (T035) to be complete first
- Frontend tasks for a feature cannot start until the corresponding API endpoint exists (or is mocked)
- Constitution Principle V: always write the `audit_log` row BEFORE the agent action — enforced in `audit_service.py`
- Constitution Principle II: never auto-advance through `interrupt()` — always require explicit PO API call
- All sandbox file operations must validate path prefix (Constitution Principle VI)
