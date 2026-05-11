# Research: Neo-Kanban Implementation Plan

**Phase**: 0 — Research & Decisions
**Date**: 2026-05-11
**Branch**: `003-core-kanban-flow`

All "NEEDS CLARIFICATION" items from Technical Context are resolved below.
Each decision includes rationale and the alternatives considered.

---

## D-01: LangGraph HIL Pattern — How to suspend a running agent and wait for PO action

**Decision**: Use LangGraph's built-in `interrupt()` primitive inside graph nodes combined with
a PostgreSQL-backed `SqliteSaver` / `AsyncPostgresSaver` checkpointer. The graph is resumed by
calling `graph.ainvoke(None, config={"configurable": {"thread_id": agent_run_id}})` from the
FastAPI approval endpoint after writing the PO decision to DB.

**Rationale**: LangGraph 0.2+ has first-class support for human-in-the-loop via `interrupt()`.
The checkpointer serialises full graph state to DB, so the process can be restarted without
losing context. This is the recommended pattern in the LangGraph documentation and aligns with
Constitution Principle II (HIL checkpoints).

**Alternatives considered**:
- `asyncio.Event` — process-local only, lost on restart. Rejected.
- Separate "poll for approval" loop in the agent — creates busy-wait and complicates audit trail.
  Rejected.
- Celery task suspension — adds Celery as a dependency; overkill for single-worker MVP. Rejected.

**Action required**: Use `langgraph-checkpoint-postgres` package and run LangGraph `ainvoke` in a
background asyncio task (not blocking the FastAPI event loop). On `interrupt()`, the task saves
state and exits. The approval endpoint restarts it.

---

## D-02: WIP = 1 Enforcement — Race condition between concurrent drag events

**Decision**: Enforce WIP = 1 at two layers:
1. **PostgreSQL** — `EXCLUDE USING btree (project_id WITH =) WHERE (status = 'in_progress')` on
   the `tasks` table. This makes the constraint atomic at the database level.
2. **Service layer** — `task_service.move()` does an explicit SELECT count check before the
   UPDATE, returning a 409 Conflict HTTP response before the DB constraint fires (better UX).

**Rationale**: Database-level constraint is the safety net; service-level check provides the
correct error message. Neither alone is sufficient — the constraint alone gives a cryptic DB
error; the service check alone has a TOCTOU race window.

**Alternatives considered**:
- Application-level mutex — not viable in multi-process deployment. Rejected.
- Redis distributed lock — adds complexity for a constraint that PostgreSQL handles natively.
  Rejected.

---

## D-03: Sandbox Security — Preventing file-system escape

**Decision**: The Coder Agent's `write_file` and `read_file` tools validate that the resolved
absolute path starts with the project's sandbox root (`/tmp/neo-kanban/{project_id}/`). Any path
traversal attempt (e.g., `../../etc/passwd`) raises a `SandboxEscapeError` which is caught by
`error_handlers.py` and returned as HTTP 400. The sandbox directory has no execute permission
for network binaries.

**Rationale**: Constitution Principle VI mandates sandbox isolation. Local tmp directory is the
MVP sandbox; Docker is deferred. Path validation is the minimum viable isolation.

**Alternatives considered**:
- `chroot` jail — requires root privileges on the host; not suitable for dev laptops. Rejected.
- Docker SDK — explicitly deferred to post-MVP by Constitution Principle VII. Rejected.
- `seccomp` profile — too complex for MVP; noted for future hardening. Deferred.

---

## D-04: Monaco Diff Format — Converting git unified diff to Monaco's diff model

**Decision**: Use Monaco's `createDiffEditor` with two `ITextModel` objects (original and
modified). Convert the git unified diff to two full-text strings (original file content and
modified file content) by applying the diff patch using Python's `whatthepatch` library server-side.
The API returns `{ original: string, modified: string }` and the frontend passes them to Monaco.

**Rationale**: Monaco `DiffEditor` requires full text models, not patch strings. The conversion
is straightforward and deterministic. Doing it server-side keeps the frontend simple.

**Alternatives considered**:
- Parse unified diff in the browser — more complex JS, harder to test. Rejected.
- Use `diff2html` library — outputs HTML, not Monaco models. Rejected.
- Store both original and modified file content in the `diffs` table — adds storage overhead but
  makes the API simpler. **Adopted as a pragmatic trade-off**.

**Action required**: Add `whatthepatch==1.0.6` to `requirements.txt`. Store `original_content`
and `modified_content` columns alongside `content` (unified diff) in the `diffs` table for fast
retrieval.

---

## D-05: LangGraph Running Without Blocking FastAPI Event Loop

**Decision**: Use `asyncio.create_task()` to run the LangGraph graph as a background async task.
FastAPI returns the `agent_run_id` immediately (HTTP 202 Accepted). The PO polls
`GET /agent-runs/{run_id}` or observes the WebSocket stream (Phase 2) to see progress.

**Rationale**: LangGraph `ainvoke` can run for minutes. Blocking the request would hold an HTTP
connection and a Uvicorn worker. Background task is the idiomatic FastAPI pattern for long-running
operations.

**Alternatives considered**:
- Celery worker queue — operational overhead not justified for single-user MVP. Deferred.
- `BackgroundTasks` (FastAPI built-in) — does not support `interrupt()`/resume across requests.
  Rejected.
- Separate agent process via subprocess — inter-process state sharing is complex. Rejected.

---

## D-06: Pause Signal — Async-safe across multiple Uvicorn workers

**Decision**: Store the pause flag as a Redis key: `SET pause:{task_id} 1` (with no expiry; TTL
managed manually on resume). Each LangGraph node checks `await redis.exists(f"pause:{task_id}")`
at its entry point. If the key exists, the node raises `PauseSignal` which is caught by the graph
runner and transitions to `awaiting_hil` state.

**Rationale**: Redis SET/GET is atomic and process-independent. Even if Uvicorn is restarted or
runs multiple workers, the pause state is correctly shared. This satisfies the spec note
"Pause signal phải là async-safe (không block event loop FastAPI)".

**Alternatives considered**:
- `asyncio.Event` — process-local, lost on restart. Rejected.
- DB row flag — polling DB on every node step adds latency and DB load. Rejected.
- LangGraph's own interrupt mechanism — designed for HIL, not for mid-flight pause from a
  separate HTTP endpoint. The two mechanisms work differently; Redis flag is cleaner here.

---

## D-07: tree-sitter Integration — Language binding installation

**Decision**: Use `tree-sitter==0.23.0` with pre-built wheel packages:
- `tree-sitter-python==0.23.2`
- `tree-sitter-javascript==0.23.0`
- `tree-sitter-typescript==0.23.0`

These wheels include precompiled grammar `.so` files and do not require a C compiler at install
time. A simple version pin matrix is tested in CI.

**Rationale**: tree-sitter is the only mature parser library that supports incremental parsing
and symbol extraction for both Python and JS/TS in a single dependency. Pre-built wheels avoid
the C-compilation step that has historically caused CI failures.

**Alternatives considered**:
- `ast` module (Python only) — does not cover JavaScript/TypeScript. Rejected.
- `jedi` + `eslint-plugin-jsdoc` — separate tools per language, harder to unify output schema.
  Rejected.
- LSP-based symbol extraction — requires running a full language server; too heavy for a
  background scan. Rejected.

**Risk**: tree-sitter grammar API changed significantly between 0.21 and 0.23. Pinning exact
versions is mandatory.

---

## D-08: WebSocket Reconnection Strategy

**Decision**: Assign each event a monotonically increasing `sequence_number` scoped to
`(task_id)`. Events are persisted to the `stream_events` table before being published to Redis.
When a client reconnects, it sends `{"type": "CATCH_UP", "last_sequence": N}`. The server queries
`stream_events WHERE task_id = X AND sequence_number > N` and replays missed events before
resuming the live Redis subscription.

**Rationale**: Persisting events to DB before publishing ensures no event is ever lost even if
the Redis connection drops. The `CATCH_UP` mechanism is simpler than maintaining an in-memory
ring buffer and works across process restarts.

**Alternatives considered**:
- Redis Streams (`XADD` / `XREAD`) — provides persistence within Redis but adds operational
  complexity (stream trimming, consumer groups). PostgreSQL already handles persistence. Rejected.
- SSE (Server-Sent Events) instead of WebSocket — SSE is unidirectional (no PAUSE/RESUME from
  client); rejected because the spec requires bidirectional control.

---

## D-09: Inline Comment Line Mapping — Stability after squash/rebase

**Decision**: Inline comments store positions as unified diff hunk positions
(`file_path`, `diff_line_number` within the diff object). They are NOT stored as absolute file
line numbers. When the Agent receives the reject feedback, it receives the diff content alongside
the comments, so it can locate the correct region without needing to know the absolute line number
in the current file.

**Rationale**: Absolute line numbers drift after any rebase or squash. Diff-relative positions
are stable within the scope of a single review cycle (one diff object, one review decision).

**Alternatives considered**:
- Store absolute file line numbers — drift after squash; PO feedback becomes inaccurate. Rejected.
- Use Git blame to correlate — complex, fragile for new files. Rejected.

**Trade-off**: If the PO rejects and the Agent modifies the file, the next diff is a new diff
object. Comments from the previous diff are historical only. This is acceptable per the spec
(inline comments apply to the current diff under review).

---

## D-10: MEMORY.md Concurrency — Preventing write conflicts

**Decision**: Agent writes to `memory_entries` table (INSERT only, never UPDATE). PO edits use
`SELECT FOR UPDATE` on the specific row then UPDATE. The `MEMORY.md` file is regenerated from
the DB as a read artifact each time the Agent context is assembled — it is not a write target
during Agent execution. This means there is no concurrent file-write contention.

**Rationale**: Separating the DB (source of truth) from the file (read artifact) eliminates the
race condition described in the spec's edge case ("PO editing MEMORY.md while Agent writes").

**Alternatives considered**:
- File lock (`fcntl.flock`) — process-local; fails with multiple workers. Rejected.
- Optimistic locking with `updated_at` version check — workable but adds round-trips. The DB row
  SELECT FOR UPDATE pattern is simpler and equally correct.
