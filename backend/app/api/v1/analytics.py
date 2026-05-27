"""Analytics API (US6 / T085)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_leader_or_above
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.analytics import AnalyticsResponse, DashboardResponse
from app.services import analytics_service

router = APIRouter(tags=["analytics"])


def _parse_analytics_range(
    range_param: str,
    from_date: str | None,
    to_date: str | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if range_param == "7d":
        return now - timedelta(days=7), now
    if range_param == "30d":
        return now - timedelta(days=30), now
    if range_param == "custom":
        if not from_date or not to_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_date and to_date are required when range=custom",
            )
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format; use ISO 8601",
            ) from exc
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        if to_dt.tzinfo is None:
            to_dt = to_dt.replace(tzinfo=timezone.utc)
        if from_dt > to_dt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_date must be before or equal to to_date",
            )
        return from_dt, to_dt
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid range parameter; use 7d, 30d, or custom",
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardResponse:
    data = await analytics_service.get_dashboard_data(session, current_user.id)
    return DashboardResponse.model_validate(data)


@router.get("/projects/{project_id}/analytics", response_model=AnalyticsResponse)
async def get_project_analytics(
    project_id: UUID,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
    range_param: Annotated[str, Query(alias="range")] = "7d",
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
) -> AnalyticsResponse:
    from_dt, to_dt = _parse_analytics_range(range_param, from_date, to_date)
    data = await analytics_service.get_project_analytics(
        session,
        project_id,
        from_dt,
        to_dt,
    )
    return AnalyticsResponse.model_validate(data)
