"""Tool registry skeleton.

Phase 2 only declares signatures + permission flags; Phase 3 wires real DB calls
through the FastAPI dependency layer. Schema is the source of truth for the
``Validation layer'' described in `docs/phase2-agent-architecture.md` §B.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field


Permission = Literal["read", "write"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: Permission
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Optional[Callable[..., Any]] = field(default=None)


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> ToolSpec:
    if spec.name in TOOL_REGISTRY:
        raise ValueError(f"Tool already registered: {spec.name}")
    TOOL_REGISTRY[spec.name] = spec
    return spec


class QueryTasksIn(BaseModel):
    board_id: str
    column_id: Optional[str] = None
    status: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)


class TaskBrief(BaseModel):
    id: str
    title: str
    status: Optional[str] = None
    priority: str = "medium"
    column_id: str
    due_at: Optional[str] = None


class QueryTasksOut(BaseModel):
    tasks: list[TaskBrief]


class CreateTaskIn(BaseModel):
    board_id: str
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_at: Optional[str] = None
    est_hours: Optional[float] = None
    column_id: Optional[str] = None


class CreateTaskOut(BaseModel):
    task: TaskBrief


class UpdateTaskStatusIn(BaseModel):
    task_id: str
    column_id: str


class AssignTaskIn(BaseModel):
    task_id: str
    user_id: str


class AssignTaskOut(BaseModel):
    task_id: str
    user_id: str
    assigned_at: str


class GetUserWorkloadIn(BaseModel):
    user_id: str
    board_id: Optional[str] = None


class GetUserWorkloadOut(BaseModel):
    open_tasks: int
    overdue: int
    in_progress: int
    est_hours_left: float


class GetUserSkillsIn(BaseModel):
    user_id: str


class UserSkill(BaseModel):
    skill: str
    level: str


class GetUserSkillsOut(BaseModel):
    skills: list[UserSkill]


class SearchSimilarTasksIn(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    board_id: Optional[str] = None


class SimilarTask(BaseModel):
    task_id: str
    score: float
    snippet: str


class SearchSimilarTasksOut(BaseModel):
    matches: list[SimilarTask]


class GetBoardActivityIn(BaseModel):
    board_id: str
    since: Optional[str] = None
    until: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=500)


class ActivityEvent(BaseModel):
    id: str
    actor_id: str
    action: str
    task_id: Optional[str] = None
    created_at: str
    details: Optional[dict[str, Any]] = None


class GetBoardActivityOut(BaseModel):
    events: list[ActivityEvent]


# Built-in declarations (handlers wired in Phase 3).
register_tool(
    ToolSpec(
        name="query_tasks",
        description="List tasks in a board with filters.",
        permission="read",
        input_model=QueryTasksIn,
        output_model=QueryTasksOut,
    )
)
register_tool(
    ToolSpec(
        name="create_task",
        description="Create a task in a board (under default column if omitted).",
        permission="write",
        input_model=CreateTaskIn,
        output_model=CreateTaskOut,
    )
)
register_tool(
    ToolSpec(
        name="update_task_status",
        description="Move a task to another column.",
        permission="write",
        input_model=UpdateTaskStatusIn,
        output_model=TaskBrief,
    )
)
register_tool(
    ToolSpec(
        name="assign_task",
        description="Assign a user to a task.",
        permission="write",
        input_model=AssignTaskIn,
        output_model=AssignTaskOut,
    )
)
register_tool(
    ToolSpec(
        name="get_user_workload",
        description="Aggregate workload metrics for a user.",
        permission="read",
        input_model=GetUserWorkloadIn,
        output_model=GetUserWorkloadOut,
    )
)
register_tool(
    ToolSpec(
        name="get_user_skills",
        description="Return skills + level for a user.",
        permission="read",
        input_model=GetUserSkillsIn,
        output_model=GetUserSkillsOut,
    )
)
register_tool(
    ToolSpec(
        name="search_similar_tasks",
        description="Vector search across previously-seen tasks.",
        permission="read",
        input_model=SearchSimilarTasksIn,
        output_model=SearchSimilarTasksOut,
    )
)
register_tool(
    ToolSpec(
        name="get_board_activity",
        description="Recent activity log slice for a board.",
        permission="read",
        input_model=GetBoardActivityIn,
        output_model=GetBoardActivityOut,
    )
)


def list_tools() -> list[str]:
    return sorted(TOOL_REGISTRY.keys())
