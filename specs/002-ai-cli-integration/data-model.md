# Data Model: AI CLI Integration

**Feature**: 002-ai-cli-integration  
**Date**: 2026-05-18  
**Scope**: Additive changes only — no breaking schema changes

---

## Changes to Existing Entities

### `projects` (modified)

Thêm một column mới:

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `coding_backend` | `VARCHAR(20)` | NOT NULL, CHECK | `'groq'` | Backend dùng để sinh code cho Coder Agent |

**CHECK constraint**:
```sql
CHECK (coding_backend IN ('groq', 'claude_code', 'openai', 'gemini'))
```

**Migration**: `backend/alembic/versions/004_add_coding_backend.py`

---

## New ORM Enum

```python
# backend/app/models/project.py
import enum

class CodingBackend(str, enum.Enum):
    groq        = "groq"         # Groq API + LangGraph ReAct (default)
    claude_code = "claude_code"  # Claude Code CLI (claude --print)
    openai      = "openai"       # OpenAI Python SDK + LangChain
    gemini      = "gemini"       # Gemini CLI (gemini -p)
```

---

## AgentState Changes

Thêm `coding_backend` vào `AgentState` TypedDict:

```python
# backend/app/agent/state.py
class AgentState(TypedDict):
    ...existing fields...
    coding_backend: str   # propagated from project.coding_backend at graph entry
```

---

## No New Tables

- Không cần bảng mới — CLI output stream qua `stream_events` hiện tại
- Diff record vẫn dùng bảng `diffs` hiện tại
- Audit log vẫn dùng bảng `audit_logs` hiện tại

---

## Schema Migration SQL

```sql
-- Migration 004
ALTER TABLE projects
  ADD COLUMN coding_backend VARCHAR(20) NOT NULL DEFAULT 'groq'
  CHECK (coding_backend IN ('groq', 'claude_code', 'openai', 'gemini'));

COMMENT ON COLUMN projects.coding_backend IS
  'AI coding backend: groq (default LangGraph ReAct), claude_code (Claude Code CLI), openai (OpenAI SDK), gemini (Gemini CLI)';
```

---

## Project Response Schema (updated)

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "primary_language": "python | javascript | typescript",
  "coding_backend": "groq | claude_code | openai | gemini",
  "constitution": "string",
  "status": "active | archived",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

## .env.example (new fields)

```env
# AI CLI Backends (add as needed)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=

GOOGLE_AI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
GEMINI_CLI_PATH=gemini

CLAUDE_CODE_PATH=claude
# ANTHROPIC_API_KEY already present for Groq alternative
```
