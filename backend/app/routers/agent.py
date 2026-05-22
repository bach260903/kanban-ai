from __future__ import annotations

import uuid
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.deps import get_current_user
from app.models import AgentRun, Board, BoardMember, User
from app.schemas import (
    AgentBreakdownRequest,
    AgentChatRequest,
    AgentMonitorRequest,
    AgentReportRequest,
    AgentRunDetailOut,
    AgentRunOut,
    AgentRunStepOut,
    AgentSuggestAssigneeRequest,
)
from app.services.agent_runner import run_agent

router = APIRouter(prefix="/agent", tags=["agent"])


async def _ensure_board(db: AsyncSession, board_id: uuid.UUID, user: User) -> Board:
    res = await db.execute(
        select(Board)
        .outerjoin(BoardMember, BoardMember.board_id == Board.id)
        .where(Board.id == board_id, or_(Board.owner_id == user.id, BoardMember.user_id == user.id))
    )
    board = res.scalar_one_or_none()
    if board is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Board not found")
    return board


async def _spawn(
    *,
    actor_id: uuid.UUID,
    board_id: uuid.UUID,
    intent_hint: str | None,
    user_message: str,
    extra: dict | None = None,
) -> AgentRun:
    """Run an agent in a fresh DB session so we can return early then continue work.

    For simplicity, we execute synchronously inline (small dataset). The
    front-end still relies on WebSocket events for streaming traces.
    """
    async with AsyncSessionLocal() as session:
        run = await run_agent(
            db=session,
            actor_id=actor_id,
            board_id=board_id,
            intent_hint=intent_hint,
            user_message=user_message,
            extra=extra,  # type: ignore[arg-type]
        )
        return run


def _is_low_signal_prompt(text: str) -> bool:
    s = (text or "").strip().lower()
    if len(s) < 10:
        return True
    words = set(re.findall(r"\w+", s))
    keywords = {"task", "board", "gán", "assign", "phân", "báo", "monitor", "hạn", "deadline", "cột"}
    return words.isdisjoint(keywords)


@router.post("/chat", response_model=AgentRunOut)
async def chat(
    body: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRun:
    await _ensure_board(db, body.board_id, user)
    if _is_low_signal_prompt(body.message):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "Yêu cầu còn mơ hồ. Hãy nêu rõ mục tiêu + tên task/cột + hành động cần AI làm "
                "(ví dụ: 'Gợi ý người làm task AI ở cột In progress')."
            ),
        )
    extra: dict = {"locale": (body.locale or "vi").strip().lower()}
    if body.context:
        extra["context"] = {**body.context, "locale": extra["locale"]}
    return await _spawn(
        actor_id=user.id,
        board_id=body.board_id,
        intent_hint=body.intent_hint,
        user_message=body.message,
        extra=extra,
    )


@router.post("/breakdown", response_model=AgentRunOut)
async def breakdown(
    body: AgentBreakdownRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRun:
    await _ensure_board(db, body.board_id, user)
    loc = (body.locale or "vi").strip().lower()
    return await _spawn(
        actor_id=user.id,
        board_id=body.board_id,
        intent_hint="plan",
        user_message=body.goal_text,
        extra={
            "target_column_id": str(body.target_column_id) if body.target_column_id else None,
            "locale": loc,
        },
    )


@router.post("/suggest-assignee", response_model=AgentRunOut)
async def suggest_assignee(
    body: AgentSuggestAssigneeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRun:
    await _ensure_board(db, body.board_id, user)
    loc = (body.locale or "vi").strip().lower()
    msg = (
        f"Gợi ý người phù hợp để gán task {body.task_id}"
        if loc.startswith("vi")
        else f"Suggest an assignee for task {body.task_id}"
    )
    return await _spawn(
        actor_id=user.id,
        board_id=body.board_id,
        intent_hint="assign",
        user_message=msg,
        extra={"task_id": str(body.task_id), "locale": loc},
    )


@router.post("/monitor", response_model=AgentRunOut)
async def monitor(
    body: AgentMonitorRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRun:
    await _ensure_board(db, body.board_id, user)
    loc = (body.locale or "vi").strip().lower()
    um = "Kiểm tra nút thắn, quá hạn và WIP trên board này" if loc.startswith("vi") else "Detect bottlenecks on this board"
    return await _spawn(
        actor_id=user.id,
        board_id=body.board_id,
        intent_hint="monitor",
        user_message=um,
        extra={"locale": loc},
    )


@router.post("/report", response_model=AgentRunOut)
async def report(
    body: AgentReportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRun:
    await _ensure_board(db, body.board_id, user)
    loc = (body.locale or "vi").strip().lower()
    extra: dict = {"locale": loc}
    if body.since:
        extra["since"] = body.since.isoformat()
    if body.until:
        extra["until"] = body.until.isoformat()
    um = (
        "Tạo báo cáo stand-up / tóm tắt hoạt động board này bằng tiếng Việt"
        if loc.startswith("vi")
        else "Generate a stand-up report for this board"
    )
    return await _spawn(
        actor_id=user.id,
        board_id=body.board_id,
        intent_hint="report",
        user_message=um,
        extra=extra,
    )


@router.get("/runs/{run_id}", response_model=AgentRunDetailOut)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentRunDetailOut:
    res = await db.execute(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.actor_id == user.id).options(selectinload(AgentRun.steps))
    )
    run = res.scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    steps = [AgentRunStepOut.model_validate(s) for s in sorted(run.steps, key=lambda s: s.step_index)]
    return AgentRunDetailOut(
        id=run.id,
        board_id=run.board_id,
        actor_id=run.actor_id,
        intent=run.intent,
        status=run.status,
        user_message=run.user_message,
        latency_ms=run.latency_ms,
        tokens_in=run.tokens_in,
        tokens_out=run.tokens_out,
        cost_usd=run.cost_usd,
        started_at=run.started_at,
        finished_at=run.finished_at,
        result=run.result,
        error=run.error,
        steps=steps,
    )


@router.get("/runs", response_model=list[AgentRunOut])
async def list_runs(
    board_id: uuid.UUID | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentRun]:
    stmt = select(AgentRun).where(AgentRun.actor_id == user.id)
    if board_id is not None:
        stmt = stmt.where(AgentRun.board_id == board_id)
    stmt = stmt.order_by(AgentRun.started_at.desc()).limit(max(1, min(limit, 200)))
    res = await db.execute(stmt)
    return list(res.scalars().all())
