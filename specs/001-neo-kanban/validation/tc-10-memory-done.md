# TC-10 — Done tasks → memory entries + MEMORY.md (five fields)

**Spec Kit:** T114  
**Related:** `tasks.md` (Phase 20 / US12), `MemoryService`, `kanban_service.move_task` on `REVIEW` → `DONE`

## Criterion

**100%** of tasks moved to **Done** with an **approved** diff must produce a `memory_entries` row with all **five** fields populated and appear in **`{SANDBOX_ROOT}/{project_id}/MEMORY.md`** in the format from `plan.md` / `_render_memory_md_entry`:

| Field            | DB column           | In MEMORY.md                    |
|------------------|---------------------|---------------------------------|
| Timestamp        | `entry_timestamp`   | `- **Timestamp**:`             |
| Task ID          | `task_id`           | `- **Task ID**:`               |
| Summary          | `summary`           | `- **Summary**:`               |
| Files affected   | `files_affected`    | `- **Files Affected**:`        |
| Lessons learned  | `lessons_learned`   | `- **Lessons Learned**:`       |

## Automated check (CI / local)

```bash
cd backend && pytest tests/integration/test_tc10_memory_five_done_cycles.py -v
```

Requires PostgreSQL (`DATABASE_URL`). The test creates **five** synthetic approved diffs, runs `MemoryService.create_entry` + `export_memory_file` for each (same code path as approve→done memory wiring), stubs LLM extraction, asserts **five** DB rows with non-empty fields and **five** entry blocks in `MEMORY.md`.

## Manual QA (full approve cycles)

1. Use a dev project with sandbox and Groq (or stub) as in quickstart.  
2. Complete **five** real review → approve → done flows (each task produces an approved diff before done).  
3. `GET /api/v1/projects/{project_id}/memory` — expect **five** entries; each JSON object has `entry_timestamp`, `task_id`, `summary`, `files_affected`, `lessons_learned` populated.  
4. Open `{SANDBOX_ROOT}/{project_id}/MEMORY.md` — expect **five** `## [MEMORY-…]` sections, each with all five bullet lines above.

Record results in your release notes if counts differ from five (investigate missing approved diff or `create_entry` errors in logs).
