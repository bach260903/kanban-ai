# TC-12 + TC-13 — Squash (one commit per approve) and inline comment round-trip

**Spec Kit:** T116  
**Related:** `tasks.md` Phase 20; US15 (Git branching); US16 (inline comments)

## TC-12 — One squash commit on `main` per approve

**Goal:** After PO approves a task (`review` → `done`), the sandbox repo gains **exactly one** new commit on the integration branch (`main` or `master`) containing the squashed work from `task/{uuid8}`.

**Implementation reference:** `BranchService` in `backend/app/git/branch_service.py` — `merge --squash` then a **single** `git commit` when there are staged changes.

### Manual scenario

1. Create or open a project; ensure `SANDBOX_ROOT/{project_id}/` is a Git repo with `main` (or `master`) and a baseline commit (normal **todo → in_progress** path initialises the repo — see `kanban_service.move_task`).
2. Move a task **in progress** so `create_task_branch` runs; confirm branch `task/{first8}` exists (`GET /api/v1/tasks/{task_id}/branch` or `git branch` in sandbox).
3. Let the coder produce commits on the task branch (or add a few commits manually on that branch for a dry run).
4. Move task to **review**, then **approve** (→ `done`). This triggers `squash_and_merge`.
5. On integration branch, run:
   - `git log --oneline -5` — you should see **one** new squash merge commit message like `Squash merge task/… into main` (not N raw task commits copied to `main`).
   - Optional: `git rev-list --count main` before vs after approve — increase by **1** when squash had staged changes.

**Conflict path (out of scope for TC-12 pass):** if merge fails, task may land in `conflict`; see `BranchService.detect_conflict`.

### Automated check

```bash
cd backend && pytest tests/unit/test_branch_squash_tc12.py -v
```

Requires `git` on `PATH` and **GitPython** (`requirements.txt`). Skips if `git` is missing.

---

## TC-13 — Inline comment `{file, line}` round-trip

**Goal:** A comment anchored to `(file_path, line_number)` is persisted, visible after reload, and available to the coder on **reject** in structured form (not only as free text).

### Manual scenario

1. Open **Code review** for a task in **review** with a loaded diff (`ReviewPanel`).
2. Click a line in the modified editor; add a comment; **Save** — confirm `POST /api/v1/tasks/{task_id}/comments` succeeds (Network tab).
3. Reload the page or re-open the panel — comment **glyphs** / list still show the same **file** and **line** (round-trip from DB).
4. Enter reject feedback; **Reject** — request body includes `inline_comments: [{ file_path, line_number, comment_text }]` (see T111) and backend validates paths against `files_affected` (`tasks.py` reject handler).
5. Confirm coder context receives that list (logs / agent behaviour as per T107).

### API quick checks

- `GET /api/v1/tasks/{task_id}/comments` — rows include `file_path`, `line_number`, `comment_text`.
- `POST .../reject` with JSON `{ "feedback": "...", "inline_comments": [...] }` — 200 when paths match the current diff.

---

## Recorded sign-off (optional)

| Date | TC-12 (1 squash commit) | TC-13 (file/line round-trip) | Notes |
|------|---------------------------|------------------------------|-------|
|      | pass / fail               | pass / fail                  |       |
