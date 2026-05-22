---
name: "speckit-approve-spec"
description: "Mark the feature spec as PO-approved and immediately generate plan.md for PO review (runs speckit-plan)."
argument-hint: "Optional PO feedback or approval notes"
compatibility: "Requires spec-kit project structure with .specify/ directory and an existing spec.md"
metadata:
  author: "kanban-ai"
  source: "workflow: spec-approved → plan-for-po-review"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). PO notes may be appended to the spec or checklist.

## Purpose

When the **Product Owner (PO) has approved** the feature specification, this command:

1. Records approval in `spec.md` and the quality checklist
2. **Immediately runs the full implementation planning workflow** (`speckit-plan`) so PO can review `plan.md` next — **do not wait** for a separate `/speckit-plan` invocation

## Pre-Execution Checks

1. **Resolve feature directory** (in order):
   - Read `.specify/feature.json` → `feature_directory`
   - Else run `.specify/scripts/powershell/check-prerequisites.ps1 -Json` from repo root and parse `FEATURE_DIR`
   - Else ERROR: "No active feature. Run `/speckit-specify` first."

2. **Verify `spec.md` exists** at `{FEATURE_DIR}/spec.md`. If missing → ERROR.

3. **Verify spec quality checklist** at `{FEATURE_DIR}/checklists/requirements.md`:
   - All items under **Content Quality**, **Requirement Completeness**, and **Feature Readiness** must be checked `[x]`
   - If any unchecked (except **PO Review Gate**): WARN and list failing items; ask PO to fix spec or waive explicitly before continuing
   - If checklist file missing: create it from the template in `speckit-specify` step 7a, run validation, then stop and ask PO to confirm checklist before re-running this command

4. **Idempotency**: If `spec.md` **Status** is already `Approved` and `plan.md` exists and is newer than spec approval:
   - Ask PO: "Plan already exists. Regenerate? (yes/no)"
   - If no → report paths and stop
   - If yes → proceed to planning

## Execution Steps

### Step 1 — Record PO approval

1. Update `{FEATURE_DIR}/spec.md`:
   - Set `**Status**: Approved`
   - Add or update line: `**Approved**: [ISO date today]`
   - If `$ARGUMENTS` non-empty, append under a new `## PO Approval Notes` section (do not remove existing content)

2. Update `{FEATURE_DIR}/checklists/requirements.md`:
   - Check all items under `## PO Review Gate` as `[x]`
   - Add note: `PO approval recorded on [date]`

3. Commit is optional (respect `extensions.yml` `after_specify` / git hooks if configured)

### Step 2 — Generate plan for PO review (mandatory, same session)

**CRITICAL**: Do **not** end this command after Step 1. You **MUST** continue into planning in the **same conversation turn**.

1. Read and follow **every step** in `.claude/skills/speckit-plan/SKILL.md` (or `.cursor/skills/speckit-plan/SKILL.md` if in Cursor):
   - Run `setup-plan.ps1 -Json`
   - Load `spec.md` + constitution
   - Complete Phase 0 (`research.md`) and Phase 1 (`data-model.md`, `contracts/`, `quickstart.md`, agent context update)
   - Fill `plan.md` from template

2. After `plan.md` is written, set in `spec.md` (optional traceability line):
   - `**Plan generated**: [ISO date today]`

### Step 3 — Report to PO

Output a short **PO review packet**:

```markdown
## Spec approved — Plan ready for review

| Artifact | Path |
|----------|------|
| Spec (approved) | {FEATURE_DIR}/spec.md |
| Implementation plan | {FEATURE_DIR}/plan.md |
| Research | {FEATURE_DIR}/research.md |
| Data model | {FEATURE_DIR}/data-model.md |

### What PO should review in plan.md
- Summary and scope match the approved spec
- Constitution Check — any violations or amendments called out
- Technical Context — stack and dependencies acceptable
- Project structure — files to add/change look reasonable

### Next steps
- **Approve plan** → run `/speckit-tasks` to generate `tasks.md`
- **Request plan changes** → describe feedback; agent updates `plan.md` then re-run `/speckit-approve-spec` only if spec also changes
- **Reject plan** → revise spec via `/speckit-clarify` or edit `spec.md`, then `/speckit-approve-spec` again
```

## Triggers (when to run this command)

Run `/speckit-approve-spec` when the user (PO) says any of:

- "spec approved" / "chấp thuận spec" / "spec OK" / "approve spec"
- "generate plan" **after** spec review is done
- Confirms all checklist items pass and wants to proceed to planning

**Do not** run if spec still has `[NEEDS CLARIFICATION]` markers or failing quality checklist items (unless PO explicitly waives).

## Relationship to bundled workflow

`.specify/workflows/speckit/workflow.yml` gate `review-spec` → on `approve` → `plan` step. This skill is the **agent-executable equivalent** for Cursor/Claude when not using the Spec Kit workflow runner.
