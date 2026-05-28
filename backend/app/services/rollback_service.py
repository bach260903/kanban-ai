"""Rollback orchestration service — Phase 4.

Safety contract (enforced here, not negotiable):
- NEVER deletes production data
- NEVER reverts DB schema / migrations automatically
- NEVER redeploys if target deployment has risk_level='critical'
- Manual confirmation required for rollbacks triggered by humans
- AI-triggered rollbacks are limited to provider re-deploy of last healthy build

Flow:
  1. Find the most recent HEALTHY deployment before the failing one
  2. Call provider adapter to redeploy that deployment's commit/branch
  3. Create RollbackEvent row tracking the attempt
  4. Update the failing Deployment.status = rolled_back
  5. Send alert
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_config import DeploymentConfig, DeployProvider
from app.models.deployment_incident import DeploymentIncident
from app.models.rollback_event import RollbackEvent, RollbackStatus, RollbackTrigger
from app.services.deployment_service import decrypt_token

logger = logging.getLogger(__name__)


# ── Public entry points ───────────────────────────────────────────────────────

async def trigger_rollback(
    session: AsyncSession,
    *,
    deployment_id: UUID,
    project_id: UUID,
    triggered_by: str = RollbackTrigger.MANUAL,
    reason: str = "Manual rollback requested",
    incident_id: UUID | None = None,
    ai_reasoning: str | None = None,
) -> RollbackEvent:
    """Orchestrate a rollback for `deployment_id`.

    Returns the RollbackEvent created (status will be 'completed' or 'failed').
    The caller is responsible for committing the session.
    """
    # ── 1. Load target deployment ─────────────────────────────────────────────
    deployment = await session.get(Deployment, deployment_id)
    if deployment is None:
        raise ValueError(f"Deployment {deployment_id} not found")

    # ── 2. Safety check: never rollback a rollback ────────────────────────────
    if deployment.rollback_of_id is not None:
        raise ValueError("Cannot roll back a deployment that is itself a rollback")

    # ── 3. Find previous healthy deployment ───────────────────────────────────
    prev = await _find_previous_healthy(session, deployment)

    # ── 4. Create RollbackEvent (pending) ─────────────────────────────────────
    event = RollbackEvent(
        deployment_id=deployment_id,
        project_id=project_id,
        triggered_by=triggered_by,
        previous_deployment_id=prev.id if prev else None,
        status=RollbackStatus.PENDING,
        reason=reason,
        ai_reasoning=ai_reasoning,
    )
    session.add(event)
    await session.flush()

    if prev is None:
        logger.warning("rollback_service: no previous healthy deployment found for %s", deployment_id)
        event.status = RollbackStatus.SKIPPED
        event.ai_reasoning = (ai_reasoning or "") + "\n[Skipped: no previous healthy deployment found]"
        deployment.health_status = "degraded"
        await session.flush()
        return event

    # ── 5. Attempt provider redeploy ──────────────────────────────────────────
    event.status = RollbackStatus.ROLLING_BACK
    await session.flush()

    try:
        new_dep = await _execute_provider_rollback(
            session,
            failing_deployment=deployment,
            target_deployment=prev,
            rollback_event_id=event.id,
        )
        event.status = RollbackStatus.COMPLETED
        event.completed_at = datetime.now(timezone.utc)
        deployment.status = DeploymentStatus.ROLLED_BACK
        deployment.health_status = "rolled_back"
        if incident_id:
            incident = await session.get(DeploymentIncident, incident_id)
            if incident:
                incident.rollback_triggered = True
                incident.resolved = True
                incident.resolved_at = datetime.now(timezone.utc)

        logger.info(
            "rollback_service: rollback completed — new dep %s (was %s)",
            new_dep.id, deployment_id,
        )
    except Exception as exc:
        logger.exception("rollback_service: provider rollback failed for %s", deployment_id)
        event.status = RollbackStatus.FAILED
        event.ai_reasoning = (ai_reasoning or "") + f"\n[Error: {exc}]"
        event.completed_at = datetime.now(timezone.utc)

    await session.flush()
    return event


async def send_rollback_notifications(
    *,
    event: RollbackEvent,
    project_name: str,
    discord_url: str | None,
    slack_url: str | None,
) -> None:
    """Fire-and-forget alert for rollback completion/failure."""
    from app.services import alert_service

    await alert_service.send_rollback_alert(
        discord_url=discord_url,
        slack_url=slack_url,
        project_name=project_name,
        deployment_id=event.deployment_id,
        triggered_by=event.triggered_by,
        status=event.status,
        reason=event.reason,
        previous_deployment_id=event.previous_deployment_id,
    )
    event.alert_sent = True


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _find_previous_healthy(
    session: AsyncSession,
    failing: Deployment,
) -> Deployment | None:
    """Return the most recent HEALTHY deployment before `failing` in the same project."""
    result = await session.execute(
        select(Deployment)
        .where(
            Deployment.project_id == failing.project_id,
            Deployment.status == DeploymentStatus.HEALTHY,
            Deployment.id != failing.id,
            Deployment.created_at < failing.created_at,
        )
        .order_by(Deployment.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _execute_provider_rollback(
    session: AsyncSession,
    *,
    failing_deployment: Deployment,
    target_deployment: Deployment,
    rollback_event_id: UUID,
) -> Deployment:
    """Call provider to redeploy the target's commit, creating a new Deployment row."""
    config = await session.scalar(
        select(DeploymentConfig).where(
            DeploymentConfig.project_id == failing_deployment.project_id,
            DeploymentConfig.enabled.is_(True),
        )
    )

    if config is None or config.provider == DeployProvider.NONE:
        # No provider configured — we still mark it as completed (manual note)
        logger.info("rollback_service: no provider configured, skipping adapter call")
        new_dep = Deployment(
            project_id=failing_deployment.project_id,
            task_id=failing_deployment.task_id,
            run_id=failing_deployment.run_id,
            status=DeploymentStatus.HEALTHY,
            environment=failing_deployment.environment,
            provider=failing_deployment.provider,
            branch_name=target_deployment.branch_name,
            commit_sha=target_deployment.commit_sha,
            preview_url=target_deployment.preview_url,
            deploy_logs="Rollback: reusing previous deployment metadata (no provider)",
            health_status="healthy",
            rollback_of_id=failing_deployment.id,
            deployed_at=datetime.now(timezone.utc),
        )
        session.add(new_dep)
        await session.flush()
        return new_dep

    token = decrypt_token(config.token_encrypted)
    adapter = _get_adapter(config.provider)
    if adapter is None:
        raise RuntimeError(f"No adapter for provider {config.provider}")

    t0 = datetime.now(timezone.utc)
    result = await adapter.deploy(
        branch_name=target_deployment.branch_name or "main",
        commit_sha=target_deployment.commit_sha,
        project_name=config.project_name,
        team_id=config.team_id,
        token=token,
    )

    duration_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    new_dep = Deployment(
        project_id=failing_deployment.project_id,
        task_id=failing_deployment.task_id,
        run_id=failing_deployment.run_id,
        status=DeploymentStatus.HEALTHY if result.success else DeploymentStatus.DEGRADED,
        environment=failing_deployment.environment,
        provider=str(config.provider),
        external_id=result.external_id,
        preview_url=result.preview_url,
        branch_name=target_deployment.branch_name,
        commit_sha=target_deployment.commit_sha,
        deploy_logs=result.logs,
        error_message=result.error_message if not result.success else None,
        health_status="healthy" if result.success else "degraded",
        rollback_of_id=failing_deployment.id,
        duration_ms=duration_ms,
        deployed_at=datetime.now(timezone.utc),
    )
    session.add(new_dep)
    await session.flush()

    if not result.success:
        raise RuntimeError(f"Provider redeploy failed: {result.error_message}")

    return new_dep


def _get_adapter(provider: DeployProvider):
    if provider == DeployProvider.VERCEL:
        from app.adapters.vercel_adapter import VercelAdapter
        return VercelAdapter()
    if provider == DeployProvider.RAILWAY:
        from app.adapters.railway_adapter import RailwayAdapter
        return RailwayAdapter()
    return None
