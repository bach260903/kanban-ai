"""Project persistence and business rules (US1)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DuplicateNameError, NotFoundError
from app.models.project import CodingBackend, Project, ProjectStatus
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    @staticmethod
    def _archived_name(original: str, project_id: UUID) -> str:
        """Rename archived project so the display name can be reused by a new project."""
        suffix = f"__archived_{project_id.hex[:8]}"
        max_base = 255 - len(suffix)
        base = original.strip()[:max_base].rstrip()
        return f"{base}{suffix}"

    @staticmethod
    async def _release_project_name(session: AsyncSession, project: Project) -> None:
        released = ProjectService._archived_name(project.name, project.id)
        if project.name == released:
            return
        project.name = released
        await session.flush()

    @staticmethod
    async def create(session: AsyncSession, data: ProjectCreate) -> Project:
        name = data.name.strip()
        project = Project(
            name=name,
            description=data.description,
            primary_language=data.primary_language,
            coding_backend=data.coding_backend,
        )
        session.add(project)
        await session.flush()
        return project

    @staticmethod
    async def get(session: AsyncSession, project_id: UUID) -> Project:
        project = await session.get(Project, project_id)
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    @staticmethod
    async def list(session: AsyncSession) -> list[Project]:
        result = await session.execute(select(Project).order_by(Project.updated_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def update(session: AsyncSession, project_id: UUID, data: ProjectUpdate) -> Project:
        project = await ProjectService.get(session, project_id)
        if data.name is not None:
            new_name = data.name.strip()
            if new_name != project.name:
                conflict = await session.scalar(
                    select(Project.id).where(
                        Project.name == new_name,
                        Project.id != project.id,
                        Project.status == ProjectStatus.ACTIVE,
                    )
                )
                if conflict is not None:
                    raise DuplicateNameError(f"Project name '{new_name}' already exists.")
            project.name = new_name
        if data.description is not None:
            project.description = data.description
        if data.coding_backend is not None:
            project.coding_backend = data.coding_backend
        await session.flush()
        return project

    @staticmethod
    async def archive(session: AsyncSession, project_id: UUID) -> Project:
        project = await ProjectService.get(session, project_id)
        project.status = ProjectStatus.ARCHIVED
        await ProjectService._release_project_name(session, project)
        await session.flush()
        return project

    @staticmethod
    async def get_constitution(session: AsyncSession, project_id: UUID) -> Project:
        return await ProjectService.get(session, project_id)

    @staticmethod
    async def update_constitution(session: AsyncSession, project_id: UUID, content: str) -> Project:
        project = await ProjectService.get(session, project_id)
        project.constitution = content
        await session.flush()
        return project
