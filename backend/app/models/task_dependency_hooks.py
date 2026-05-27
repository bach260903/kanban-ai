"""ORM hooks: keep ``is_blocked`` accurate when prerequisite tasks are deleted."""

from __future__ import annotations

from sqlalchemy import event, select, text

from app.models.task import Task
from app.models.task_dependency import TaskDependency

_RESYNC_KEY = "dependency_resync_task_ids"


def _sync_blocked_flag_sync(connection, task_id) -> None:
    blocked = connection.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM task_dependencies td
                INNER JOIN tasks t ON t.id = td.depends_on_task_id
                WHERE td.task_id = :task_id AND t.status <> 'done'
            )
            """
        ),
        {"task_id": task_id},
    ).scalar()
    connection.execute(
        text("UPDATE tasks SET is_blocked = :blocked WHERE id = :task_id"),
        {"blocked": bool(blocked), "task_id": task_id},
    )


@event.listens_for(Task, "before_delete")
def _task_before_delete(_mapper, connection, target: Task) -> None:
    dependent_ids = connection.execute(
        select(TaskDependency.task_id).where(
            TaskDependency.depends_on_task_id == target.id
        )
    ).scalars().all()
    if not dependent_ids:
        return
    pending = connection.info.setdefault(_RESYNC_KEY, set())
    pending.update(dependent_ids)


@event.listens_for(Task, "after_delete")
def _task_after_delete(_mapper, connection, _target: Task) -> None:
    pending = connection.info.pop(_RESYNC_KEY, set())
    for task_id in pending:
        _sync_blocked_flag_sync(connection, task_id)
