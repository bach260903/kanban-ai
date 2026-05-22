# Implementation Plan: AI CLI Integration — Vibe Coding Backends

**Branch**: `004-ai-cli-integration` | **Date**: 2026-05-18 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/002-ai-cli-integration/spec.md`  
**Prerequisites**: Feature 001 (Neo-Kanban core) fully complete

---

## Summary

Extends Neo-Kanban's Coder Agent to support three additional AI coding backends alongside the
existing Groq + LangGraph approach. Project Owners can select which AI CLI ("vibe coding" engine)
runs their tasks: Claude Code CLI, OpenAI SDK, or Gemini CLI. The backend is stored per-project
and can be changed at any time.

**Architectural approach**:
- `claude_code` and `gemini` → new `CLICoderRunner` (subprocess, streaming stdout to WebSocket)
- `openai` → swap `ChatGroq` → `ChatOpenAI` inside existing `coder_node` ReAct loop
- `groq` → unchanged (default)
- Conditional graph routing dispatches to the right node based on `project.coding_backend`

---

## Technical Context

**Language/Version**: Python 3.11 (backend) · TypeScript 5.6 + React 18 (frontend)  
**New Dependencies**: `langchain-openai>=0.3.0` (OpenAI backend only)  
**No new DB tables** — one new column on `projects`  
**No new API prefix** — extends `/api/v1`  
**CLI tools** (external, must be installed in server env):
- Claude Code: `claude` binary from `@anthropic-ai/claude-code`
- Gemini: `gemini` binary from `@google/gemini-cli`
- OpenAI: Python SDK only (no binary)

---

## Constitution Check

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Artifact communication | ✅ PASS | CLI output → stream_events table; diff → diffs table; no shared session |
| II | HIL checkpoints | ✅ PASS | CLICoderRunner calls `interrupt()` after completing, same as coder_node |
| III | WIP = 1 | ✅ PASS | WIP enforcement unchanged — in kanban_service, not in coder logic |
| IV | Kanban one-way flow | ✅ PASS | Task transitions unchanged |
| V | Full audit logging | ✅ PASS | `audit_service.write_pending_log()` called before CLI invocation |
| VI | Security | ✅ PASS | API keys in env (never DB); CLI runs in isolated sandbox dir; no new network exposure |
| VII | MVP scope | ✅ PASS | Single-user, local sandbox; CLI selection is additive, not a scope change |
| VIII | Code quality | ✅ PASS | PEP 8 + type hints; new component follows existing patterns |

**Gate result: ALL PASS**

---

## Project Structure Changes

```
backend/
├── alembic/versions/
│   └── 004_add_coding_backend.py          ← NEW migration
├── app/
│   ├── config.py                          ← MODIFIED: add OPENAI_*, GOOGLE_AI_*, CLI paths
│   ├── models/
│   │   └── project.py                     ← MODIFIED: add CodingBackend enum + column
│   ├── schemas/
│   │   └── project.py                     ← MODIFIED: add coding_backend field
│   ├── agent/
│   │   ├── graph.py                       ← MODIFIED: add conditional routing + cli_coder_node
│   │   ├── state.py                       ← MODIFIED: add coding_backend field
│   │   └── nodes/
│   │       └── cli_coder_node.py          ← NEW: CLICoderRunner for Claude Code + Gemini
│   └── api/v1/
│       ├── projects.py                    ← MODIFIED: accept + return coding_backend
│       └── backends.py                    ← NEW: GET /backends/available
├── requirements.txt                       ← MODIFIED: add langchain-openai

frontend/
├── src/
│   ├── types/index.ts                     ← MODIFIED: add coding_backend to Project type
│   ├── services/project-api.ts           ← MODIFIED: include coding_backend in payloads
│   ├── components/
│   │   ├── atoms/
│   │   │   └── backend-badge.tsx          ← NEW: coloured badge for backend name
│   │   └── molecules/
│   │       └── backend-selector.tsx       ← NEW: dropdown to choose backend
│   ├── pages/
│   │   └── project-list.tsx              ← MODIFIED: add backend field to create form
│   └── components/organisms/
│       └── project-header.tsx            ← MODIFIED: show backend badge
```

---

## Phase 1: Setup & Migration

**Purpose**: DB migration, config, ORM, schema — no user-visible change.

- [ ] T001 Write Alembic migration `004_add_coding_backend.py`: `ALTER TABLE projects ADD COLUMN coding_backend VARCHAR(20) NOT NULL DEFAULT 'groq' CHECK (...)`. Down migration: `DROP COLUMN coding_backend`.
- [ ] T002 [P] Update `CodingBackend` enum in `backend/app/models/project.py`: add `CodingBackend(str, enum.Enum)` with values `groq`, `claude_code`, `openai`, `gemini`; add `coding_backend: Mapped[CodingBackend]` column with default.
- [ ] T003 [P] Update `backend/app/config.py`: add `openai_api_key: str | None`, `openai_model: str = "gpt-4o-mini"`, `openai_base_url: str | None`, `google_ai_api_key: str | None`, `gemini_model: str = "gemini-2.0-flash"`, `claude_code_path: str = "claude"`, `gemini_cli_path: str = "gemini"`.
- [ ] T004 [P] Update `backend/.env.example`: add `OPENAI_API_KEY=`, `OPENAI_MODEL=gpt-4o-mini`, `GOOGLE_AI_API_KEY=`, `GEMINI_MODEL=gemini-2.0-flash`, `CLAUDE_CODE_PATH=claude`, `GEMINI_CLI_PATH=gemini`.
- [ ] T005 Update Pydantic schemas in `backend/app/schemas/project.py`: add `coding_backend: CodingBackend = CodingBackend.groq` to `ProjectCreate` and `ProjectUpdate`; add `coding_backend: CodingBackend` to `ProjectResponse`.
- [ ] T006 Add `langchain-openai>=0.3.0` to `backend/requirements.txt`.

**Checkpoint**: `alembic upgrade head` succeeds; `projects` table has `coding_backend` column; `GET /projects` returns `coding_backend` field.

---

## Phase 2: Backend — CLICoderRunner

**Purpose**: Implement the new CLI subprocess runner and OpenAI provider swap.

- [ ] T007 Implement `backend/app/agent/nodes/cli_coder_node.py`:
  - `async def run(state: AgentState) -> AgentState`
  - Reads `state["coding_backend"]` to pick `claude_code` or `gemini`
  - Builds prompt via `ContextBuilder.build_coder_context()`
  - `claude_code`: `f"{settings.claude_code_path} --print -p {shlex.quote(prompt)}"` with `ANTHROPIC_API_KEY` env
  - `gemini`: `f"{settings.gemini_cli_path} -p {shlex.quote(prompt)}"` with `GOOGLE_AI_API_KEY` env
  - Streams stdout lines as `THOUGHT` events via `event_publisher.publish()`
  - Streams stderr lines as `ACTION` events
  - `asyncio.wait_for(proc.wait(), timeout=600.0)` — on timeout: move task to `rejected`, publish `ERROR`, write audit log
  - On exit code ≠ 0: publish `ERROR` event with `CLI_AUTH_ERROR` or `CLI_NOT_FOUND` code; move task to `rejected`
  - On success: call `GitService.diff()` → save `Diff` record → call `interrupt()`
  - BẮTBUỘC (Principle V): `audit_service.write_pending_log()` BEFORE CLI invocation; `audit_service.finalise_log()` after
- [ ] T008 [P] Patch `coder_node` for OpenAI backend: in `backend/app/agent/nodes/coder_node.py`, check `state["coding_backend"]`; if `openai`, instantiate `ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key)` instead of `ChatGroq`. No other changes to the ReAct loop.
- [ ] T009 Update `backend/app/agent/state.py`: add `coding_backend: str` field to `AgentState` TypedDict.
- [ ] T010 Update `backend/app/agent/graph.py`:
  - Import `cli_coder_node`
  - Add `cli_coder_node` as a graph node
  - Add conditional routing function `route_coder(state)`: returns `"cli_coder_node"` if `coding_backend in ("claude_code", "gemini")`, else `"coder_node"`
  - Add conditional edge from the trigger point to `route_coder`
  - Propagate `coding_backend` into state when launching from `kanban_service`
- [ ] T011 Update `backend/app/services/kanban_service.py`: when dispatching Coder Agent background task on `todo → in_progress`, load `project.coding_backend` from DB and pass it into the initial `AgentState`.
- [ ] T012 Implement `GET /api/v1/backends/available` endpoint in `backend/app/api/v1/backends.py`: check presence of `settings.openai_api_key`, `settings.google_ai_api_key`, `settings.groq_api_key`, and CLI binary existence for `claude_code` / `gemini`; return `{available: [...], unavailable: [...]}`. Register router in `main.py`.

**Checkpoint**: With `coding_backend = claude_code` and valid `ANTHROPIC_API_KEY`: drag task to In Progress → `claude --print` invoked in sandbox → stdout appears as THOUGHT events → diff generated → task moves to Review.

---

## Phase 3: Backend — Projects API

**Purpose**: Accept and return `coding_backend` in project endpoints.

- [ ] T013 Update `backend/app/api/v1/projects.py`:
  - `POST /projects`: pass `coding_backend` from schema to `ProjectService.create()`
  - `PUT /projects/{id}`: pass `coding_backend` from update schema to `ProjectService.update()`
  - All responses include `coding_backend`
- [ ] T014 Update `backend/app/services/project_service.py`: `create()` and `update()` accept and persist `coding_backend`.

**Checkpoint**: `POST /projects` with `coding_backend=openai` returns project with that field; `PUT /projects/{id}` changes backend; `GET /projects/{id}` returns updated value.

---

## Phase 4: Frontend

**Purpose**: Backend selector in project creation + badge in header.

- [ ] T015 [P] Update `frontend/src/types/index.ts`: add `coding_backend: 'groq' | 'claude_code' | 'openai' | 'gemini'` to `Project` and `ProjectListItem` types.
- [ ] T016 [P] Create `frontend/src/components/atoms/backend-badge.tsx`: pill badge showing backend name with colour coding:
  - `groq` → grey
  - `claude_code` → amber (`Claude Code`)
  - `openai` → green (`OpenAI`)
  - `gemini` → blue (`Gemini`)
- [ ] T017 [P] Create `frontend/src/components/molecules/backend-selector.tsx`: `<select>` dropdown with four options; calls `GET /backends/available` on mount to disable unavailable backends with a tooltip "Not configured".
- [ ] T018 Update `frontend/src/services/project-api.ts`: include `coding_backend` in `ProjectCreatePayload` (optional, default omitted = server uses `groq`) and `ProjectUpdatePayload`.
- [ ] T019 Update `frontend/src/pages/project-list.tsx`: add `BackendSelector` to the inline create-project form; pass selected value to `createProject()`.
- [ ] T020 Update `frontend/src/components/organisms/project-header.tsx`: render `BackendBadge` next to the language badge, using `project.coding_backend`.

**Checkpoint**: Create project → choose "Claude Code" in form → Project header shows "Claude Code" badge; update project backend via settings → badge updates.

---

## Phase 5: Hardening & Tests

- [ ] T021 [P] Write `backend/tests/unit/test_cli_coder_node.py`: mock `asyncio.create_subprocess_shell` — test timeout → rejected status; test exit code ≠ 0 → CLI_NOT_FOUND error; test success → Diff saved + interrupt called.
- [ ] T022 [P] Write `backend/tests/unit/test_backend_routing.py`: test `route_coder()` returns correct node for each backend value; test `AgentState` carries `coding_backend`.
- [ ] T023 Write integration test `backend/tests/integration/test_backend_switch.py`: create project with `groq`, switch to `openai` via PUT, verify field updated; verify `GET /backends/available` lists configured backends.
- [ ] T024 Validate TC-01 (CLI overhead ≤ 500 ms): time from drag event to subprocess start using audit log timestamps.
- [ ] T025 [P] Validate TC-03 (timeout = 10 min): unit test with mocked subprocess that never exits.

---

## Dependencies & Execution Order

```
Phase 1 (Setup) ─────────────────────────────► BLOCKS all other phases
Phase 2 (CLICoderRunner + graph) ────────────► BLOCKS Phase 3 (API propagates coding_backend)
Phase 3 (API) ───────────────────────────────► BLOCKS Phase 4 (frontend needs field)
Phase 4 (Frontend) ─────────────────────────►
Phase 5 (Tests) ─────────────────────────────► can start after Phase 2

T001 → T002, T003, T004, T005, T006 [P]
T007, T008 [P] → T009 → T010 → T011 → T012
T013 → T014
T015, T016, T017, T018 [P] → T019 → T020
```

---

## Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Claude Code CLI `--print` mode not available in older versions | Medium | High | Pin minimum version in install docs; check with `claude --version` at startup |
| Gemini CLI interface changes (Google alpha software) | Medium | Medium | Wrap in CLICoderRunner abstraction — easy to update cmd template |
| OpenAI SDK version conflicts with existing langchain | Low | Medium | Pin `langchain-openai>=0.3.0,<0.4` |
| CLI output format differs from Groq ReAct → diffs harder to generate | Low | High | CLICoderRunner uses `git diff HEAD` after exit — format-independent |
| `shlex.quote(prompt)` edge cases with Unicode | Low | Low | pytest fixture with Vietnamese task descriptions |

---

## Post-Design Constitution Re-Check

| # | Principle | Evidence |
|---|-----------|----------|
| I | Artifact communication | CLI output written to stream_events + files in sandbox; no shared session |
| II | HIL checkpoints | `interrupt()` called after CLI completes — same gate as Groq path |
| III | WIP = 1 | Enforcement in kanban_service unchanged |
| IV | One-way flow | Unchanged |
| V | Audit logging | `write_pending_log()` before CLI invocation per Principle V |
| VI | Security | API keys stay server-side; CLI runs in sandbox; `shlex.quote()` prevents injection |
| VII | MVP scope | Additive feature; single-user; local sandbox |
| VIII | Code quality | PEP 8 + type hints; `cli_coder_node.py` follows same pattern as `coder_node.py` |

**Post-design gate: ALL PASS**
