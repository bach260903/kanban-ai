"""Reviewer Agent Node — runs automatically after coder/cli_coder, before HIL interrupt.

Flow (per plan.md):
    coder_node / cli_coder_node  →  reviewer_node  →  interrupt_node
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_maker
from app.llm.factory import create_chat_llm
from app.models.diff import Diff
from app.models.review_report import (
    ReviewComment,
    ReviewReport,
    ReviewSeverity,
    ReviewStatus,
    ReviewSuggestion,
)
from app.models.stream_event import StreamEventType
from app.models.task import Task
from app.services import reviewer_service
from app.services.audit_service import REVIEWER_AGENT_ID, finalise_log, write_pending_log
from app.websocket.event_publisher import EventPublisher

logger = logging.getLogger(__name__)

StateDict = dict[str, Any]

_REVIEWER_TIMEOUT_SEC = 300

# Path from this file: backend/app/agent/nodes/reviewer_node.py
# parents[4] = project root (d:/KLTN/kanban-ai)
_CONSTITUTION_PATH: Path = (
    Path(__file__).resolve().parents[4] / ".specify" / "memory" / "constitution.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_uuid_or_none(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _sandbox_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    return (root / str(project_id)).resolve()


def _load_constitution() -> str:
    try:
        if _CONSTITUTION_PATH.exists():
            return _CONSTITUTION_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("reviewer_node: could not read constitution at %s", _CONSTITUTION_PATH)
    return ""


async def _safe_publish(
    session: AsyncSession,
    task_id: UUID,
    agent_run_id: UUID | None,
    event_type: StreamEventType,
    body: dict[str, Any],
) -> None:
    """Publish a WebSocket stream event, silently swallowing failures."""
    try:
        await EventPublisher.publish(
            task_id,
            event_type,
            json.dumps(body, separators=(",", ":")),
            session,
            agent_run_id,
        )
    except Exception:
        logger.exception(
            "reviewer_node: failed to publish %s for task %s", event_type, task_id
        )


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------


async def _run_with_session(state: StateDict) -> StateDict:  # noqa: PLR0912, PLR0915
    task_id = _as_uuid_or_none(state.get("task_id"))
    project_id = _as_uuid_or_none(state.get("project_id"))
    agent_run_id = _as_uuid_or_none(state.get("agent_run_id"))

    if task_id is None:
        logger.warning("reviewer_node: no task_id in state — skipping review")
        return state

    async with async_session_maker() as session:
        # ------------------------------------------------------------------
        # T028: Fetch task + latest diff
        # ------------------------------------------------------------------
        task = await session.get(Task, task_id)
        if task is None:
            logger.warning("reviewer_node: task %s not found — skipping", task_id)
            return state

        diff_result = await session.execute(
            select(Diff)
            .where(Diff.task_id == task_id)
            .order_by(Diff.created_at.desc())
            .limit(1)
        )
        diff_row = diff_result.scalar_one_or_none()
        diff_content: str = diff_row.content if diff_row else ""

        constitution = _load_constitution()

        # ------------------------------------------------------------------
        # T028: Create ReviewReport with status=running
        # ------------------------------------------------------------------
        report = ReviewReport(
            task_id=task_id,
            agent_run_id=agent_run_id,
            status=ReviewStatus.RUNNING,
        )
        session.add(report)
        await session.flush()  # assigns report.id

        # ------------------------------------------------------------------
        # T028: Write pending audit log — Constitution Principle V
        # ------------------------------------------------------------------
        audit_log = await write_pending_log(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="reviewer_node",
            action_description=f"AI reviewer started for task {task.title!r}",
            agent_id=REVIEWER_AGENT_ID,
            input_refs=[str(diff_row.id)] if diff_row else [],
        )

        # ------------------------------------------------------------------
        # T029: Main execution block (5-minute hard timeout)
        # ------------------------------------------------------------------
        exec_error: Exception | None = None
        test_pass = 0
        test_fail = 0
        secret_findings: list[dict[str, Any]] = []
        ai_comments: list[dict[str, Any]] = []
        suggestion: str = ReviewSuggestion.NEEDS_CHANGES
        score = 0
        runner: str | None = None

        try:
            async with asyncio.timeout(_REVIEWER_TIMEOUT_SEC):
                # Detect test runner + run tests
                sandbox_path = str(_sandbox_root(project_id)) if project_id else ""
                if sandbox_path:
                    runner = reviewer_service.detect_test_runner(sandbox_path)
                if runner:
                    test_pass, test_fail, test_error_msg = reviewer_service.run_tests(
                        runner, sandbox_path
                    )
                    report.test_error = test_error_msg
                else:
                    test_pass, test_fail = 0, 0

                # Scan for secrets in diff
                secret_findings = reviewer_service.scan_secrets(diff_content)
                secret_count = len(secret_findings)

                # AI review
                llm = create_chat_llm(provider=settings.review_llm_provider, temperature=0.1)
                suggestion, ai_comments = await reviewer_service.ai_review_diff(
                    diff=diff_content,
                    constitution=constitution,
                    llm=llm,
                )

                # Score calculation
                score = reviewer_service.calculate_score(
                    test_pass, test_fail, secret_count, suggestion
                )

                # ------------------------------------------------------------------
                # T029: Update report with results
                # ------------------------------------------------------------------
                # Coerce suggestion to ReviewSuggestion enum to satisfy DB CHECK constraint
                try:
                    suggestion_enum = ReviewSuggestion(suggestion)
                except ValueError:
                    suggestion_enum = ReviewSuggestion.NEEDS_CHANGES

                report.score = score
                report.suggestion = suggestion_enum
                report.test_runner = runner
                report.test_pass = test_pass
                report.test_fail = test_fail
                report.status = ReviewStatus.COMPLETE
                report.completed_at = datetime.now(timezone.utc)

                # ------------------------------------------------------------------
                # T029: Persist ReviewComment rows — AI comments
                # ------------------------------------------------------------------
                for c in ai_comments:
                    severity_raw = str(c.get("severity", "info")).lower()
                    try:
                        severity = ReviewSeverity(severity_raw)
                    except ValueError:
                        severity = ReviewSeverity.INFO
                    session.add(
                        ReviewComment(
                            review_report_id=report.id,
                            file_path=str(c.get("file_path", "unknown"))[:500],
                            line_number=c.get("line_number"),
                            content=str(c.get("content", ""))[:2000],
                            severity=severity,
                        )
                    )

                # Persist ReviewComment rows — secret findings (always ERROR severity)
                for s in secret_findings:
                    session.add(
                        ReviewComment(
                            review_report_id=report.id,
                            file_path=str(s.get("file", "unknown"))[:500],
                            line_number=s.get("line"),
                            content=f"Potential secret detected: {s['pattern_name']}",
                            severity=ReviewSeverity.ERROR,
                        )
                    )

                await session.flush()
                await finalise_log(
                    session, audit_log.id, "success", output_refs=[str(report.id)]
                )

        # ------------------------------------------------------------------
        # T030: Error handling — catch all (incl. TimeoutError), never propagate
        # ------------------------------------------------------------------
        except Exception as exc:  # noqa: BLE001
            exec_error = exc
            report.status = ReviewStatus.ERROR
            report.error_message = str(exc)[:500]
            report.completed_at = datetime.now(timezone.utc)
            await session.flush()
            # Finalize audit log as failure — Constitution Principle V requires every
            # pending log to be closed regardless of outcome.
            await finalise_log(session, audit_log.id, "failure", output_refs=[str(report.id)])
            logger.exception("reviewer_node: error reviewing task %s", task_id)

        # ------------------------------------------------------------------
        # T030: Publish WebSocket events
        # ------------------------------------------------------------------
        if exec_error is None:
            # REVIEW_SCORE event (uses ACTION type — StreamEventType has no REVIEW_* values)
            await _safe_publish(
                session,
                task_id,
                agent_run_id,
                StreamEventType.ACTION,
                {
                    "type": "REVIEW_SCORE",
                    "task_id": str(task_id),
                    "report_id": str(report.id),
                    "score": report.score,
                    "suggestion": report.suggestion,
                    "test_pass": report.test_pass,
                    "test_fail": report.test_fail,
                    "test_runner": report.test_runner,
                },
            )
            # REVIEW_COMMENT event — reload comments relationship only
            await session.refresh(report, attribute_names=["comments"])
            await _safe_publish(
                session,
                task_id,
                agent_run_id,
                StreamEventType.ACTION,
                {
                    "type": "REVIEW_COMMENT",
                    "task_id": str(task_id),
                    "report_id": str(report.id),
                    "comments": [
                        {
                            "file_path": c.file_path,
                            "line_number": c.line_number,
                            "content": c.content,
                            "severity": c.severity,
                        }
                        for c in report.comments
                    ],
                },
            )
        else:
            # REVIEW_ERROR event
            await _safe_publish(
                session,
                task_id,
                agent_run_id,
                StreamEventType.ERROR,
                {
                    "type": "REVIEW_ERROR",
                    "task_id": str(task_id),
                    "report_id": str(report.id),
                    "error": report.error_message,
                },
            )

        await session.commit()

    # Store report ID in state for downstream nodes / REST API polling
    state["review_report_id"] = str(report.id)
    return state


# ---------------------------------------------------------------------------
# T030: Public entry point — never raises, continues to interrupt_node
# ---------------------------------------------------------------------------


async def run(state: StateDict) -> StateDict:
    """Entry point for LangGraph (reviewer_node).

    Guaranteed to return state even on catastrophic failure so that the
    graph can proceed to the HIL interrupt checkpoint.
    """
    try:
        return await _run_with_session(state)
    except Exception:  # noqa: BLE001
        logger.exception("reviewer_node: unhandled top-level error")
        return state
