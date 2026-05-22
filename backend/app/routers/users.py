from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Board,
    Skill,
    Task,
    TaskAssignment,
    User,
    UserSkill,
)
from app.schemas import (
    UserSkillIn,
    UserSkillOut,
    UserSummaryOut,
    WorkloadOut,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserSummaryOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[User]:
    res = await db.execute(select(User).order_by(User.display_name.asc()))
    return list(res.scalars().all())


@router.get("/me", response_model=UserSummaryOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/{user_id}/skills", response_model=list[UserSkillOut])
async def get_user_skills(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[UserSkillOut]:
    target = await db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    res = await db.execute(
        select(UserSkill, Skill)
        .join(Skill, Skill.id == UserSkill.skill_id)
        .where(UserSkill.user_id == user_id)
    )
    out: list[UserSkillOut] = []
    for us, sk in res.all():
        out.append(UserSkillOut(user_id=us.user_id, skill_id=us.skill_id, level=us.level, skill_name=sk.name))
    return out


@router.put("/{user_id}/skills", response_model=list[UserSkillOut])
async def set_user_skills(
    user_id: uuid.UUID,
    items: list[UserSkillIn],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[UserSkillOut]:
    if user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's skills")
    res = await db.execute(select(UserSkill).where(UserSkill.user_id == user_id))
    for us in res.scalars().all():
        await db.delete(us)
    await db.flush()
    for item in items:
        sk = await db.get(Skill, item.skill_id)
        if sk is None:
            continue
        db.add(UserSkill(user_id=user_id, skill_id=item.skill_id, level=item.level))
    await db.commit()
    return await get_user_skills(user_id, db, user)  # type: ignore[return-value]


@router.get("/{user_id}/workload", response_model=WorkloadOut)
async def workload(
    user_id: uuid.UUID,
    board_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> WorkloadOut:
    stmt = (
        select(Task)
        .join(TaskAssignment, TaskAssignment.task_id == Task.id)
        .where(TaskAssignment.user_id == user_id)
    )
    if board_id is not None:
        stmt = stmt.where(Task.board_id == board_id)
    res = await db.execute(stmt)
    tasks = list(res.scalars().all())
    now = datetime.now(timezone.utc)
    open_tasks = [t for t in tasks if (t.status or "todo") != "done"]
    in_progress = [t for t in open_tasks if (t.status or "") == "in_progress"]
    overdue = [t for t in open_tasks if t.due_at and t.due_at < now]
    est = sum((t.est_hours or 0.0) for t in open_tasks)
    return WorkloadOut(
        user_id=user_id,
        open_tasks=len(open_tasks),
        in_progress=len(in_progress),
        overdue=len(overdue),
        est_hours_left=round(est, 2),
    )
