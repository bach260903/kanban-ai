# Research: Neo-Kanban — RTK Token Optimizer + Constitution Tab

**Phase 0 Output** | Date: 2026-05-17 | Plan: [plan.md](plan.md)
**Implementation status**: ✅ Implemented 2026-05-18 — `token_optimizer.py` (9 public functions), patched `file_tools.py`, `sandbox_tools.py`, `context_builder.py`; Constitution tab added to workspace (5th tab in `project-workspace.tsx`)

---

## 1. RTK-AI/RTK — Core Technology Analysis

**Source**: github.com/rtk-ai/rtk — CLI proxy, 60-90% LLM token reduction on dev commands.

### 1.1 Architecture

| Aspect | Detail |
|---|---|
| Implementation | Single Rust binary, zero runtime dependencies |
| Integration point | CLI proxy layer between agent tools and shell output |
| Storage | `~/.local/share/rtk/tee/` — full output saved on failure for fallback |
| Config | `~/.config/rtk/config.toml` with `[hooks]` and `[tee]` sections |

RTK intercepts shell output **before** it reaches the LLM context window and applies four transformations. For this project we implement the same transformations in Python inside the agent tool pipeline.

### 1.2 The Four Core Techniques

#### A. Smart Filtering
Removes content that LLMs don't need: comments, excessive whitespace, boilerplate headers, binary content markers, progress bars, ANSI codes.

**Applied to**: `read_file` output, `run_command` stdout/stderr, MEMORY.md injection.

#### B. Grouping
Aggregates related items into structured summaries instead of flat lists:
- File listings → directory tree with file counts per folder
- Test failures → grouped by test suite / file
- Lint errors → grouped by rule name or file

**Applied to**: `list_files` output (flat list → tree), `run_command` for test/lint output.

#### C. Truncation
Keeps contextually important lines (head + tail pattern), discards middle redundancy. Preserves first N lines (imports, setup) and last M lines (errors, results).

**Applied to**: `read_file` for large files (>500 lines), `run_command` stdout when verbose.

#### D. Deduplication
Collapses repeated identical lines into `× N` counters. Example:
```
[INFO] Processing file...   (×47)
```
**Applied to**: `run_command` log-heavy output (servers, migrations, docker).

### 1.3 Command-Specific Transformations

| Command Category | RTK Technique | Token Saving |
|---|---|---|
| `ls` / `list_files` | Flat list → hierarchical tree | ~80% |
| `pytest` / `jest` / `go test` | Failures-only + summary line | ~90% |
| `git status` | Staged/unstaged counts, branch info | ~75% |
| `git log` | One-line format with author+date | ~85% |
| `git diff` | Keep only `+`/`-` lines + file headers | ~70% |
| `tsc` / `eslint` / `ruff` | Group errors by file, dedupe rule | ~80% |
| `docker logs` | Deduplicate + last 50 lines | ~85% |
| `cat` large file | head+tail with skip notice | ~60% |

### 1.4 Implementation Decision for Neo-Kanban

**Decision**: Implement RTK techniques as a pure-Python module `backend/app/tools/token_optimizer.py` — no external binary dependency.

**Rationale**:
- The project uses `sandbox_tools.py` (Python asyncio subprocess) and `file_tools.py` — injection points are clear.
- Avoids binary dependency on a Rust binary in the Docker/CI pipeline.
- The four RTK techniques are straightforward to implement in Python with `re` and `pathlib`.

**Alternatives considered**:
- Shell to RTK binary: rejected — adds Rust toolchain as a hard dependency; fragile on Windows dev env.
- LangChain output parser: rejected — would require changing tool signatures; token_optimizer.py is a thin utility layer that can be inserted without altering the tool API.

---

## 2. Constitution Tab — Gap Analysis

### 2.1 Implementation Status

| Item | Status |
|---|---|
| Constitution data model | ✅ `projects.constitution TEXT` column |
| API endpoints | ✅ `GET/PUT /api/v1/projects/{id}/constitution` |
| Editor page | ✅ `frontend/src/pages/constitution-editor.tsx` (Monaco + save) |
| Navigation to editor | ✅ Standalone route `/projects/:id/constitution` still exists |
| Workspace tab | ✅ **Implemented 2026-05-18** — 5th tab "Constitution" in `project-workspace.tsx` |
| Constitution organism | ✅ `frontend/src/components/organisms/constitution-panel.tsx` — Monaco + dirty indicator + save/load |
| CSS module | ✅ `frontend/src/components/organisms/constitution-panel.module.css` |

### 2.2 Implementation Decision (Resolved)

Added a 5th **"Constitution"** tab to `project-workspace.tsx`. Logic extracted into `constitution-panel.tsx` organism so it can be embedded without full-page navigation.

**Decision**: Created `frontend/src/components/organisms/constitution-panel.tsx` — self-contained, reuses `getConstitution` / `updateConstitution` from `project-api.ts`. Standalone editor page untouched.

**Rationale**: Zero new API calls, zero new state management. Dirty detection via `content !== savedContent` guards accidental navigation away.

---

## 3. RTK Optimizer — Implementation Details (2026-05-18)

### 3.1 Public API (`backend/app/tools/token_optimizer.py`)

All 9 functions are pure (no I/O, no async):

| Function | Technique | Output |
|---|---|---|
| `optimize_list_output(paths)` | Grouping | Directory tree with per-dir file counts |
| `optimize_file_content(content, max_lines=500)` | Truncation + Filtering | ANSI stripped, blank lines collapsed, head+tail |
| `optimize_command_output(cmd, stdout, stderr, exit_code)` | Routing | Dispatches to specialised handler, always prepends `exit_code: N` |
| `filter_test_output(output)` | Filtering | FAILED/ERROR/Traceback lines + last summary line |
| `compress_git_diff(diff)` | Filtering | Strips space-prefix context lines; keeps `+/-/@@/---/+++` |
| `compress_git_log(log)` | Truncation | One line per commit: hash(7) · author · date · subject |
| `compress_git_status(status)` | Grouping | Branch line + staged/unstaged/untracked counts |
| `group_build_errors(output)` | Grouping | Errors grouped by file path (TypeScript + ruff/flake8 patterns) |
| `deduplicate_lines(text, threshold=3)` | Deduplication | Consecutive identical lines → `line × N` |

### 3.2 Integration Points

| File patched | What changed |
|---|---|
| `file_tools.py` | `read_file` → `optimize_file_content(raw)`; `list_files` return type `list[str]` → `str` via `optimize_list_output` |
| `sandbox_tools.py` | Final `return f"exit_code: ..."` → `optimize_command_output(...)`; `RTK_OPTIMIZER_DISABLED` env-var escape hatch added |
| `context_builder.py` | MEMORY.md injected via `optimize_file_content(mem_txt, max_lines=300)` before char-limit truncation; constitution block via `deduplicate_lines(constitution)` |

### 3.3 Resolved Technical Context

| Question | Resolution |
|---|---|
| RTK binary dependency? | Not needed — all 9 techniques implemented in Python stdlib only (`re`, `collections`) |
| New DB tables for optimizer? | No — pure processing layer, no persistence |
| New API endpoints? | No — constitution uses existing `GET/PUT /api/v1/projects/{id}/constitution` |
| Monaco available in workspace? | Yes — `@monaco-editor/react` already in `document-editor.tsx` |
| CSS module convention? | kebab-case `.module.css` per Constitution Principle VIII |
| `list_files` return type change breaks callers? | Verified — only agent nodes consume this; tool description updated |
