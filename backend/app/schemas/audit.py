"""Schemas for audit log read API (T071)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit_log import AuditLogResult


class AuditLogListItem(BaseModel):
    """Single row for read-only audit table (agent + action + time + result)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: str
    agent_version: str
    action_type: str
    action_description: str
    timestamp: datetime
    input_refs: list[str]
    output_refs: list[str]
    result: AuditLogResult
    project_id: UUID | None = None
    task_id: UUID | None = None
    # Resolved display names (not in DB — populated by the API endpoint)
    task_title: str | None = None


class AuditLogsPageResponse(BaseModel):
    items: list[AuditLogListItem]
    total: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
