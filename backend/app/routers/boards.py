from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    ActivityLog,
    Board,
    BoardMember,
    Column,
    Task,
    TaskAssignment,
    User,
)
from app.schemas import (
    BoardCreate,
    BoardDetailOut,
    BoardMemberAddIn,
    BoardMemberOut,
    BoardOut,
    BoardUpdate,
    ColumnCreate,
    ColumnOut,
    ColumnUpdate,
    TaskAssigneeOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services import vectorstore

router = APIRouter(prefix="/boards", tags=["boards"])

DEFAULT_COLUMNS = (
    ("To do", None, "todo"),
    ("In progress", 5, "in_progress"),
    ("Done", None, "done"),
)


async def _log(
    db: AsyncSession,
    *,
    board_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    task_id: Optional[uuid.UUID] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        ActivityLog(
            board_id=board_id,
            task_id=task_id,
            actor_id=actor_id,
            action=action,
            details=details,
        )
    )


def _board_query(board_id: uuid.UUID, user_id: uuid.UUID):
    return (
        select(Board)
        .outerjoin(BoardMember, BoardMember.board_id == Board.id)
        .where(Board.id == board_id, or_(Board.owner_id == user_id, BoardMember.user_id == user_id))
        .options(
            selectinload(Board.owner),
            selectinload(Board.members).selectinload(BoardMember.user),
            selectinload(Board.columns),
            selectinload(Board.tasks).selectinload(Task.assignments).selectinload(TaskAssignment.user),
        )
    )


async def _can_access_board(db: AsyncSession, board_id: uuid.UUID, user_id: uuid.UUID) -> Board | None:
    board = await db.get(Board, board_id)
    if board is None:
        return None
    if board.owner_id == user_id:
        return board
    member = await db.execute(
        select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == user_id)
    )
    return board if member.scalar_one_or_none() is not None else None


def _task_to_out(t: Task) -> TaskOut:
    return TaskOut(
        id=t.id,
        board_id=t.board_id,
        column_id=t.column_id,
        title=t.title,
        description=t.description,
        priority=t.priority,
        status=t.status,
        est_hours=t.est_hours,
        tags=t.tags,
        due_at=t.due_at,
        position=t.position,
        created_at=t.created_at,
        updated_at=t.updated_at,
        assignees=[
            TaskAssigneeOut(user_id=a.user_id, display_name=a.user.display_name, email=a.user.email)
            for a in (t.assignments or [])
            if a.user is not None
        ],
    )


def _members_to_out(board: Board) -> list[BoardMemberOut]:
    seen: set[str] = set()
    out: list[BoardMemberOut] = []
    if board.owner is not None:
        out.append(
            BoardMemberOut(user_id=board.owner.id, display_name=board.owner.display_name, email=board.owner.email)
        )
        seen.add(str(board.owner.id))
    for m in (board.members or []):
        if m.user is None:
            continue
        uid = str(m.user.id)
        if uid in seen:
            continue
        seen.add(uid)
        out.append(BoardMemberOut(user_id=m.user.id, display_name=m.user.display_name, email=m.user.email))
    return out


@router.get("", response_model=list[BoardOut])
async def list_boards(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Board]:
    result = await db.execute(
        select(Board)
        .outerjoin(BoardMember, BoardMember.board_id == Board.id)
        .where(or_(Board.owner_id == user.id, BoardMember.user_id == user.id))
        .order_by(Board.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=BoardDetailOut, status_code=status.HTTP_201_CREATED)
async def create_board(
    body: BoardCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BoardDetailOut:
    board = Board(owner_id=user.id, title=body.title, description=body.description)
    db.add(board)
    await db.flush()
    for i, (name, wip, _status) in enumerate(DEFAULT_COLUMNS):
        db.add(Column(board_id=board.id, name=name, position=i, wip_limit=wip))
    await _log(db, board_id=board.id, actor_id=user.id, action="board.create", details={"title": body.title})
    await db.commit()
    res = await db.execute(_board_query(board.id, user.id))
    b = res.scalar_one()
    cols = sorted(b.columns, key=lambda c: c.position)
    tasks = sorted(b.tasks, key=lambda t: (t.column_id, t.position))
    return BoardDetailOut(
        id=b.id,
        owner_id=b.owner_id,
        title=b.title,
        description=b.description,
        created_at=b.created_at,
        columns=[ColumnOut.model_validate(c) for c in cols],
        tasks=[_task_to_out(t) for t in tasks],
        members=_members_to_out(b),
    )


@router.get("/{board_id}", response_model=BoardDetailOut)
async def get_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BoardDetailOut:
    result = await db.execute(_board_query(board_id, user.id))
    board = result.scalar_one_or_none()
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    cols = sorted(board.columns, key=lambda c: c.position)
    tasks = sorted(board.tasks, key=lambda t: (t.column_id, t.position))
    return BoardDetailOut(
        id=board.id,
        owner_id=board.owner_id,
        title=board.title,
        description=board.description,
        created_at=board.created_at,
        columns=[ColumnOut.model_validate(c) for c in cols],
        tasks=[_task_to_out(t) for t in tasks],
        members=_members_to_out(board),
    )


@router.get("/{board_id}/members", response_model=list[BoardMemberOut])
async def list_board_members(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BoardMemberOut]:
    result = await db.execute(_board_query(board_id, user.id))
    board = result.scalar_one_or_none()
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    return _members_to_out(board)


@router.post("/{board_id}/members", response_model=list[BoardMemberOut])
async def add_board_member(
    board_id: uuid.UUID,
    body: BoardMemberAddIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BoardMemberOut]:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    target = await db.get(User, body.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id != board.owner_id:
        exists = await db.execute(
            select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == target.id)
        )
        if exists.scalar_one_or_none() is None:
            db.add(BoardMember(board_id=board_id, user_id=target.id))
    await _log(
        db,
        board_id=board_id,
        actor_id=user.id,
        action="board.member.add",
        details={"user_id": str(target.id)},
    )
    await db.commit()
    refreshed = (await db.execute(_board_query(board_id, user.id))).scalar_one()
    return _members_to_out(refreshed)


@router.delete("/{board_id}/members/{member_user_id}", response_model=list[BoardMemberOut])
async def remove_board_member(
    board_id: uuid.UUID,
    member_user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[BoardMemberOut]:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    if member_user_id == board.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot remove board owner")
    res = await db.execute(
        select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == member_user_id)
    )
    membership = res.scalar_one_or_none()
    if membership is not None:
        await db.delete(membership)
        ass_res = await db.execute(
            select(TaskAssignment)
            .join(Task, Task.id == TaskAssignment.task_id)
            .where(Task.board_id == board_id, TaskAssignment.user_id == member_user_id)
        )
        for a in ass_res.scalars().all():
            await db.delete(a)
    await _log(
        db,
        board_id=board_id,
        actor_id=user.id,
        action="board.member.remove",
        details={"user_id": str(member_user_id)},
    )
    await db.commit()
    refreshed = (await db.execute(_board_query(board_id, user.id))).scalar_one()
    return _members_to_out(refreshed)


@router.patch("/{board_id}", response_model=BoardOut)
async def update_board(
    board_id: uuid.UUID,
    body: BoardUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Board:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    if body.title is not None:
        board.title = body.title
    if body.description is not None:
        board.description = body.description
    await _log(db, board_id=board.id, actor_id=user.id, action="board.update")
    await db.commit()
    await db.refresh(board)
    return board


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    await db.delete(board)
    await db.commit()


@router.post("/{board_id}/columns", response_model=ColumnOut, status_code=status.HTTP_201_CREATED)
async def create_column(
    board_id: uuid.UUID,
    body: ColumnCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Column:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    pos = body.position
    if pos is None:
        result = await db.execute(select(Column).where(Column.board_id == board_id))
        existing = list(result.scalars().all())
        pos = max((c.position for c in existing), default=-1) + 1
    col = Column(
        board_id=board_id,
        name=body.name,
        position=pos,
        wip_limit=body.wip_limit,
    )
    db.add(col)
    await _log(db, board_id=board_id, actor_id=user.id, action="column.create", details={"name": body.name})
    await db.commit()
    await db.refresh(col)
    return col


@router.patch("/{board_id}/columns/{column_id}", response_model=ColumnOut)
async def update_column(
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    body: ColumnUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Column:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    col = await db.get(Column, column_id)
    if col is None or col.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Column not found")
    if body.name is not None:
        col.name = body.name
    if body.position is not None:
        col.position = body.position
    if body.wip_limit is not None:
        col.wip_limit = body.wip_limit
    await _log(db, board_id=board_id, actor_id=user.id, action="column.update")
    await db.commit()
    await db.refresh(col)
    return col


@router.delete("/{board_id}/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    col = await db.get(Column, column_id)
    if col is None or col.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Column not found")
    await db.delete(col)
    await db.commit()


def _derive_status(column_name: str | None) -> str:
    name = (column_name or "").lower()
    if "done" in name or "complete" in name or "ship" in name:
        return "done"
    if "progress" in name or "doing" in name or "review" in name:
        return "in_progress"
    return "todo"


@router.post("/{board_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    board_id: uuid.UUID,
    body: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    board = await _can_access_board(db, board_id, user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    col = await db.get(Column, body.column_id)
    if col is None or col.board_id != board_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid column for this board")
    pos = body.position
    if pos is None:
        result = await db.execute(select(Task).where(Task.column_id == body.column_id))
        tasks_in_col = list(result.scalars().all())
        pos = max((t.position for t in tasks_in_col), default=-1) + 1
    task = Task(
        board_id=board_id,
        column_id=body.column_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status=body.status or _derive_status(col.name),
        est_hours=body.est_hours,
        tags=body.tags,
        due_at=body.due_at,
        position=pos,
    )
    db.add(task)
    await db.flush()
    await _log(
        db,
        board_id=board_id,
        actor_id=user.id,
        action="task.create",
        task_id=task.id,
        details={"title": body.title},
    )
    await db.commit()
    res = await db.execute(
        select(Task).where(Task.id == task.id).options(selectinload(Task.assignments).selectinload(TaskAssignment.user))
    )
    t = res.scalar_one()
    vectorstore.upsert_task(
        task_id=str(t.id),
        board_id=str(t.board_id),
        title=t.title,
        description=t.description or "",
        status=t.status,
        priority=t.priority,
        tags=t.tags or [],
    )
    return _task_to_out(t)


@router.patch("/{board_id}/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    body: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    board = await _can_access_board(db, board_id, user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    task = await db.get(Task, task_id)
    if task is None or task.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    if body.column_id is not None:
        new_col = await db.get(Column, body.column_id)
        if new_col is None or new_col.board_id != board_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid column")
        task.column_id = body.column_id
        if body.status is None:
            task.status = _derive_status(new_col.name)
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.priority is not None:
        task.priority = body.priority
    if body.status is not None:
        task.status = body.status
    if body.est_hours is not None:
        task.est_hours = body.est_hours
    if body.tags is not None:
        task.tags = body.tags
    if body.due_at is not None:
        task.due_at = body.due_at
    if body.position is not None:
        task.position = body.position
    await _log(db, board_id=board_id, actor_id=user.id, action="task.update", task_id=task.id)
    await db.commit()
    res = await db.execute(
        select(Task).where(Task.id == task.id).options(selectinload(Task.assignments).selectinload(TaskAssignment.user))
    )
    t = res.scalar_one()
    vectorstore.upsert_task(
        task_id=str(t.id),
        board_id=str(t.board_id),
        title=t.title,
        description=t.description or "",
        status=t.status,
        priority=t.priority,
        tags=t.tags or [],
    )
    return _task_to_out(t)


@router.delete("/{board_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    board = await _can_access_board(db, board_id, user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    task = await db.get(Task, task_id)
    if task is None or task.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    await db.delete(task)
    await db.commit()
    vectorstore.delete_task(str(task_id))


@router.post("/{board_id}/tasks/{task_id}/assign", response_model=TaskOut)
async def assign_user(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    """Attach a user to a task (idempotent)."""
    board = await _can_access_board(db, board_id, user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    task = await db.get(Task, task_id)
    if task is None or task.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    try:
        uid = uuid.UUID(str(body.get("user_id")))
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="user_id required")
    target = await db.get(User, uid)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    if uid != board.owner_id:
        member_res = await db.execute(
            select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.user_id == uid)
        )
        if member_res.scalar_one_or_none() is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="User is not a member of this board")
    res = await db.execute(
        select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.user_id == uid)
    )
    if res.scalar_one_or_none() is None:
        db.add(TaskAssignment(task_id=task_id, user_id=uid))
        await _log(db, board_id=board_id, actor_id=user.id, action="task.assign",
                   task_id=task_id, details={"user_id": str(uid)})
        await db.commit()
    res = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.assignments).selectinload(TaskAssignment.user))
    )
    return _task_to_out(res.scalar_one())


@router.delete("/{board_id}/tasks/{task_id}/assign/{user_id}", response_model=TaskOut)
async def unassign_user(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    board = await _can_access_board(db, board_id, user.id)
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    res = await db.execute(
        select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.user_id == user_id)
    )
    a = res.scalar_one_or_none()
    if a is not None:
        await db.delete(a)
        await _log(db, board_id=board_id, actor_id=user.id, action="task.unassign",
                   task_id=task_id, details={"user_id": str(user_id)})
        await db.commit()
    res2 = await db.execute(
        select(Task).where(Task.id == task_id).options(selectinload(Task.assignments).selectinload(TaskAssignment.user))
    )
    t = res2.scalar_one_or_none()
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_to_out(t)
