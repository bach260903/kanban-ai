"""Memory entries from approved diffs and MEMORY.md export (US12 / T091–T092)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundError, SandboxEscapeError
from app.models.diff import Diff
from app.models.memory_entry import MemoryEntry

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = 24_000
_MAX_SUMMARY = 20_000
_MAX_LESSONS = 50_000


def _sandbox_project_dir(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


def _task_id_short(task_id: UUID | None) -> str:
    if task_id is None:
        return "unknown"
    return str(task_id).replace("-", "")[:8]


def _format_timestamp_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.astimezone(timezone.utc).isoformat()
    return s.replace("+00:00", "Z")


def _render_memory_md_entry(row: MemoryEntry) -> str:
    """One block per ``plan.md`` § MEMORY.md Entry Format."""
    short = _task_id_short(row.task_id)
    first_line = (row.summary or "").strip().split("\n", 1)[0].strip() or "(no summary)"
    heading = first_line[:500]
    files = row.files_affected or []
    files_line = ", ".join(f"`{p}`" for p in files) if files else "_(none)_"
    tid = str(row.task_id) if row.task_id is not None else "—"
    lines = [
        f"## [MEMORY-{short}] {heading}",
        "",
        f"- **Timestamp**: {_format_timestamp_z(row.entry_timestamp)}",
        f"- **Task ID**: {tid}",
        f"- **Summary**: {row.summary}",
        f"- **Files Affected**: {files_line}",
        "- **Lessons Learned**:",
        row.lessons_learned,
    ]
    return "\n".join(lines)


def _stub_extraction(diff: Diff) -> tuple[str, str]:
    files = diff.files_affected or []
    label = ", ".join(files[:12]) if files else "(no paths listed)"
    if len(files) > 12:
        label += ", …"
    summary = (
        f"Code change across {len(files)} path(s). "
        f"Files: {label[:1800]}"
    )[:_MAX_SUMMARY]
    excerpt = (diff.content or "").strip()[:1200]
    lessons = (
        "No LLM extraction (GROQ_API_KEY missing or parse failed). "
        "Review the unified diff manually for pitfalls and patterns.\n\n"
        f"Excerpt:\n{excerpt}"
    )[:_MAX_LESSONS]
    return summary, lessons


def _parse_llm_json(text: str) -> tuple[str | None, str | None]:
    t = text.strip()
    if "```" in t:
        for block in t.split("```"):
            b = block.strip()
            if b.lower().startswith("json"):
                b = b[4:].lstrip()
            if b.startswith("{"):
                t = b
                break
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end <= start:
        return None, None
    try:
        data = json.loads(t[start : end + 1])
    except json.JSONDecodeError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    s = data.get("summary")
    l = data.get("lessons_learned")
    if not isinstance(s, str) or not isinstance(l, str):
        return None, None
    s, l = s.strip(), l.strip()
    if not s or not l:
        return None, None
    return s[:_MAX_SUMMARY], l[:_MAX_LESSONS]


async def _extract_summary_and_lessons(diff: Diff) -> tuple[str, str]:
    if not settings.groq_api_key.strip():
        return _stub_extraction(diff)

    body = (diff.content or "").strip()
    if len(body) > _MAX_DIFF_CHARS:
        body = body[:_MAX_DIFF_CHARS] + "\n…(diff truncated)"

    system = (
        "You extract institutional memory from an approved code diff. "
        "Respond with ONLY a single JSON object (no markdown fences), keys exactly: "
        '"summary" (one short paragraph) and "lessons_learned" '
        "(plain text: what worked, risks, follow-ups for similar tasks)."
    )
    human = (
        "Files affected (JSON array):\n"
        + json.dumps(diff.files_affected or [])
        + "\n\nUnified diff:\n"
        + body
    )

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.2,
    )
    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(content=system),
                HumanMessage(content=human),
            ]
        )
        raw = str(resp.content).strip()
    except Exception:
        logger.exception("memory LLM invoke failed")
        return _stub_extraction(diff)

    summ, lessons = _parse_llm_json(raw)
    if summ is None or lessons is None:
        logger.warning("memory LLM JSON parse failed; raw_len=%s", len(raw))
        return _stub_extraction(diff)
    return summ, lessons


class MemoryService:
    """``memory_entries`` persistence and sandbox ``MEMORY.md`` export."""

    @staticmethod
    async def create_entry(
        session: AsyncSession,
        project_id: UUID,
        task_id: UUID,
        diff: Diff,
    ) -> MemoryEntry:
        """LLM-derived ``summary`` / ``lessons_learned`` plus diff metadata → new ``MemoryEntry`` (not committed)."""
        if diff.task_id != task_id:
            raise ValueError("diff.task_id must match task_id for memory entry.")
        summary, lessons_learned = await _extract_summary_and_lessons(diff)
        now = datetime.now(timezone.utc)
        row = MemoryEntry(
            project_id=project_id,
            task_id=task_id,
            entry_timestamp=now,
            summary=summary,
            files_affected=list(diff.files_affected or []),
            lessons_learned=lessons_learned,
        )
        session.add(row)
        await session.flush()
        return row

    @staticmethod
    async def export_memory_file(session: AsyncSession, project_id: UUID) -> Path:
        """Load all project memory rows (oldest first), render ``MEMORY.md``, write under sandbox (T092)."""
        stmt = (
            select(MemoryEntry)
            .where(MemoryEntry.project_id == project_id)
            .order_by(MemoryEntry.entry_timestamp.asc())
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())

        header = (
            "# MEMORY\n\n"
            "Entries below are generated from `memory_entries` in chronological order "
            "(see implementation plan MEMORY.md format).\n"
        )
        blocks = [_render_memory_md_entry(r) for r in rows]
        body = header + ("\n\n".join(blocks) if blocks else "_No memory entries yet._\n")
        if not body.endswith("\n"):
            body += "\n"

        sandbox = _sandbox_project_dir(project_id)
        sandbox.mkdir(parents=True, exist_ok=True)
        out = sandbox / "MEMORY.md"
        out.write_text(body, encoding="utf-8", newline="\n")
        return out

    @staticmethod
    async def list_for_project(session: AsyncSession, project_id: UUID) -> list[MemoryEntry]:
        result = await session.execute(
            select(MemoryEntry)
            .where(MemoryEntry.project_id == project_id)
            .order_by(MemoryEntry.entry_timestamp.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_entry(session: AsyncSession, project_id: UUID, entry_id: UUID) -> MemoryEntry:
        row = await session.get(MemoryEntry, entry_id)
        if row is None or row.project_id != project_id:
            raise NotFoundError("Memory entry not found.")
        return row

    @staticmethod
    async def update_entry(
        session: AsyncSession,
        project_id: UUID,
        entry_id: UUID,
        *,
        summary: str | None,
        lessons_learned: str | None,
    ) -> MemoryEntry:
        row = await MemoryService.get_entry(session, project_id, entry_id)
        if summary is not None:
            row.summary = summary.strip()
        if lessons_learned is not None:
            row.lessons_learned = lessons_learned.strip()
        await session.flush()
        return row

    @staticmethod
    async def delete_entry(session: AsyncSession, project_id: UUID, entry_id: UUID) -> None:
        row = await MemoryService.get_entry(session, project_id, entry_id)
        await session.delete(row)
        await session.flush()
