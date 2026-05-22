from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import ActivityLog, Board, Comment, Task, User
from app.schemas import CommentCreate, CommentOut
from app.services import vectorstore

router = APIRouter(prefix="/boards/{board_id}/tasks/{task_id}/comments", tags=["comments"])


async def _ensure(db: AsyncSession, board_id: uuid.UUID, task_id: uuid.UUID, user: User) -> Task:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    task = await db.get(Task, task_id)
    if task is None or task.board_id != board_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.get("", response_model=list[CommentOut])
async def list_comments(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Comment]:
    await _ensure(db, board_id, task_id, user)
    res = await db.execute(
        select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at.asc())
    )
    return list(res.scalars().all())


@router.post("", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
async def create_comment(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Comment:
    await _ensure(db, board_id, task_id, user)
    c = Comment(task_id=task_id, author_id=user.id, body=body.body)
    db.add(c)
    db.add(
        ActivityLog(
            board_id=board_id,
            task_id=task_id,
            actor_id=user.id,
            action="task.comment",
            details={"length": len(body.body)},
        )
    )
    await db.commit()
    await db.refresh(c)
    vectorstore.upsert_comment(
        comment_id=str(c.id),
        task_id=str(task_id),
        board_id=str(board_id),
        body=c.body,
        author_id=str(user.id),
    )
    return c


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    board_id: uuid.UUID,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await _ensure(db, board_id, task_id, user)
    c = await db.get(Comment, comment_id)
    if c is None or c.task_id != task_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if c.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot delete others' comment")
    await db.delete(c)
    await db.commit()
