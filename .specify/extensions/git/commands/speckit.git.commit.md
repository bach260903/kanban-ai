---
description: "Auto-commit changes after a Spec Kit command completes"
---

# Auto-Commit Changes

Automatically stage and commit all changes after a Spec Kit command completes.

## Behavior

This command is invoked as a hook after (or before) core commands. It:

1. Determines the event name from the hook context (e.g., if invoked as an `after_specify` hook, the event is `after_specify`; if `before_plan`, the event is `before_plan`)
2. Checks `.specify/extensions/git/git-config.yml` for the `auto_commit` section
3. Looks up the specific event key to see if auto-commit is enabled
4. Falls back to `auto_commit.default` if no event-specific key exists
5. Uses the per-command `message` if configured, otherwise a default message (see **Conventional Commits** below)
6. If enabled and there are uncommitted changes, runs `git add .` + `git commit`

## Commit messages (Conventional Commits)

Commits created by this command **SHOULD** follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

**Subject line (required, single line):**

```text
<type>[optional scope]: <description>
```

- **type** (common): `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `build`, `ci`, `perf`
- **scope** (optional): area of the repo, e.g. `spec`, `frontend`, `backend`, `spec-kit`
- **description**: imperative mood, lowercase start (no trailing period preferred), ~72 chars max

**Breaking changes:** append `!` after type/scope, e.g. `feat(api)!: remove legacy endpoint`.

**Body (optional):** after a blank line, add context such as Spec Kit task IDs:

```text
feat(frontend): add constitution editor page

Spec Kit: T029
```

**Examples**

- `docs(spec): add neo-kanban specification`
- `feat(backend): add projects CRUD API`
- `chore(spec-kit): sync tasks after plan update`

Avoid non-conventional prefixes like `[Spec Kit]` **in the subject**; put that in the **body** if you need traceability.

## Execution

Determine the event name from the hook that triggered this command, then run the script:

- **Bash**: `.specify/extensions/git/scripts/bash/auto-commit.sh <event_name>`
- **PowerShell**: `.specify/extensions/git/scripts/powershell/auto-commit.ps1 <event_name>`

Replace `<event_name>` with the actual hook event (e.g., `after_specify`, `before_plan`, `after_implement`).

## Configuration

In `.specify/extensions/git/git-config.yml`:

```yaml
auto_commit:
  default: false          # Global toggle — set true to enable for all commands
  after_specify:
    enabled: true          # Override per-command
    message: "docs(spec): add specification"
  after_plan:
    enabled: false
    message: "docs(plan): add implementation plan"
```

## Graceful Degradation

- If Git is not available or the current directory is not a repository: skips with a warning
- If no config file exists: skips (disabled by default)
- If no changes to commit: skips with a message
