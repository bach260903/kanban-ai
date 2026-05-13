"""Append-only audit log writes (US5 / T041)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditLogResult

SYSTEM_AGENT_ID = "system"
SYSTEM_AGENT_VERSION = "1.0.0"


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
