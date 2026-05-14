# WebSocket Protocol Contract: Neo-Kanban Thought Stream

**Endpoint**: `ws://localhost:8000/ws/tasks/{task_id}/stream`
**Auth**: Pass JWT as query param: `?token=<jwt_token>` (WebSocket does not support custom headers in browsers)
**Phase**: 2

---

## Connection Lifecycle

```
Client                          Server
  │                               │
  │──── WS connect ──────────────►│  authenticate JWT from ?token=
  │                               │  look up task, verify status = in_progress
  │                               │
  │◄─── {"type":"CONNECTED"} ────│
  │                               │
  │  [optional: send CATCH_UP]    │
  │──── {"type":"CATCH_UP",...} ─►│  replay missed events from DB
  │◄─── event stream ────────────│
  │◄─── event stream ────────────│
  │                               │
  │  [optionally: send PAUSE]     │
  │──── {"type":"PAUSE"} ────────►│  sets Redis key pause:{task_id}
  │                               │  agent stops at next node entry
  │◄─── {"event_type":"STATUS_CHANGE",...,"content":{"from":"CODING","to":"PAUSED"}} ─┤
  │                               │
  │──── {"type":"RESUME",...} ───►│  clears Redis key, passes steering instructions
  │◄─── event stream resumes ────│
  │                               │
  │◄─── {"event_type":"STATUS_CHANGE",...,"content":{"from":"CODING","to":"REVIEWING"}} ─┤
  │                               │  (task complete; stream ends)
  │◄─── {"type":"STREAM_END"} ──│
  │                               │
  │── WS close ──────────────────►│
```

---

## Server → Client Messages

All server-to-client messages are JSON objects. All event messages share the base envelope.

### Base Envelope (all stream events)

```jsonc
{
  "event_type": string,       // one of the 6 event types
  "sequence_number": number,  // monotonically increasing, scoped to task_id
  "timestamp": string,        // ISO 8601 UTC, e.g., "2026-05-11T10:30:00.123Z"
  "task_id": string,          // UUID
  "agent_run_id": string,     // UUID
  "content": object           // see per-type schemas below
}
```

### `THOUGHT`

Agent's internal reasoning step. Not a tool call; no side effects.

```jsonc
{
  "event_type": "THOUGHT",
  "content": {
    "reasoning": "I need to check whether the user model already has a verify_password method before writing a new one."
  }
}
```

### `TOOL_CALL`

Agent is about to invoke a tool. Published **before** the tool runs.

```jsonc
{
  "event_type": "TOOL_CALL",
  "content": {
    "tool_name": "read_file",          // e.g., "read_file", "write_file", "list_files", "run_command"
    "call_id": "tc-001",               // unique within this agent run
    "arguments": {
      "path": "src/models/user.py"     // tool-specific arguments
    }
  }
}
```

### `TOOL_RESULT`

Result returned by a tool. Published **after** the tool completes.

```jsonc
{
  "event_type": "TOOL_RESULT",
  "content": {
    "tool_name": "read_file",
    "call_id": "tc-001",               // matches the originating TOOL_CALL
    "success": true,
    "result": "class User:\n    ...",  // truncated to 2000 chars for display
    "result_truncated": false          // true if result was truncated
  }
}
```

### `ACTION`

A side-effecting action (file write, git operation, sandbox command). Published **after** the action
is logged to `audit_logs` and **before** execution.

```jsonc
{
  "event_type": "ACTION",
  "content": {
    "action_type": "write_file",       // "write_file" | "run_command" | "git_commit" | "git_branch"
    "description": "Writing updated user model with verify_password method",
    "target": "src/models/user.py",    // file path, branch name, or command preview
    "audit_log_id": "uuid"             // ID of the pre-written audit_log entry
  }
}
```

### `ERROR`

An error occurred during agent execution.

```jsonc
{
  "event_type": "ERROR",
  "content": {
    "error_type": "SandboxEscapeError",   // exception class name
    "message": "Attempted path traversal: ../../etc/passwd",
    "recoverable": false,                  // if false, agent will transition to failure state
    "step": "CODING"                       // which LangGraph node raised the error
  }
}
```

### `STATUS_CHANGE`

LangGraph state machine transitioned to a new node.

```jsonc
{
  "event_type": "STATUS_CHANGE",
  "content": {
    "from": "CODING",                 // previous state name
    "to": "REVIEWING",                // new state name
    "reason": "Agent completed implementation; diff stored."
  }
}
```

---

### Control Messages (server → client, not stream events)

These are not persisted to `stream_events`; they are connection-management signals.

#### `CONNECTED`

Sent immediately after the WebSocket connection is accepted.

```jsonc
{
  "type": "CONNECTED",
  "task_id": "uuid",
  "agent_run_id": "uuid",
  "latest_sequence": 41              // highest sequence_number in DB; client can send CATCH_UP if needed
}
```

#### `STREAM_END`

Sent when the agent's run is complete (success, failure, or task moved to `review`).

```jsonc
{
  "type": "STREAM_END",
  "task_id": "uuid",
  "final_status": "success",         // "success" | "failure" | "awaiting_hil"
  "event_count": {
    "THOUGHT": 12,
    "TOOL_CALL": 8,
    "TOOL_RESULT": 8,
    "ACTION": 3,
    "ERROR": 0,
    "STATUS_CHANGE": 2
  }
}
```

#### `ERROR` (connection-level)

Sent if the connection cannot be established (invalid JWT, task not in_progress).

```jsonc
{
  "type": "ERROR",
  "code": "UNAUTHORIZED",            // "UNAUTHORIZED" | "TASK_NOT_ACTIVE" | "TASK_NOT_FOUND"
  "message": "Invalid or expired JWT token."
}
```

---

## Client → Server Messages

### `CATCH_UP`

Request replay of events missed since disconnection.

```jsonc
{
  "type": "CATCH_UP",
  "last_sequence": 41                // server replays all events with sequence_number > 41
}
```

The server queries `stream_events WHERE task_id = X AND sequence_number > 41 ORDER BY sequence_number ASC`
and sends them as regular event envelopes before resuming the live Redis subscription.

### `PAUSE`

Request the agent to pause after its current reasoning step.

```jsonc
{
  "type": "PAUSE",
  "timestamp": "2026-05-11T10:31:00Z"
}
```

Effect: server calls `pause_service.pause(task_id)` which sets `Redis SET pause:{task_id} 1`.
The agent checks this key at each LangGraph node entry and raises `PauseSignal` if set.

### `RESUME`

Resume the paused agent with optional steering instructions.

```jsonc
{
  "type": "RESUME",
  "steering_instructions": "Focus on writing unit tests for the new function.",
  "timestamp": "2026-05-11T10:35:00Z"
}
```

Effect: server calls `pause_service.resume(task_id, steering_instructions)` which deletes
`pause:{task_id}` from Redis and stores `steering_instructions` in `agent_pause_states`. The
LangGraph graph resumes; next `context_builder` call injects the steering instructions.

---

## Reconnection Algorithm (Client Side)

```typescript
function connectWithReconnect(taskId: string, lastSequence: number) {
  const ws = new WebSocket(`ws://localhost:8000/ws/tasks/${taskId}/stream?token=${jwt}`);

  ws.onopen = () => {
    if (lastSequence > 0) {
      ws.send(JSON.stringify({ type: 'CATCH_UP', last_sequence: lastSequence }));
    }
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.sequence_number !== undefined) {
      lastSequence = msg.sequence_number;   // track latest seen
    }
    // dispatch to UI...
  };

  ws.onclose = (event) => {
    if (!event.wasClean && agentStillRunning) {
      setTimeout(() => connectWithReconnect(taskId, lastSequence), 1000);  // 1 s backoff
    }
  };
}
```

---

## Sequence Number Guarantees

- `sequence_number` starts at 1 for each agent run.
- It is assigned by `event_publisher.py` inside a DB transaction (`SELECT MAX(sequence_number) + 1 FOR UPDATE`).
- Events are inserted into `stream_events` before being published to Redis.
- If Redis publish fails, the event remains in `stream_events` and will be replayed via `CATCH_UP`.
- Clients should display events in `sequence_number` order (server sends them in order, but the client
  should sort the catch-up batch before merging with the live stream).

---

## Redis Channel Naming

| Channel | Description |
|---------|-------------|
| `task:{task_id}:events` | Live event stream for the task |
| `pause:{task_id}` | Pause flag (presence = paused; delete = resumed) |

`event_publisher.py` publishes to `task:{task_id}:events`.
`ws_handler.py` subscribes to `task:{task_id}:events` and forwards to the WebSocket connection.
Multiple WebSocket connections to the same `task_id` all receive the same events (fan-out via Redis Pub/Sub).
