"""Webhooks API (US7 / T099)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_any_member, require_leader_or_above
from app.exceptions import NotFoundError
from app.models.project_member import ProjectMember
from app.models.user import User
from app.models.webhook import WebhookConfig, WebhookDelivery
from app.schemas.webhook import (
    TestWebhookResponse,
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookUpdate,
)
from app.services import webhook_service

router = APIRouter(tags=["webhooks"])

VALID_WEBHOOK_EVENTS = frozenset({"task.needs_review", "task.done", "agent.error"})


def _validate_events(events: list[str]) -> None:
    if not events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one webhook event is required.",
        )
    invalid = [event for event in events if event not in VALID_WEBHOOK_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook event type(s): {', '.join(invalid)}",
        )


async def _get_project_webhook(
    session: AsyncSession,
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
) -> WebhookConfig:
    config = await session.scalar(
        select(WebhookConfig).where(
            WebhookConfig.id == webhook_id,
            WebhookConfig.project_id == project_id,
        )
    )
    if config is None:
        raise NotFoundError("Webhook not found.")
    return config


@router.get("/projects/{project_id}/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(
    project_id: uuid.UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[WebhookResponse]:
    rows = (
        await session.scalars(
            select(WebhookConfig)
            .where(WebhookConfig.project_id == project_id)
            .order_by(WebhookConfig.created_at.desc())
        )
    ).all()
    return [WebhookResponse.model_validate(row) for row in rows]


@router.post(
    "/projects/{project_id}/webhooks",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    project_id: uuid.UUID,
    body: WebhookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    _validate_events(body.events)
    config = WebhookConfig(
        project_id=project_id,
        url=body.url.strip(),
        secret=body.secret or None,
        events=body.events,
        enabled=True,
        created_by=current_user.id,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return WebhookResponse.model_validate(config)


@router.patch("/projects/{project_id}/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    config = await _get_project_webhook(session, project_id, webhook_id)
    if body.events is not None:
        _validate_events(body.events)
        config.events = body.events
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.url is not None:
        config.url = body.url.strip()
    if body.secret is not None:
        config.secret = body.secret or None
    await session.commit()
    await session.refresh(config)
    return WebhookResponse.model_validate(config)


@router.delete(
    "/projects/{project_id}/webhooks/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_webhook(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    config = await _get_project_webhook(session, project_id, webhook_id)
    await session.delete(config)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/webhooks/{webhook_id}/test",
    response_model=TestWebhookResponse,
)
async def test_webhook(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TestWebhookResponse:
    config = await _get_project_webhook(session, project_id, webhook_id)
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook is disabled.",
        )
    result = await webhook_service.test_webhook(session, webhook_id)
    # Always return 200 — let the frontend display success/failure details
    return TestWebhookResponse(**result)


@router.get(
    "/projects/{project_id}/webhooks/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
)
async def list_deliveries(
    project_id: uuid.UUID,
    webhook_id: uuid.UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[WebhookDeliveryResponse]:
    """Return the last N delivery attempts for a webhook (newest first)."""
    config = await _get_project_webhook(session, project_id, webhook_id)
    rows = (
        await session.scalars(
            select(WebhookDelivery)
            .where(WebhookDelivery.webhook_config_id == config.id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(min(limit, 50))
        )
    ).all()
    return [WebhookDeliveryResponse.model_validate(row) for row in rows]
