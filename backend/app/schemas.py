from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ColumnCreate(BaseModel):
    name: str = Field(max_length=120)
    position: Optional[int] = None
    wip_limit: Optional[int] = None


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position: int
    wip_limit: Optional[int]


class ColumnUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=120)
    position: Optional[int] = None
    wip_limit: Optional[int] = None


class TaskAssigneeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    email: str


class TaskCreate(BaseModel):
    column_id: uuid.UUID
    title: str = Field(max_length=300)
    description: Optional[str] = None
    priority: str = Field(default="medium", max_length=32)
    status: Optional[str] = Field(default=None, max_length=64)
    est_hours: Optional[float] = None
    tags: Optional[list[str]] = None
    due_at: Optional[datetime] = None
    position: Optional[int] = None


class TaskUpdate(BaseModel):
    column_id: Optional[uuid.UUID] = None
    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=64)
    est_hours: Optional[float] = None
    tags: Optional[list[str]] = None
    due_at: Optional[datetime] = None
    position: Optional[int] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    column_id: uuid.UUID
    title: str
    description: Optional[str]
    priority: str
    status: str
    est_hours: Optional[float]
    tags: Optional[list[str]]
    due_at: Optional[datetime]
    position: int
    created_at: datetime
    updated_at: datetime
    assignees: list[TaskAssigneeOut] = []


class BoardCreate(BaseModel):
    title: str = Field(max_length=200)
    description: Optional[str] = None


class BoardUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None


class BoardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    description: Optional[str]
    created_at: datetime


class BoardDetailOut(BoardOut):
    columns: list[ColumnOut]
    tasks: list[TaskOut]
    members: list["BoardMemberOut"] = []


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    created_at: datetime


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UserSkillIn(BaseModel):
    skill_id: uuid.UUID
    level: str = Field(default="intermediate", max_length=64)


class UserSkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    skill_id: uuid.UUID
    level: str
    skill_name: Optional[str] = None


class UserSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    email: str


class BoardMemberAddIn(BaseModel):
    user_id: uuid.UUID


class BoardMemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str


class WorkloadOut(BaseModel):
    user_id: uuid.UUID
    open_tasks: int
    in_progress: int
    overdue: int
    est_hours_left: float


class AssignTaskIn(BaseModel):
    user_id: uuid.UUID


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    task_id: Optional[uuid.UUID]
    actor_id: uuid.UUID
    action: str
    details: Optional[dict[str, Any]]
    created_at: datetime


# === Agent endpoints ===

class AgentChatRequest(BaseModel):
    board_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)
    intent_hint: Optional[str] = None
    context: Optional[dict[str, Any]] = None
    locale: str = Field(default="vi", max_length=16, description="UI language: vi or en — agents reply in this language")


class AgentBreakdownRequest(BaseModel):
    board_id: uuid.UUID
    goal_text: str = Field(min_length=1, max_length=4000)
    target_column_id: Optional[uuid.UUID] = None
    locale: str = Field(default="vi", max_length=16)


class AgentSuggestAssigneeRequest(BaseModel):
    board_id: uuid.UUID
    task_id: uuid.UUID
    locale: str = Field(default="vi", max_length=16)


class AgentMonitorRequest(BaseModel):
    board_id: uuid.UUID
    locale: str = Field(default="vi", max_length=16)


class AgentReportRequest(BaseModel):
    board_id: uuid.UUID
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    locale: str = Field(default="vi", max_length=16)


class AgentRunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    step_index: int
    node: str
    input_summary: Optional[str]
    output_summary: Optional[str]
    payload: Optional[dict[str, Any]]
    latency_ms: Optional[int]
    started_at: datetime
    finished_at: Optional[datetime]


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    board_id: uuid.UUID
    actor_id: uuid.UUID
    intent: str
    status: str
    user_message: Optional[str]
    latency_ms: Optional[int]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    started_at: datetime
    finished_at: Optional[datetime]


class AgentRunDetailOut(AgentRunOut):
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    steps: list[AgentRunStepOut] = []
