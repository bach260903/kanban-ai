"""Append-only audit log writes (US5 / T041) + pending/finalise flow (T014 / T044)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditLogResult

SYSTEM_AGENT_ID = "system"
SYSTEM_AGENT_VERSION = "1.0.0"


def _coerce_audit_result(result: AuditLogResult | str) -> AuditLogResult:
    if isinstance(result, AuditLogResult):
        return result
    key = str(result).strip().lower()
    if key == "success" or key == AuditLogResult.SUCCESS.value:
        return AuditLogResult.SUCCESS
    if key in ("awaiting_hil", AuditLogResult.AWAITING_HIL.value):
        return AuditLogResult.AWAITING_HIL
    return AuditLogResult.FAILURE


async def write_audit(
    session: AsyncSession,
    *,
    project_id: UUID | None,
    task_id: UUID | None,
    action_type: str,
    action_description: str,
    result: AuditLogResult,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
) -> AuditLog:
    """Insert a single immutable-style audit row (no updates exposed)."""
    row = AuditLog(
        agent_id=SYSTEM_AGENT_ID,
        agent_version=SYSTEM_AGENT_VERSION,
        action_type=action_type,
        action_description=action_description,
        result=result,
        input_refs=input_refs or [],
        output_refs=output_refs or [],
        project_id=project_id,
        task_id=task_id,
    )
    session.add(row)
    await session.flush()
    return row


async def write_pending_log(
    session: AsyncSession,
    *,
    project_id: UUID | None,
    task_id: UUID | None,
    action_type: str,
    action_description: str,
    input_refs: list[str] | None = None,
) -> AuditLog:
    """Insert a pre-action audit row (``result = awaiting_hil``) — Constitution Principle V."""
    row = AuditLog(
        agent_id=SYSTEM_AGENT_ID,
        agent_version=SYSTEM_AGENT_VERSION,
        action_type=action_type,
        action_description=action_description,
        result=AuditLogResult.AWAITING_HIL,
        input_refs=input_refs or [],
        output_refs=[],
        project_id=project_id,
        task_id=task_id,
    )
    session.add(row)
    await session.flush()
    return row


async def list_audit_logs_for_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    offset: int,
    limit: int,
) -> tuple[list[AuditLog], int]:
    """Return newest-first audit rows for a project and total count (pagination)."""
    count_stmt = select(func.count()).select_from(AuditLog).where(AuditLog.project_id == project_id)
    total = int(await session.scalar(count_stmt) or 0)
    stmt = (
        select(AuditLog)
        .where(AuditLog.project_id == project_id)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return rows, total


async def finalise_log(
    session: AsyncSession,
    log_id: UUID,
    result: AuditLogResult | str,
    *,
    output_refs: list[str] | None = None,
) -> AuditLog | None:
    """The permitted UPDATE path for ``audit_logs`` (T014): close a pending row."""
    row = await session.get(AuditLog, log_id)
    if row is None:
        return None
    row.result = _coerce_audit_result(result)
    if output_refs is not None:
        row.output_refs = output_refs
    await session.flush()
    return row
