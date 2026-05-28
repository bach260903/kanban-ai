"""Task dependency DAG: cycle detection, blocking, unlock (US4 / T063–T065)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    CircularDependencyError,
    DependencyBlockedError,
    InvalidTransitionError,
    NotFoundError,
)
from app.models.task import Task, TaskStatus
from app.models.task_dependency import TaskDependency
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


async def _load_all_deps(session: AsyncSession, project_id: UUID) -> dict[str, list[str]]:
    """Return adjacency list ``{task_id: [depends_on_task_id, ...]}`` for the project."""
    rows = await session.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
        .join(Task, Task.id == TaskDependency.task_id)
        .where(Task.project_id == project_id)
    )
    adj: dict[str, list[str]] = {}
    for task_id, dep_id in rows.all():
        adj.setdefault(str(task_id), []).append(str(dep_id))
    return adj


def _has_cycle(task_id: str, new_dep_id: str, adj: dict[str, list[str]]) -> bool:
    """DFS from ``new_dep_id``; True if ``task_id`` is reachable (adding the edge would cycle)."""
    visited: set[str] = set()
    stack = [new_dep_id]
    while stack:
        node = stack.pop()
        if node == task_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adj.get(node, []))
    return False


async def is_task_blocked(session: AsyncSession, task_id: UUID) -> bool:
    """True when any direct dependency is not ``done``."""
    dep_ids = await session.scalars(
        select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task_id)
    )
    for dep_id in dep_ids.all():
        dep_task = await session.get(Task, dep_id)
        if dep_task is None or dep_task.status != TaskStatus.DONE:
            return True
    return False


async def _sync_blocked_flag(session: AsyncSession, task_id: UUID) -> None:
    task = await session.get(Task, task_id)
    if task is None:
        return
    task.is_blocked = await is_task_blocked(session, task_id)
    await session.flush()


async def sync_blocked_flag(session: AsyncSession, task_id: UUID) -> None:
    """Public wrapper: recompute ``is_blocked`` from live dependency rows."""
    await _sync_blocked_flag(session, task_id)


async def enforce_not_blocked_for_move(session: AsyncSession, task: Task) -> None:
    """Revalidate blocking from the DAG; sync flag and raise if still blocked."""
    should_block = await is_task_blocked(session, task.id)
    if task.is_blocked != should_block:
        task.is_blocked = should_block
        await session.flush()
    if should_block:
        raise DependencyBlockedError("Task is blocked by dependencies")


async def add_dependency(
    session: AsyncSession,
    task_id: UUID,
    depends_on_id: UUID,
    project_id: UUID,
) -> tuple[TaskDependency, bool]:
    """Return ``(row, created)``; ``created=False`` when the edge already existed."""
    if task_id == depends_on_id:
        raise InvalidTransitionError("A task cannot depend on itself.")

    task = await TaskService.get(session, task_id, project_id=project_id)
    dep_task = await TaskService.get(session, depends_on_id, project_id=project_id)
    if task.project_id != dep_task.project_id:
        raise InvalidTransitionError("Both tasks must belong to the same project.")

    existing = await session.scalar(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == depends_on_id,
        )
    )
    if existing is not None:
        await _sync_blocked_flag(session, task_id)
        return existing, False

    adj = await _load_all_deps(session, project_id)
    if _has_cycle(str(task_id), str(depends_on_id), adj):
        raise CircularDependencyError("Circular dependency detected.")

    row = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id)
    session.add(row)
    await session.flush()
    await _sync_blocked_flag(session, task_id)
    return row, True


async def remove_dependency(
    session: AsyncSession,
    task_id: UUID,
    dep_id: UUID,
    *,
    project_id: UUID | None = None,
) -> None:
    if project_id is not None:
        await TaskService.get(session, task_id, project_id=project_id)

    result = await session.execute(
        delete(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_task_id == dep_id,
        )
    )
    if result.rowcount == 0:
        raise NotFoundError("Dependency not found.")
    await session.flush()
    await _sync_blocked_flag(session, task_id)


async def get_dependency_graph(session: AsyncSession, project_id: UUID) -> dict[str, list[dict[str, str]]]:
    tasks = await TaskService.list_by_project(session, project_id)
    nodes = [
        {"id": str(t.id), "title": t.title, "status": str(t.status)}
        for t in tasks
    ]
    rows = await session.execute(
        select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
        .join(Task, Task.id == TaskDependency.task_id)
        .where(Task.project_id == project_id)
    )
    edges = [
        {"from": str(task_id), "to": str(dep_id)}
        for task_id, dep_id in rows.all()
    ]
    return {"nodes": nodes, "edges": edges}


async def list_task_dependencies(
    session: AsyncSession,
    task_id: UUID,
    project_id: UUID,
) -> dict[str, object]:
    await TaskService.get(session, task_id, project_id=project_id)

    dep_rows = await session.execute(
        select(Task)
        .join(TaskDependency, TaskDependency.depends_on_task_id == Task.id)
        .where(TaskDependency.task_id == task_id)
        .order_by(Task.title)
    )
    depends_on_tasks = list(dep_rows.scalars().all())

    def _ref(t: Task) -> dict[str, str]:
        return {"task_id": str(t.id), "title": t.title, "status": str(t.status)}

    depends_on = [_ref(t) for t in depends_on_tasks]
    blocked_by = [_ref(t) for t in depends_on_tasks if t.status != TaskStatus.DONE]

    return {
        "task_id": str(task_id),
        "depends_on": depends_on,
        "blocked_by": blocked_by,
    }


async def ai_suggest_dependencies(
    session: AsyncSession,
    project_id: UUID,
) -> dict[str, int]:
    """Use LLM to analyse task titles/descriptions and automatically add logical dependencies."""
    from langchain_core.messages import HumanMessage  # lazy import

    from app.config import settings
    from app.services.llm import get_chat_model

    tasks = await TaskService.list_by_project(session, project_id)
    if len(tasks) < 2:
        return {"added": 0, "skipped": 0, "total_tasks": len(tasks)}

    # Build task list for the prompt
    task_lines = []
    for t in tasks:
        desc_snippet = f" | Mô tả: {t.description[:150]}" if t.description else ""
        task_lines.append(f'- id="{t.id}" | Tên: "{t.title}"{desc_snippet}')
    task_list_str = "\n".join(task_lines)

    prompt = f"""Bạn là chuyên gia phân tích quy trình phát triển phần mềm.
Dưới đây là danh sách các task trong dự án:

{task_list_str}

Hãy xác định các dependency LOGIC giữa các task — task nào cần phải hoàn thành TRƯỚC thì task kia mới có thể bắt đầu.

Quy tắc:
1. Chỉ thêm dependency khi thực sự cần thiết về mặt kỹ thuật hoặc logic nghiệp vụ
2. Không tạo cycle (vòng lặp)
3. Trả về ĐÚNG JSON array, không giải thích thêm

Format trả về (chỉ JSON):
[
  {{"task_id": "<uuid của task phụ thuộc>", "depends_on_id": "<uuid của task phải làm trước>"}},
  ...
]

Nếu không có dependency nào rõ ràng, trả về: []"""

    spec = f"{settings.coder_llm_provider}:{settings.groq_model or 'llama-3.3-70b-versatile'}"
    llm = get_chat_model(spec, temperature=0.0)

    try:
        result = await asyncio.to_thread(llm.invoke, [HumanMessage(content=prompt)])
        content: str = result.content if hasattr(result, "content") else str(result)
    except Exception:
        logger.exception("AI suggest dependencies LLM call failed")
        return {"added": 0, "skipped": 0, "total_tasks": len(tasks)}

    # Extract JSON array from response (LLM sometimes wraps in markdown)
    match = re.search(r"\[.*?\]", content, re.DOTALL)
    if not match:
        logger.warning("AI suggest dependencies: no JSON array found in LLM response")
        return {"added": 0, "skipped": 0, "total_tasks": len(tasks)}

    try:
        pairs: list[dict[str, str]] = json.loads(match.group())
    except json.JSONDecodeError:
        logger.warning("AI suggest dependencies: invalid JSON from LLM")
        return {"added": 0, "skipped": 0, "total_tasks": len(tasks)}

    valid_ids = {str(t.id) for t in tasks}
    added = 0
    skipped = 0

    for pair in pairs:
        task_id_str = str(pair.get("task_id", "")).strip()
        dep_id_str = str(pair.get("depends_on_id", "")).strip()
        if task_id_str not in valid_ids or dep_id_str not in valid_ids:
            skipped += 1
            continue
        try:
            _, created = await add_dependency(
                session, UUID(task_id_str), UUID(dep_id_str), project_id
            )
            added += int(created)
            if not created:
                skipped += 1
        except Exception:
            skipped += 1

    return {"added": added, "skipped": skipped, "total_tasks": len(tasks)}


async def unlock_dependents(session: AsyncSession, completed_task_id: UUID) -> list[UUID]:
    """After a task moves to ``done``, sync ``is_blocked`` on direct dependents."""
    dependent_ids = await session.scalars(
        select(TaskDependency.task_id).where(
            TaskDependency.depends_on_task_id == completed_task_id
        )
    )
    unlocked: list[UUID] = []
    changed = False
    for dep_task_id in dependent_ids.all():
        task = await session.get(Task, dep_task_id)
        if task is None:
            continue
        should_block = await is_task_blocked(session, dep_task_id)
        if task.is_blocked == should_block:
            continue
        if task.is_blocked and not should_block:
            unlocked.append(dep_task_id)
        task.is_blocked = should_block
        changed = True
    if changed:
        await session.flush()
    return unlocked
