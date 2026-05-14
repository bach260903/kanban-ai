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
    async def build_architect_context(project_id: UUID, session: AsyncSession) -> dict[str, str]:
        """Load project constitution and compose architect prompt context."""
        project = await ProjectService.get(session, project_id)
        constitution = project.constitution.strip()
        constitution_block = (
            constitution if constitution else "No constitution provided yet. Follow safe defaults."
        )

        system_prompt = (
            "You are the Architect Agent for Neo-Kanban. "
            "Produce clear, testable Markdown artifacts aligned with project goals.\n\n"
            "## Project Constitution\n"
            f"{constitution_block}\n"
        )
        human_prompt = (
            "Generate or revise the requested architecture/specification content for this project "
            "while strictly following the constitution above."
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
            "Use run_terminal only for read-only git commands (e.g. `git status`).\n"
            "When finished, stop calling tools and briefly summarize what you changed."
        )
        memory_path = _sandbox_project_dir(project_id) / "MEMORY.md"
        try:
            if memory_path.is_file():
                mem_txt = memory_path.read_text(encoding="utf-8", errors="replace").strip()
                if mem_txt:
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
        base = await ContextBuilder.build_architect_context(project_id, session)
        system_prompt = (
            base["system"]
            + "\n## PLAN output\n"
            "You now produce **PLAN.md**: a concise implementation plan derived from the approved SPEC below. "
            "Use Markdown with clear sections (for example phases, workstreams, milestones, risks, and testing). "
            "Do not paste the entire SPEC; reference its sections when helpful.\n"
        )
        human_prompt = (
            base["human"]
            + "\n\n## Approved SPEC (read-only)\n\n"
            f"{spec_markdown.strip()}\n"
        )
        return {"system": system_prompt, "human": human_prompt}
