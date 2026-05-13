"""Assemble agent prompts from persisted project context (US4)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.project_service import ProjectService


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
