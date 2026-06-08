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

# Kept small to limit tokens per coder call (free-tier friendly): the codebase map
# and memory are injected into the coder's context every run, so a 120k-char map was
# ~30k tokens per call and drained the daily quota in a few tasks.
_MAX_MEMORY_MD_CHARS = 4_000           # ~1 k tokens  (was 8 000)
_MAX_CODEBASE_MAP_JSON_CHARS = 10_000  # ~2.5 k tokens (was 20 000)
_MAX_INLINE_COMMENTS_JSON_CHARS = 8_000
_MAX_CONSTITUTION_CHARS = 2_000        # ~500 tokens — coder needs the gist, not full doc


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
            "intent/constitution does not support. This means:\n"
            "   - Do NOT add performance metrics (Lighthouse scores, FCP targets, uptime %) unless "
            "the user explicitly asked for them.\n"
            "   - Do NOT add security requirements (HTTPS, sanitization, rate limiting) unless "
            "the user explicitly asked for them.\n"
            "   - Do NOT add reliability requirements (retry logic, concurrent request limits) "
            "unless the user explicitly asked for them.\n"
            "   - Do NOT add scalability or CDN requirements unless explicitly requested.\n"
            "   If something is genuinely undecided, state it as an assumption, not a requirement.\n"
            "3. SCOPE MATCHING — match the spec depth to the intent complexity. A simple website "
            "or CRUD app does NOT need enterprise NFRs. Only describe what the user asked for.\n"
            "4. TESTABLE & CONCRETE — prefer specific, verifiable statements over vague ones. "
            "Every requirement must be checkable by a reader.\n"
            "5. MARKDOWN ONLY — output a single well-formed Markdown document. "
            "No preamble, no apology, no 'here is your document' wrapper text.\n\n"
            "## Project Constitution\n"
            f"{constitution_block}\n"
        )
        if artifact == "spec":
            system_prompt += (
                "\n## SPEC.md output contract\n"
                "You produce **SPEC.md**, the authoritative specification for this project. "
                "Every section you include must be complete and useful — do not pad with boilerplate.\n\n"
                "**ALWAYS include:**\n"
                "1. `# Overview` — what is being built, in the user's own words.\n"
                "2. `## Goals` and `## Non-Goals` — bound the scope explicitly.\n"
                "3. `## Functional Requirements` — one requirement per user-facing behaviour "
                "the user asked for. Write exactly as many as the user asked for — no more.\n"
                "4. `## Acceptance Criteria` — checklist defining 'done'.\n\n"
                "**Include ONLY when the user's intent explicitly mentions it:**\n"
                "- `## Non-Functional Requirements` — ONLY if the user mentioned performance, "
                "security, or reliability. DO NOT invent metrics, uptime targets, or benchmarks.\n"
                "- `## Data Model` — ONLY if there is persistent storage with real schema decisions.\n"
                "- `## Interfaces / API` — ONLY if the API has non-obvious contracts that "
                "cannot fit in Functional Requirements.\n"
                "- `## Assumptions & Open Questions` — ONLY for genuine ambiguity.\n\n"
                "Do not add sections to appear thorough. Write only what the user's intent supports.\n"
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
        ci_failure_report: str | None = None,
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
            "Implement the task in the sandbox using relative POSIX paths.\n"
            "Use run_terminal to VERIFY your own work before finishing — run the tests and "
            "compile/lint checks (e.g. `python -m pytest -q`, `python -m py_compile <file>`, "
            "`ruff check .`, `node --check <file>`). Allowed: git, python, pytest, ruff, node, "
            "npx, npm — one command per call, 60s limit.\n"
            "When finished, stop calling tools and briefly summarize what you changed.\n"
            "\n"
            "## File size — HARD LIMITS\n"
            "- Maximum 200 lines per source file. If a file would exceed 200 lines, split it into "
            "focused modules (e.g. `auth.py`, `models.py`, `utils.py`) — never write a monolith.\n"
            "- Maximum 100 lines per test file. One test file per source module.\n"
            "- `package-lock.json` and other auto-generated lock files must NOT be written by hand "
            "— run `npm install` and let npm generate them; do not write their content directly.\n"
            "- Config files (tsconfig.json, .eslintrc, etc.) must be minimal — only the fields "
            "actually needed. Never copy full boilerplate configs with hundreds of unused options.\n"
            "\n"
            "## Code quality requirements (apply to every language)\n"
            "Your output is validated by an automated CI pipeline (Test → Lint → Build). "
            "Write complete, runnable, self-consistent code that passes all three:\n"
            "1. COMPLETE — no placeholders, TODOs, stubs, or unimplemented functions. "
            "Implement everything the task asks for.\n"
            "2. SCOPE — implement ONLY what the task description asks for. Do not add extra "
            "features, utilities, helper classes, or abstractions beyond the task scope.\n"
            "3. CONSISTENT IMPORTS/EXPORTS — every symbol another file imports must be "
            "explicitly exported from its source file. Import paths and names must match exactly.\n"
            "4. ONE ECOSYSTEM PER PROJECT — never mix package managers or put one "
            "language's packages into another's manifest. This is a hard rule:\n"
            "   - A Python project uses `requirements.txt` (or `pyproject.toml`) and "
            "`test_*.py` files. Do NOT create `package.json` or `tsconfig.json` for it.\n"
            "   - A Node/TypeScript project uses `package.json` listing ONLY real npm "
            "packages; `scripts.test` must call a JS runner (jest/vitest), never `pytest`.\n"
            "   - Only create config for a language you actually wrote source files in.\n"
            "5. PROJECT CONFIG — write minimal config only:\n"
            "   - Node/TypeScript: `package.json` with only the dependencies you actually use, "
            "plus `scripts.test` and `scripts.build`. Do NOT generate `package-lock.json` by hand.\n"
            "   - Config files: create EXACTLY ONE format per tool — these are ALL the same tool:\n"
            "       Jest:   jest.config.js | jest.config.ts | jest.config.cjs | jest.config.mjs | jest.config.json\n"
            "       ESLint: .eslintrc.json | .eslintrc.js | .eslintrc.cjs | eslint.config.js | eslint.config.mjs\n"
            "     Pick ONE and never create the others. If you already wrote jest.config.js, do NOT also\n"
            "     write jest.config.cjs — Jest will fail with 'Multiple configurations found'.\n"
            "   - Python: correct package layout, `__init__.py` where needed.\n"
            "6. TESTS — write tests for the main behavior only: one happy path + one important "
            "edge case per function. Do NOT write exhaustive test suites with 20+ cases per "
            "function — keep test files under 100 lines. Tests must run and pass.\n"
            "   - Python: `test_*.py` files, plain `assert`, collectable by pytest.\n"
            "   - Node/TypeScript: `*.test.ts`/`*.test.js`, runner in `devDependencies`.\n"
            "7. NO BROKEN REFERENCES — do not reference files, modules, functions, env vars, or "
            "packages that you have not created or declared.\n"
            "Before finishing, run your tests with run_terminal and fix every failure. "
            "Do NOT finish while tests fail or the code does not compile."
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
            f"Project constitution (excerpt):\n{project.constitution[:_MAX_CONSTITUTION_CHARS]}"
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
        if ci_failure_report and ci_failure_report.strip():
            human_prompt += (
                "\n\n⚠️ CI pipeline FAILED on your previous submission. "
                "You MUST fix every issue listed below before finishing.\n\n"
                "MANDATORY steps before writing any code:\n"
                "1. Use read_file to read EVERY existing file in the project.\n"
                "2. Identify which files are causing the CI failure.\n"
                "3. Use write_file or run_terminal (e.g. `rm <file>`) to fix them.\n"
                "   - Duplicate config files (e.g. both jest.config.js AND jest.config.ts): "
                "delete one, keep the other.\n"
                "   - Do NOT create new files until you have read and assessed the existing ones.\n"
                "4. Run the tests with run_terminal to confirm the fix works.\n\n"
                "CI failure details:\n"
                + ci_failure_report.strip()[:10_000]
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
            "Kanban tasks, so every item must be actionable.\n\n"
            "**NO INVENTION RULE (applies to PLAN too):**\n"
            "Do NOT add tech choices, tools, or steps that the SPEC does not require:\n"
            "- Do NOT add ESLint, Prettier, Rollup, Webpack, Vite unless SPEC requires them.\n"
            "- Do NOT add Jest/pytest unless the SPEC explicitly requires testing.\n"
            "- Do NOT add GitHub Actions, Docker, CI/CD setup unless SPEC explicitly requires them.\n"
            "- Do NOT add TypeScript unless SPEC requires it — plain JS is fine for simple projects.\n"
            "The stack must be the minimum that delivers the SPEC. Fewer dependencies = better.\n\n"
            "**Scope calibration — derive workstream count from the SPEC itself:**\n"
            "Count the number of INDEPENDENTLY DEPLOYABLE features in the SPEC. "
            "That count is your maximum number of workstream items.\n"
            "A 'feature' is something the user asked for — not a sub-step of building it. "
            "Setup, config, testing, and tooling are NEVER separate features.\n"
            "Default to the LOWEST count that covers the SPEC. Do NOT pad with granularity.\n\n"
            "Always include these core sections:\n"
            "1. `# Implementation Plan` — 1–2 sentence framing tied to the SPEC.\n"
            "2. `## Tech Stack` — minimum viable only. One sentence per choice.\n"
            "3. `## Workstreams` — ordered deliverables; dependencies first.\n"
            "   HARD RULES:\n"
            "   a) Tests are NOT a separate workstream item — fold into the feature item.\n"
            "   b) Project setup (package.json, etc.) is NOT a separate workstream item — "
            "fold into the first implementation item.\n"
            "   c) Config/tooling (ESLint, tsconfig, jest.config) is NOT a workstream item.\n"
            "   d) Only split when features are genuinely independent and cannot be built together.\n\n"
            "Include only when genuinely applicable:\n"
            "4. `## Risks & Mitigations` — only for large/complex scope with real risks.\n\n"
            "Reference SPEC sections by name instead of pasting them.\n"
        )
        human_prompt = (
            base["human"]
            + "\n\n## Approved SPEC (read-only)\n\n"
            f"{spec_markdown.strip()}\n"
        )
        return {"system": system_prompt, "human": human_prompt}
