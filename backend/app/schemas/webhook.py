"""Pydantic schemas for webhooks (US7 / T098)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WebhookCreate(BaseModel):
    url: str = Field(..., min_length=1)
    secret: str | None = None
    events: list[str] = Field(..., min_length=1)


class WebhookUpdate(BaseModel):
    url: str | None = None
    secret: str | None = None
    events: list[str] | None = None
    enabled: bool | None = None


class WebhookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    events: list[str]
    enabled: bool
    created_at: datetime


class TestWebhookResponse(BaseModel):
    delivered: bool
    http_status: int | None
    response_time_ms: int
