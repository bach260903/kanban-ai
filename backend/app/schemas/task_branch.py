"""API schemas for task Git branches (US15 / T104)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.task_branch import TaskBranchStatus


class TaskBranchResponse(BaseModel):
    """``GET /tasks/{task_id}/branch`` payload."""

    model_config = ConfigDict(from_attributes=True)

    task_id: UUID
    branch_name: str
    status: TaskBranchStatus
    created_at: datetime
    merged_at: datetime | None
