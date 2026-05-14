# TC-08 — Thought stream event latency (≤ 2 s)

**Spec Kit:** T112  
**Related:** `tasks.md` (Phase 20 / US10), `contracts/websocket-protocol.md`

## Criterion

With a task **in progress**, stream events MUST appear in the browser within **2 seconds** of the corresponding agent publish (per `tasks.md` independent test for US10).

This document records **how** to validate that using Chrome DevTools, what the server path is, and the **outcome** of the checks performed for T112.

## Server publish path (coder → browser)

1. `coder_node` calls `_publish_event` → `EventPublisher.publish` (`backend/app/agent/nodes/coder_node.py`, `backend/app/websocket/event_publisher.py`).
2. Event is persisted to `stream_events`, then `PUBLISH` to Redis channel `task:{task_id}:events`.
3. WebSocket handler `_pump_redis` consumes via `EventConsumer.consume` and `send_text` to the client (`backend/app/websocket/ws_handler.py`, `backend/app/websocket/event_consumer.py`).
4. Frontend `TaskThoughtStreamClient` receives frames and `useThoughtStream` / `ThoughtStreamPanel` render them (`frontend/src/services/websocket-client.ts`, `frontend/src/hooks/use-thought-stream.ts`).

Code review (2026-05-13): this path has **no intentional delay** of 2 s or more; relay is bounded by DB flush, Redis pub/sub, and the WS pump. Under **localhost** API + Redis, typical end-to-end latency is expected to be **well under 2 s** unless the host is overloaded or the network path is high-latency.

## Manual measurement — Chrome WebSocket inspector

**Preconditions**

- Backend and Redis running; user logged in; JWT available.
- A task in **`in_progress`** with an active coder run so that `TOOL_CALL` / `THOUGHT` / etc. events are emitted.

**Steps**

1. Open the project workspace, start the thought stream (FAB / panel) so the WebSocket connects to `ws://…/ws/tasks/{task_id}/stream?token=…`.
2. Open **DevTools → Network → WS**, select the `stream` connection.
3. Open the **Messages** tab (Chrome shows a time column per frame).
4. Trigger or wait for the next agent step that causes `coder_node` to publish (e.g. a tool round).
5. For one event:
   - Note the **message receive time** in DevTools (wall-clock / relative as shown).
   - Compare with server **ISO `timestamp`** in the JSON payload (`contracts/websocket-protocol.md` base envelope) using the same wall clock if possible, or compare **delta between consecutive events** against expected agent pacing.
6. **Pass** if the observed delay from “publish effective” to “frame visible in Messages” is **≤ 2000 ms** under normal dev conditions.

**Tip:** Each stream event JSON includes `"timestamp"` (UTC ISO). You can paste the payload into a scratch pad and compare `Date.parse(timestamp)` to `Date.now()` at the moment you observe the frame (small clock skew is normal; large skew suggests NTP issues).

## Recorded results (T112)

| Check | Result | Notes |
|--------|--------|--------|
| Code path review (publish → Redis → WS → client) | **PASS** | No ≥ 2 s sleeps or batching delays on the hot path. |
| Manual E2E (DevTools, localhost) | **Recommended at release gate** | Run the steps above on a real agent run; record max observed latency (ms) and environment below. |

**Optional sign-off row (fill when manual E2E is run):**

| Date | Environment | Max observed latency (ms) | Pass (≤ 2000 ms) |
|------|-------------|---------------------------|------------------|
| | | | |

## References

- `specs/001-neo-kanban/tasks.md` — US10 independent test (2 s, sequence, CATCH_UP).
- `specs/001-neo-kanban/contracts/websocket-protocol.md` — endpoint, envelope, event types.
