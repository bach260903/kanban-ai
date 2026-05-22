"""Concrete handlers for the 8 agent tools defined in `agents/src/tools/registry.py`.

Each handler receives an explicit `ToolContext` (DB session + actor + board) and
returns plain dicts so they can be serialized to JSON for both LangChain tool
calling and WebSocket trace events.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    ActivityLog,
    Board,
    BoardMember,
    BoardMember,
    Column as ColumnModel,
    Skill,
    Task,
    TaskAssignment,
    User,
    UserSkill,
)
from app.services import vectorstore

log = logging.getLogger(__name__)


@dataclass
class ToolContext:
    db: AsyncSession
    actor_id: uuid.UUID
    board_id: uuid.UUID


async def _ensure_board(ctx: ToolContext) -> Board:
    res = await ctx.db.execute(
        select(Board)
        .outerjoin(BoardMember, BoardMember.board_id == Board.id)
        .where(Board.id == ctx.board_id, or_(Board.owner_id == ctx.actor_id, BoardMember.user_id == ctx.actor_id))
    )
    board = res.scalar_one_or_none()
    if board is None:
        raise PermissionError(f"Board {ctx.board_id} not accessible")
    return board


def _task_to_dict(t: Task) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "column_id": str(t.column_id),
        "due_at": t.due_at.isoformat() if t.due_at else None,
        "est_hours": t.est_hours,
        "tags": t.tags or [],
    }


async def query_tasks(
    ctx: ToolContext,
    *,
    column_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> dict[str, Any]:
    await _ensure_board(ctx)
    stmt = select(Task).where(Task.board_id == ctx.board_id)
    if column_id:
        try:
            stmt = stmt.where(Task.column_id == uuid.UUID(column_id))
        except ValueError:
            pass
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.order_by(Task.position).limit(max(1, min(int(limit or 50), 200)))
    res = await ctx.db.execute(stmt)
    tasks = [_task_to_dict(t) for t in res.scalars().all()]
    return {"tasks": tasks}


async def create_task(
    ctx: ToolContext,
    *,
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    column_id: Optional[str] = None,
    due_at: Optional[str] = None,
    est_hours: Optional[float] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    board = await _ensure_board(ctx)
    target_col_id: uuid.UUID
    if column_id:
        try:
            target_col_id = uuid.UUID(column_id)
        except ValueError as e:
            raise ValueError("Invalid column_id") from e
        col = await ctx.db.get(ColumnModel, target_col_id)
        if col is None or col.board_id != board.id:
            raise ValueError("column_id does not belong to this board")
    else:
        res = await ctx.db.execute(
            select(ColumnModel).where(ColumnModel.board_id == board.id).order_by(ColumnModel.position)
        )
        col = res.scalars().first()
        if col is None:
            raise ValueError("Board has no columns")
        target_col_id = col.id

    pos_res = await ctx.db.execute(
        select(Task).where(Task.column_id == target_col_id)
    )
    existing = list(pos_res.scalars().all())
    pos = max((t.position for t in existing), default=-1) + 1

    due_dt: Optional[datetime] = None
    if due_at:
        try:
            due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        except ValueError:
            due_dt = None

    task = Task(
        board_id=board.id,
        column_id=target_col_id,
        title=title,
        description=description,
        priority=priority or "medium",
        status="todo",
        est_hours=est_hours,
        tags=tags or None,
        due_at=due_dt,
        position=pos,
    )
    ctx.db.add(task)
    await ctx.db.flush()
    ctx.db.add(
        ActivityLog(
            board_id=board.id,
            task_id=task.id,
            actor_id=ctx.actor_id,
            action="task.create.agent",
            details={"title": title},
        )
    )
    await ctx.db.commit()
    await ctx.db.refresh(task)
    vectorstore.upsert_task(
        task_id=str(task.id),
        board_id=str(board.id),
        title=task.title,
        description=task.description or "",
        status=task.status,
        priority=task.priority,
        tags=task.tags or [],
    )
    return {"task": _task_to_dict(task)}


async def update_task_status(ctx: ToolContext, *, task_id: str, column_id: str) -> dict[str, Any]:
    board = await _ensure_board(ctx)
    try:
        tid = uuid.UUID(task_id)
        cid = uuid.UUID(column_id)
    except ValueError as e:
        raise ValueError("Invalid task_id or column_id") from e
    task = await ctx.db.get(Task, tid)
    if task is None or task.board_id != board.id:
        raise ValueError("Task not found")
    new_col = await ctx.db.get(ColumnModel, cid)
    if new_col is None or new_col.board_id != board.id:
        raise ValueError("column_id does not belong to this board")
    task.column_id = cid
    name = (new_col.name or "").lower()
    if "done" in name or "complete" in name or "ship" in name:
        task.status = "done"
    elif "progress" in name or "doing" in name or "review" in name:
        task.status = "in_progress"
    else:
        task.status = "todo"
    ctx.db.add(
        ActivityLog(
            board_id=board.id,
            task_id=task.id,
            actor_id=ctx.actor_id,
            action="task.move.agent",
            details={"to_column": new_col.name},
        )
    )
    await ctx.db.commit()
    await ctx.db.refresh(task)
    vectorstore.upsert_task(
        task_id=str(task.id),
        board_id=str(board.id),
        title=task.title,
        description=task.description or "",
        status=task.status,
        priority=task.priority,
        tags=task.tags or [],
    )
    return _task_to_dict(task)


async def assign_task(ctx: ToolContext, *, task_id: str, user_id: str) -> dict[str, Any]:
    board = await _ensure_board(ctx)
    try:
        tid = uuid.UUID(task_id)
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise ValueError("Invalid id") from e
    task = await ctx.db.get(Task, tid)
    if task is None or task.board_id != board.id:
        raise ValueError("Task not found")
    user = await ctx.db.get(User, uid)
    if user is None:
        raise ValueError("User not found")
    res = await ctx.db.execute(
        select(TaskAssignment).where(TaskAssignment.task_id == tid, TaskAssignment.user_id == uid)
    )
    existing = res.scalar_one_or_none()
    if existing is None:
        ctx.db.add(TaskAssignment(task_id=tid, user_id=uid))
    ctx.db.add(
        ActivityLog(
            board_id=board.id,
            task_id=task.id,
            actor_id=ctx.actor_id,
            action="task.assign.agent",
            details={"user_id": str(uid)},
        )
    )
    await ctx.db.commit()
    return {"task_id": str(tid), "user_id": str(uid), "assigned_at": datetime.now(timezone.utc).isoformat()}


async def get_user_workload(
    ctx: ToolContext,
    *,
    user_id: str,
    board_id: Optional[str] = None,
) -> dict[str, Any]:
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise ValueError("Invalid user_id") from e
    bid = ctx.board_id
    if board_id:
        try:
            bid = uuid.UUID(board_id)
        except ValueError:
            bid = ctx.board_id
    stmt = (
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(TaskAssignment.user_id == uid, Task.board_id == bid)
    )
    res = await ctx.db.execute(stmt)
    tasks = list(res.scalars().all())
    now = datetime.now(timezone.utc)
    open_tasks = [t for t in tasks if (t.status or "todo") != "done"]
    in_progress = [t for t in open_tasks if (t.status or "") == "in_progress"]
    overdue = [t for t in open_tasks if t.due_at and t.due_at < now]
    est = sum((t.est_hours or 0.0) for t in open_tasks)
    return {
        "user_id": str(uid),
        "open_tasks": len(open_tasks),
        "in_progress": len(in_progress),
        "overdue": len(overdue),
        "est_hours_left": round(est, 2),
    }


async def get_user_skills(ctx: ToolContext, *, user_id: str) -> dict[str, Any]:
    try:
        uid = uuid.UUID(user_id)
    except ValueError as e:
        raise ValueError("Invalid user_id") from e
    stmt = (
        select(UserSkill, Skill)
        .join(Skill, Skill.id == UserSkill.skill_id)
        .where(UserSkill.user_id == uid)
    )
    res = await ctx.db.execute(stmt)
    items = []
    for us, sk in res.all():
        items.append({"skill": sk.name, "level": us.level})
    return {"skills": items}


async def search_similar_tasks(
    ctx: ToolContext,
    *,
    query: str,
    top_k: int = 5,
    board_id: Optional[str] = None,
) -> dict[str, Any]:
    bid = board_id or str(ctx.board_id)
    matches = vectorstore.search_tasks(query, top_k=top_k, board_id=bid)
    return {"matches": matches}


async def get_board_activity(
    ctx: ToolContext,
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    await _ensure_board(ctx)
    stmt = select(ActivityLog).where(ActivityLog.board_id == ctx.board_id)
    if since:
        try:
            stmt = stmt.where(ActivityLog.created_at >= datetime.fromisoformat(since.replace("Z", "+00:00")))
        except ValueError:
            pass
    if until:
        try:
            stmt = stmt.where(ActivityLog.created_at <= datetime.fromisoformat(until.replace("Z", "+00:00")))
        except ValueError:
            pass
    stmt = stmt.order_by(ActivityLog.created_at.desc()).limit(max(1, min(int(limit or 100), 500)))
    res = await ctx.db.execute(stmt)
    events = []
    for ev in res.scalars().all():
        events.append({
            "id": str(ev.id),
            "actor_id": str(ev.actor_id),
            "action": ev.action,
            "task_id": str(ev.task_id) if ev.task_id else None,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "details": ev.details,
        })
    return {"events": events}


# Convenience: human-readable list of users on the board (used by Assigner)
async def list_board_members(ctx: ToolContext) -> list[dict[str, Any]]:
    """Return owner + explicit members added to this board."""
    board = await _ensure_board(ctx)
    res = await ctx.db.execute(select(User).where(User.id == board.owner_id))
    members = list(res.scalars().all())
    res2 = await ctx.db.execute(
        select(User)
        .join(BoardMember, BoardMember.user_id == User.id)
        .where(BoardMember.board_id == board.id)
    )
    existing = {m.id for m in members}
    for u in res2.scalars().all():
        if u.id not in existing:
            members.append(u)
            existing.add(u.id)
    return [
        {"id": str(u.id), "display_name": u.display_name, "email": u.email}
        for u in members
    ]


HANDLERS = {
    "query_tasks": query_tasks,
    "create_task": create_task,
    "update_task_status": update_task_status,
    "assign_task": assign_task,
    "get_user_workload": get_user_workload,
    "get_user_skills": get_user_skills,
    "search_similar_tasks": search_similar_tasks,
    "get_board_activity": get_board_activity,
}
