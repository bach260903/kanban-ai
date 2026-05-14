"""TC-10 (T114): five approved-diff memory writes → five DB rows + MEMORY.md with all five fields each.

Mirrors ``move_task(..., DONE)`` memory path without Git merge: each synthetic ``Diff`` is approved,
``MemoryService.create_entry`` + ``export_memory_file`` run once per task. ``_extract_summary_and_lessons``
is stubbed so tests do not call Groq. Requires PostgreSQL; skips if unreachable.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select, text

from app.database import async_session_maker, engine
from app.models.diff import Diff, DiffReviewStatus
from app.models.memory_entry import MemoryEntry
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.services import memory_service
from app.services.memory_service import MemoryService


async def _cleanup_project(project_id: UUID) -> None:
    async with async_session_maker() as session:
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.commit()


@pytest_asyncio.fixture
async def tc10_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> UUID:
    """Create project + 5 done tasks + approved diffs; run memory create+export; yield ``project_id``."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        low = str(exc).lower()
        if "refused" in low or "1225" in str(exc) or "could not connect" in low:
            pytest.skip(f"PostgreSQL not reachable (integration TC-10): {exc}")
        raise

    monkeypatch.setattr(memory_service.settings, "sandbox_root", str(tmp_path))

    async def _fake_extract(_diff: Diff) -> tuple[str, str]:
        return (
            "Summary for approved diff (TC-10 stub).",
            "Lessons learned (TC-10 stub): verify patterns and edge cases.",
        )

    monkeypatch.setattr(memory_service, "_extract_summary_and_lessons", _fake_extract)

    name = f"tc10_mem_{uuid.uuid4().hex[:12]}"
    project_id: UUID | None = None

    async with async_session_maker() as session:
        proj = Project(
            name=name,
            description="T114",
            primary_language="python",
            constitution="",
            status=ProjectStatus.ACTIVE,
        )
        session.add(proj)
        await session.flush()
        project_id = proj.id

        task_rows: list[Task] = []
        for i in range(5):
            t = Task(
                project_id=project_id,
                title=f"TC-10 task {i + 1}",
                description=None,
                status=TaskStatus.DONE,
                priority=i,
            )
            session.add(t)
            task_rows.append(t)
        await session.flush()

        for idx, t in enumerate(task_rows):
            session.add(
                Diff(
                    task_id=t.id,
                    agent_run_id=None,
                    content=f"diff body {idx}\n---\n+line",
                    original_content="",
                    modified_content="x",
                    files_affected=[f"src/tc10_{idx}.py"],
                    review_status=DiffReviewStatus.APPROVED,
                )
            )
        await session.flush()

        for t in task_rows:
            diff = (await session.execute(select(Diff).where(Diff.task_id == t.id))).scalar_one()
            await MemoryService.create_entry(session, project_id, t.id, diff)

        await MemoryService.export_memory_file(session, project_id)
        await session.commit()

    assert project_id is not None
    try:
        yield project_id
    finally:
        await _cleanup_project(project_id)


@pytest.mark.asyncio
async def test_tc10_five_memory_entries_all_fields_and_memory_md(tc10_project_id: UUID, tmp_path: Path) -> None:
    project_id = tc10_project_id

    async with async_session_maker() as session:
        n = await session.scalar(
            select(func.count()).select_from(MemoryEntry).where(MemoryEntry.project_id == project_id)
        )
        assert int(n or 0) == 5

        rows = (
            await session.execute(
                select(MemoryEntry)
                .where(MemoryEntry.project_id == project_id)
                .order_by(MemoryEntry.entry_timestamp.asc())
            )
        ).scalars().all()
        assert len(rows) == 5
        for row in rows:
            assert row.task_id is not None
            assert row.entry_timestamp is not None
            assert (row.summary or "").strip() != ""
            assert (row.lessons_learned or "").strip() != ""
            assert isinstance(row.files_affected, list)
            assert len(row.files_affected) >= 1
            assert all(isinstance(p, str) and p.strip() for p in row.files_affected)

    md_path = tmp_path / str(project_id) / "MEMORY.md"
    assert md_path.is_file(), f"expected MEMORY.md at {md_path}"
    body = md_path.read_text(encoding="utf-8")
    headings = re.findall(r"^## \[MEMORY-", body, flags=re.MULTILINE)
    assert len(headings) == 5
    assert body.count("- **Timestamp**:") == 5
    assert body.count("- **Task ID**:") == 5
    assert body.count("- **Summary**:") == 5
    assert body.count("- **Files Affected**:") == 5
    assert body.count("- **Lessons Learned**:") == 5
