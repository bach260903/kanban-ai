from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Skill, User
from app.schemas import SkillCreate, SkillOut

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("", response_model=list[SkillOut])
async def list_skills(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Skill]:
    res = await db.execute(select(Skill).order_by(Skill.name.asc()))
    return list(res.scalars().all())


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Skill:
    res = await db.execute(select(Skill).where(Skill.name == body.name.lower().strip()))
    existing = res.scalar_one_or_none()
    if existing is not None:
        return existing
    s = Skill(name=body.name.lower().strip())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s
