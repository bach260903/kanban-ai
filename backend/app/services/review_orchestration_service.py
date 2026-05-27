"""Coder ↔ reviewer loop until approve_suggested, then hand off to PO (review column)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.stream_event import StreamEventType
from app.models.task import Task, TaskStatus
from app.services.diff_service import DiffService
from app.services.kanban_service import KanbanService
from app.services.task_service import TaskService
from app.websocket.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


def _status_event_content(body: dict[str, Any]) -> str:
    return json.dumps(body, separators=(",", ":"))


def _feedback_from_review_result(result: dict) -> str:
    summary = str(result.get("summary", "")).strip()
    findings = result.get("findings")
    lines = [summary] if summary else []
    if isinstance(findings, list):
        for item in findings[:12]:
            if isinstance(item, dict):
                sev = str(item.get("severity", "info"))
                msg = str(item.get("message", "")).strip()
                if msg:
                    lines.append(f"- [{sev}] {msg}")
    body = "\n".join(lines).strip()
    return body or "Reviewer requested changes. Address the diff issues and try again."


class ReviewOrchestrationService:
    @staticmethod
    async def count_reviewer_rounds(session: AsyncSession, task_id: UUID) -> int:
        n = await session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(
                AgentRun.task_id == task_id,
                AgentRun.agent_type == AgentType.REVIEWER,
                AgentRun.status == AgentRunStatus.SUCCESS,
            )
        )
        return int(n or 0)

    @staticmethod
    async def apply_reviewer_result(
        project_id: UUID,
        task_id: UUID,
        *,
        diff_id: UUID,
        result: dict,
    ) -> None:
        """Run after reviewer agent completes: revise via coder or open PO review."""
        restart: tuple[UUID, str] | None = None
        async with async_session_maker() as session:
            try:
                restart = await ReviewOrchestrationService._apply_in_session(
                    session,
                    project_id=project_id,
                    task_id=task_id,
                    diff_id=diff_id,
                    result=result,
                )
                await session.commit()
            except Exception:
                logger.exception("Review orchestration failed task_id=%s", task_id)
                await session.rollback()
                await ReviewOrchestrationService._escalate_to_po_after_error(
                    project_id, task_id, reason="Review orchestration error; escalated to PO."
                )
                return
        if restart is not None:
            agent_run_id, feedback = restart
            KanbanService.start_coder_agent(
                task_id,
                project_id,
                po_feedback=feedback,
                agent_run_id=agent_run_id,
            )

    @staticmethod
    async def _apply_in_session(
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        diff_id: UUID,
        result: dict,
    ) -> tuple[UUID, str] | None:
        task = await TaskService.get(session, task_id, project_id=project_id)
        verdict = str(result.get("verdict", "unclear"))
        rounds = await ReviewOrchestrationService.count_reviewer_rounds(session, task_id)
        max_rounds = settings.agent_review_max_rounds

        if verdict == "approve_suggested":
            await ReviewOrchestrationService._open_po_review(
                session, task, project_id=project_id, task_id=task_id, reason="Reviewer approved; awaiting PO."
            )
            return None

        if verdict == "needs_changes" and rounds < max_rounds:
            feedback = _feedback_from_review_result(result)
            return await ReviewOrchestrationService._request_coder_revision(
                session,
                project_id=project_id,
                task_id=task_id,
                feedback=feedback,
                round_no=rounds,
            )

        # unclear, reviewer error, or max rounds — escalate to PO
        await ReviewOrchestrationService._open_po_review(
            session,
            task,
            project_id=project_id,
            task_id=task_id,
            reason=(
                f"Reviewer escalated to PO (verdict={verdict}, rounds={rounds}/{max_rounds})."
            ),
        )
        return None

    @staticmethod
    async def _open_po_review(
        session: AsyncSession,
        task: Task,
        *,
        project_id: UUID,
        task_id: UUID,
        reason: str,
    ) -> None:
        entering_review = task.status != TaskStatus.REVIEW
        task.status = TaskStatus.REVIEW
        task.updated_at = datetime.now(timezone.utc)
        await session.flush()
        if entering_review:
            await KanbanService.on_task_needs_review(session, task)
        await EventPublisher.publish(
            task_id,
            StreamEventType.STATUS_CHANGE,
            _status_event_content(
                {
                    "from": "AGENT_REVIEW",
                    "to": "PO_REVIEW",
                    "reason": reason,
                }
            ),
            session,
            None,
        )

    @staticmethod
    async def _request_coder_revision(
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID,
        feedback: str,
        round_no: int,
    ) -> tuple[UUID, str]:
        try:
            await DiffService.reject_latest_pending(session, task_id=task_id, project_id=project_id)
        except Exception:
            logger.info("No pending diff to reject before revision task_id=%s", task_id)

        task = await TaskService.get(session, task_id, project_id=project_id)
        if task.status != TaskStatus.IN_PROGRESS:
            task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.now(timezone.utc)

        agent_run = AgentRun(
            project_id=project_id,
            task_id=task_id,
            agent_type=AgentType.CODER,
            agent_version="1.0.0",
            status=AgentRunStatus.RUNNING,
            input_artifacts=[str(task_id)],
            output_artifacts=[],
            result={"reviewer_revision_round": round_no},
        )
        session.add(agent_run)
        await session.flush()
        agent_run_id = agent_run.id

        await EventPublisher.publish(
            task_id,
            StreamEventType.STATUS_CHANGE,
            _status_event_content(
                {
                    "from": "AGENT_REVIEW",
                    "to": "CODING",
                    "reason": f"Reviewer requested changes (round {round_no + 1}).",
                }
            ),
            session,
            agent_run_id,
        )

        return agent_run_id, feedback

    @staticmethod
    async def _escalate_to_po_after_error(project_id: UUID, task_id: UUID, *, reason: str) -> None:
        async with async_session_maker() as session:
            try:
                task = await TaskService.get(session, task_id, project_id=project_id)
                await ReviewOrchestrationService._open_po_review(
                    session, task, project_id=project_id, task_id=task_id, reason=reason
                )
                await session.commit()
            except Exception:
                logger.exception("Failed to escalate task_id=%s to PO review after error", task_id)
                await session.rollback()
