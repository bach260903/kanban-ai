"""Audit log writes: pending row before risky work, finalise when done (DB trigger allows only that UPDATE path)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InvalidTransitionError, NotFoundError
from app.models.audit_log import AuditLog, AuditLogResult


class AuditService:
    @staticmethod
    async def write_pending_log(
        session: AsyncSession,
        *,
        agent_id: str,
        agent_version: str,
        action_type: str,
        action_description: str,
        input_refs: list[str],
        output_refs: list[str] | None = None,
        project_id: UUID | None = None,
        task_id: UUID | None = None,
    ) -> UUID:
        """INSERT a row with ``result = awaiting_hil`` (only permitted initial outcome for agent steps)."""
        log = AuditLog(
            agent_id=agent_id,
            agent_version=agent_version,
            action_type=action_type,
            action_description=action_description,
            input_refs=input_refs,
            output_refs=output_refs or [],
            result=AuditLogResult.AWAITING_HIL,
            project_id=project_id,
            task_id=task_id,
        )
        session.add(log)
        await session.flush()
        return log.id

    @staticmethod
    async def finalise_log(
        session: AsyncSession,
        log_id: UUID,
        result: AuditLogResult,
        output_refs: list[str] | None = None,
    ) -> None:
        """UPDATE a pending log to ``success`` or ``failure`` (DB allows UPDATE only from ``awaiting_hil``)."""
        if result not in (AuditLogResult.SUCCESS, AuditLogResult.FAILURE):
            raise InvalidTransitionError("finalise_log requires result success or failure")

        log = await session.get(AuditLog, log_id)
        if log is None:
            raise NotFoundError("Audit log not found.")
        if log.result != AuditLogResult.AWAITING_HIL:
            raise InvalidTransitionError("Audit log is not awaiting finalisation.")

        log.result = result
        if output_refs is not None:
            log.output_refs = output_refs
        await session.flush()
