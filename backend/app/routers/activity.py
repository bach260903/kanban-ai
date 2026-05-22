from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import ActivityLog, Board, User
from app.schemas import ActivityLogOut

router = APIRouter(prefix="/boards/{board_id}/activity", tags=["activity"])


@router.get("", response_model=list[ActivityLogOut])
async def list_activity(
    board_id: uuid.UUID,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ActivityLog]:
    board = await db.get(Board, board_id)
    if board is None or board.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    stmt = select(ActivityLog).where(ActivityLog.board_id == board_id)
    if since is not None:
        stmt = stmt.where(ActivityLog.created_at >= since)
    if until is not None:
        stmt = stmt.where(ActivityLog.created_at <= until)
    stmt = stmt.order_by(ActivityLog.created_at.desc()).limit(max(1, min(limit, 500)))
    res = await db.execute(stmt)
    return list(res.scalars().all())
