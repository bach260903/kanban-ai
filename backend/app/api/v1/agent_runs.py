"""Agent run status polling (US4 / T037)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import NotFoundError
from app.middleware.auth import require_jwt
from app.models.agent_run import AgentRun
from app.schemas.agent_run import AgentRunResponse

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: UUID,
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AgentRunResponse:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise NotFoundError("Agent run not found.")
    return AgentRunResponse.model_validate(run)
