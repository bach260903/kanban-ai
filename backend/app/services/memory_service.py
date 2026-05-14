"""Memory entries from approved diffs (US12 / T091)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.diff import Diff
from app.models.memory_entry import MemoryEntry

logger = logging.getLogger(__name__)

_MAX_DIFF_CHARS = 24_000
_MAX_SUMMARY = 20_000
_MAX_LESSONS = 50_000


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
    """Create ``memory_entries`` rows from diff content (optional Groq extraction)."""

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
