"""Assemble agent prompts from persisted project context (US4)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import SandboxEscapeError
from app.models.agent_pause_state import AgentPauseState
from app.models.project import Project
from app.models.task import Task
from app.services.codebase_mapper import run as run_codebase_map
from app.services.project_service import ProjectService
from app.tools.token_optimizer import deduplicate_lines, optimize_file_content

logger = logging.getLogger(__name__)

_MAX_MEMORY_MD_CHARS = 24_000
_MAX_CODEBASE_MAP_JSON_CHARS = 120_000
_MAX_INLINE_COMMENTS_JSON_CHARS = 12_000


def _sandbox_project_dir(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


class ContextBuilder:
    """Build system/human prompt payloads for agent nodes."""

    @staticmethod
    async def build_architect_context(
        project_id: UUID,
        session: AsyncSession,
        *,
        artifact: str = "spec",
    ) -> dict[str, str]:
        """Load project constitution and compose architect prompt context.

        ``artifact`` selects the artifact-specific guidance appended to the base
        system prompt: ``"spec"`` adds the SPEC.md structure contract; ``"plan"``
        leaves the base generic so :meth:`build_plan_context` can append its own.
        """
        project = await ProjectService.get(session, project_id)
        constitution = project.constitution.strip()
        constitution_block = (
            deduplicate_lines(constitution) if constitution else "No constitution provided yet. Follow safe defaults."
        )

        system_prompt = (
            "You are the Architect Agent for Neo-Kanban, an autonomous software factory. "
            "The artifacts you produce are consumed downstream by other AI agents — a planner, "
            "a task-breakdown agent, and coding agents — with no human rewriting in between. "
            "Vague or incomplete output silently corrupts everything downstream, so be precise, "
            "concrete, and self-contained.\n\n"
            "## Operating rules\n"
            "1. CONSTITUTION IS BINDING — the project constitution below overrides your defaults. "
            "If a request conflicts with it, follow the constitution and note the conflict.\n"
            "2. NO INVENTION — do not invent product requirements, tech choices, or scope that the "
            "intent/constitution does not support. If something is genuinely undecided, state the "
            "assumption explicitly under an 'Assumptions' heading rather than silently guessing.\n"
            "3. TESTABLE & CONCRETE — prefer specific, verifiable statements ('expose POST /auth/login "
            "returning a JWT') over vague ones ('handle authentication'). Every requirement must be "
            "checkable by a reader.\n"
            "4. MARKDOWN ONLY — output a single well-formed Markdown document with a clear heading "
            "hierarchy. No preamble, no apology, no 'here is your document' wrapper text.\n\n"
            "## Project Constitution\n"
            f"{constitution_block}\n"
        )
        if artifact == "spec":
            system_prompt += (
                "\n## SPEC.md output contract\n"
                "You produce **SPEC.md**, the authoritative specification for this project. "
                "Use this section structure (omit a section only if it is truly inapplicable, and "
                "say why):\n"
                "1. `# Overview` — 2–4 sentences: what is being built and the problem it solves.\n"
                "2. `## Goals` and `## Non-Goals` — bullet lists bounding the scope explicitly.\n"
                "3. `## Functional Requirements` — numbered, each independently testable; reference "
                "concrete endpoints, screens, data, or behaviors.\n"
                "4. `## Non-Functional Requirements` — performance, security, reliability, "
                "accessibility, or constraints that apply.\n"
                "5. `## Data Model` — key entities and their important fields/relationships "
                "(only if the project stores data).\n"
                "6. `## Interfaces / API` — the external surface (HTTP endpoints, CLI, UI flows) "
                "with inputs and outputs (only if applicable).\n"
                "7. `## Acceptance Criteria` — a checklist that defines 'done' for the whole spec.\n"
                "8. `## Assumptions & Open Questions` — anything you had to assume or that needs "
                "a human decision.\n"
                "Keep it complete but tight; do not pad with boilerplate.\n"
            )
        human_prompt = (
            "Generate or revise the requested architecture/specification content for this project "
            "while strictly following the constitution and the output contract above."
        )
        return {"system": system_prompt, "human": human_prompt}

    @staticmethod
    async def build_coder_context(
        project_id: UUID,
        task_id: UUID,
        session: AsyncSession,
        *,
        task: Task,
        project: Project,
        po_feedback: str | None = None,
        inline_comments: list[dict[str, str | int]] | None = None,
    ) -> dict[str, str]:
        """Coder system/human prompts; MEMORY.md (T094), codebase map (T100), PO steering (T087)."""
        if task.id != task_id or task.project_id != project_id or project.id != project_id:
            raise ValueError("build_coder_context: task/project must match project_id and task_id.")

        pause_row = await session.scalar(select(AgentPauseState).where(AgentPauseState.task_id == task_id))
        steering: str | None = None
        if pause_row is not None and pause_row.steering_instructions is not None:
            stripped = pause_row.steering_instructions.strip()
            if stripped:
                steering = stripped

        system_prompt = (
            "You are the Coder agent. Work only via tools: read_file, write_file, run_terminal.\n"
            "Implement the task in the sandbox using relative POSIX paths. Prefer small files.\n"
            "Use run_terminal to VERIFY your own work before finishing — run the tests and "
            "compile/lint checks (e.g. `python -m pytest -q`, `python -m py_compile <file>`, "
            "`ruff check .`, `node --check <file>`). Allowed: git, python, pytest, ruff, node, "
            "npx, npm — one command per call, 60s limit.\n"
            "When finished, stop calling tools and briefly summarize what you changed.\n"
            "\n"
            "## Code quality requirements (apply to every language)\n"
            "Your output is validated by an automated CI pipeline (Test → Lint → Build). "
            "Write complete, runnable, self-consistent code that passes all three:\n"
            "1. COMPLETE — no placeholders, TODOs, stubs, or unimplemented functions. "
            "Implement everything the task asks for.\n"
            "2. CONSISTENT IMPORTS/EXPORTS — every symbol another file imports must be "
            "explicitly exported from its source file (e.g. `export` in JS/TS, public "
            "names in Python). Import paths and names must match exactly.\n"
            "3. ONE ECOSYSTEM PER PROJECT — never mix package managers or put one "
            "language's packages into another's manifest. This is a hard rule:\n"
            "   - A Python project uses `requirements.txt` (or `pyproject.toml`) and "
            "`test_*.py` files. Do NOT create `package.json` or `tsconfig.json` for it, "
            "and NEVER list Python packages (pytest, numpy, flask, fastapi, …) in a "
            "`package.json` — pip packages are not npm packages.\n"
            "   - A Node/TypeScript project uses `package.json` listing ONLY real npm "
            "packages; `scripts.test` must call a JS runner (jest/vitest), never `pytest` "
            "or `python`. Only add `tsconfig.json` if you actually wrote `.ts`/`.tsx` files.\n"
            "   - Only create config for a language you actually wrote source files in. "
            "Pinned versions must exist in that ecosystem's registry.\n"
            "4. PROJECT CONFIG — write the config files the chosen ecosystem needs to build "
            "and lint:\n"
            "   - Node/TypeScript: a `package.json` with `dependencies`, `devDependencies`, "
            "and a `scripts` block including real `test` and `build` commands. If you write "
            "tests, add the test runner (e.g. jest or vitest) to `devDependencies` and set "
            "`scripts.test`. For TypeScript also add a `tsconfig.json`; if tests use a runner, "
            "include its types (e.g. `@types/jest`) in `devDependencies` and the tsconfig `types`.\n"
            "   - Python: keep modules importable (correct package layout, `__init__.py` where "
            "needed). Name test files `test_*.py` with importable, runnable test functions.\n"
            "5. ALWAYS WRITE TESTS — for any code that has behavior (functions, classes, "
            "endpoints, components), write at least one real automated test with meaningful "
            "assertions covering the main path, plus an important edge case when relevant. "
            "This is required, not optional — the CI test step must have something real to run.\n"
            "   - Python: put tests in `test_*.py` files with `def test_*` functions using plain "
            "`assert`; import the code under test. They must be collectable and pass under pytest.\n"
            "   - Node/TypeScript: name tests `*.test.ts`/`*.test.js` (or `*.spec.*`), wire the "
            "runner in `devDependencies` + `scripts.test`, and make them pass.\n"
            "   - The tests must actually run and PASS in a clean checkout: the runner is "
            "declared, the test command exists, and the code under test is importable. Do not "
            "write empty tests or tests that assert nothing.\n"
            "   - Only skip tests for tasks that genuinely have no testable behavior (pure docs/"
            "config); if you skip, state why in your summary.\n"
            "6. NO BROKEN REFERENCES — do not reference files, modules, functions, env vars, or "
            "packages that you have not created or declared.\n"
            "Before finishing, you MUST verify your work by running it, not just reading it: "
            "run your tests with run_terminal (e.g. `python -m pytest -q`) and fix every failure. "
            "Do NOT finish while your own tests fail or the code does not import/compile. "
            "Every symbol your code or tests reference MUST be defined — if a test calls "
            "`User.get_by_id(...)` or `user.save()`, you must define those methods on the class. "
            "Re-read the files you wrote and confirm imports resolve, exports exist, and config "
            "files are consistent with the code."
        )
        memory_path = _sandbox_project_dir(project_id) / "MEMORY.md"
        try:
            if memory_path.is_file():
                mem_txt = memory_path.read_text(encoding="utf-8", errors="replace").strip()
                if mem_txt:
                    mem_txt = optimize_file_content(mem_txt, max_lines=300)
                    if len(mem_txt) > _MAX_MEMORY_MD_CHARS:
                        mem_txt = mem_txt[:_MAX_MEMORY_MD_CHARS] + "\n…(MEMORY.md truncated)"
                    system_prompt += "\n\n## Past Lessons\n\n" + mem_txt
        except SandboxEscapeError:
            raise
        except OSError as exc:
            logger.warning("Could not read MEMORY.md for project_id=%s: %s", project_id, exc)
        try:
            map_payload = await run_codebase_map(
                session,
                project_id=project_id,
                task_id=task_id,
                project_root=_sandbox_project_dir(project_id),
                primary_language=project.primary_language,
            )
            blob = json.dumps(map_payload, indent=2, ensure_ascii=False)
            if len(blob) > _MAX_CODEBASE_MAP_JSON_CHARS:
                blob = blob[:_MAX_CODEBASE_MAP_JSON_CHARS] + "\n…(codebase map JSON truncated)"
            system_prompt += f"\n\n## Codebase Structure\n\n```json\n{blob}\n```\n"
        except SandboxEscapeError:
            raise
        except Exception as exc:
            logger.warning("codebase map run failed for project_id=%s task_id=%s: %s", project_id, task_id, exc)
        if steering is not None:
            system_prompt += f"\n\nUpdated instructions from Project Owner: {steering}"

        human_prompt = (
            f"Task title: {task.title}\n"
            f"Task description:\n{task.description or '(none)'}\n\n"
            f"Project constitution (excerpt, first 8000 chars):\n{project.constitution[:8000]}"
        )
        if po_feedback is not None and po_feedback.strip():
            human_prompt += (
                "\n\nPO review feedback (address this in your changes):\n" + po_feedback.strip()[:20_000]
            )
        if inline_comments:
            blob = json.dumps(inline_comments, indent=2, ensure_ascii=False)
            if len(blob) > _MAX_INLINE_COMMENTS_JSON_CHARS:
                blob = blob[:_MAX_INLINE_COMMENTS_JSON_CHARS] + "\n…(inline comments JSON truncated)"
            human_prompt += (
                "\n\nPO inline comments (structured; align edits with file_path and line_number):\n"
                f"```json\n{blob}\n```"
            )
        return {"system": system_prompt, "human": human_prompt}

    @staticmethod
    async def build_plan_context(
        project_id: UUID,
        session: AsyncSession,
        spec_markdown: str,
    ) -> dict[str, str]:
        """Architect constitution + approved SPEC body for PLAN.md generation (T044)."""
        base = await ContextBuilder.build_architect_context(project_id, session, artifact="plan")
        system_prompt = (
            base["system"]
            + "\n## PLAN.md output contract\n"
            "You now produce **PLAN.md**: a concrete implementation plan that turns the approved SPEC "
            "below into buildable work. It is read by a task-breakdown agent that will split it into "
            "Kanban tasks, so every item must be actionable. Use this structure:\n"
            "1. `# Implementation Plan` — 1–2 sentence framing tied to the SPEC.\n"
            "2. `## Tech Stack & Key Decisions` — languages, frameworks, libraries, and storage you "
            "will use, with a one-line justification each. Be specific (name + rough version) so the "
            "coder agents and CI pipeline (Test → Lint → Build) produce consistent project config.\n"
            "3. `## Architecture` — the main components/modules and how they interact.\n"
            "4. `## Workstreams / Phases` — ordered groups of work; dependencies first "
            "(data models → services/API → UI → integration), so tasks can be sequenced.\n"
            "5. `## Testing Strategy` — how the work will be verified (unit/integration, test runner).\n"
            "6. `## Risks & Mitigations` — the few things most likely to break, and the fallback.\n"
            "Reference SPEC sections by name instead of pasting them. Keep each item concrete enough "
            "that a coding agent could start without asking clarifying questions.\n"
        )
        human_prompt = (
            base["human"]
            + "\n\n## Approved SPEC (read-only)\n\n"
            f"{spec_markdown.strip()}\n"
        )
        return {"system": system_prompt, "human": human_prompt}
