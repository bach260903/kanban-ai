"""DevOps API — health monitoring, incidents, rollbacks, alert config.

Phase 4 router. All endpoints require project membership.

Routes:
    GET  /projects/{project_id}/devops/health-summary
    GET  /projects/{project_id}/devops/incidents
    GET  /projects/{project_id}/devops/rollbacks
    GET  /projects/{project_id}/devops/alert-config
    PUT  /projects/{project_id}/devops/alert-config
    GET  /deployments/{deployment_id}/health-checks
    POST /deployments/{deployment_id}/rollback
    GET  /deployments/{deployment_id}/risk-assessment
"""

from __future__ import annotations

import asyncio
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import (
    get_current_user,
    require_any_member,
    require_leader_or_above,
)
from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_config import DeploymentConfig
from app.models.deployment_health_check import DeploymentHealthCheck
from app.models.deployment_incident import DeploymentIncident
from app.models.project_member import MemberStatus, ProjectMember, ProjectRole
from app.models.rollback_event import RollbackEvent
from app.models.user import User
from app.schemas.devops import (
    AlertConfigOut,
    AlertConfigUpdate,
    DeploymentHealthSummary,
    HealthCheckOut,
    IncidentOut,
    ManualRollbackRequest,
    RiskAssessmentOut,
    RollbackEventOut,
)

router = APIRouter(tags=["devops"])


# ── Shared dependency: load deployment + verify membership ────────────────────

async def _load_dep_and_check_member(
    deployment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    min_role: ProjectRole = ProjectRole.VIEWER,
) -> tuple[Deployment, ProjectMember]:
    dep = await session.get(Deployment, deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    member = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == dep.project_id,
            ProjectMember.user_id == current_user.id,
            ProjectMember.status == MemberStatus.ACTIVE,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    _ROLE_ORDER = [ProjectRole.VIEWER, ProjectRole.DEVELOPER, ProjectRole.LEADER, ProjectRole.OWNER]
    if _ROLE_ORDER.index(member.role) < _ROLE_ORDER.index(min_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return dep, member


# ── Health summary ─────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/devops/health-summary",
    response_model=list[DeploymentHealthSummary],
)
async def get_health_summary(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DeploymentHealthSummary]:
    """Health overview for all active deployments in a project."""
    result = await session.execute(
        select(Deployment)
        .where(
            Deployment.project_id == project_id,
            Deployment.status.notin_([DeploymentStatus.SKIPPED, DeploymentStatus.ROLLED_BACK]),
        )
        .order_by(Deployment.created_at.desc())
        .limit(20)
    )
    deployments = result.scalars().all()

    summaries: list[DeploymentHealthSummary] = []
    for dep in deployments:
        latest_hc = await session.scalar(
            select(DeploymentHealthCheck)
            .where(DeploymentHealthCheck.deployment_id == dep.id)
            .order_by(DeploymentHealthCheck.checked_at.desc())
            .limit(1)
        )

        open_incidents = await session.scalar(
            select(func.count(DeploymentIncident.id)).where(
                DeploymentIncident.deployment_id == dep.id,
                DeploymentIncident.resolved.is_(False),
            )
        ) or 0

        last_rollback = await session.scalar(
            select(RollbackEvent)
            .where(RollbackEvent.deployment_id == dep.id)
            .order_by(RollbackEvent.created_at.desc())
            .limit(1)
        )

        recent_statuses_result = await session.execute(
            select(DeploymentHealthCheck.status)
            .where(DeploymentHealthCheck.deployment_id == dep.id)
            .order_by(DeploymentHealthCheck.checked_at.desc())
            .limit(10)
        )
        statuses = [r[0] for r in recent_statuses_result]
        consec = 0
        for s in statuses:
            if s not in ("healthy",):
                consec += 1
            else:
                break

        summaries.append(DeploymentHealthSummary(
            deployment_id=dep.id,
            project_id=dep.project_id,
            health_status=dep.health_status,
            last_checked_at=latest_hc.checked_at if latest_hc else None,
            latest_http_status=latest_hc.http_status if latest_hc else None,
            latest_latency_ms=latest_hc.latency_ms if latest_hc else None,
            consecutive_failures=consec,
            open_incidents=open_incidents,
            last_rollback_at=last_rollback.created_at if last_rollback else None,
        ))

    return summaries


# ── Incidents ─────────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/devops/incidents",
    response_model=list[IncidentOut],
)
async def list_incidents(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
    resolved: bool | None = None,
    limit: int = 50,
) -> list[IncidentOut]:
    q = select(DeploymentIncident).where(DeploymentIncident.project_id == project_id)
    if resolved is not None:
        q = q.where(DeploymentIncident.resolved.is_(resolved))
    q = q.order_by(DeploymentIncident.created_at.desc()).limit(min(limit, 200))
    result = await session.execute(q)
    return [_incident_out(i) for i in result.scalars().all()]


# ── Rollback events ───────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/devops/rollbacks",
    response_model=list[RollbackEventOut],
)
async def list_rollbacks(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> list[RollbackEventOut]:
    result = await session.execute(
        select(RollbackEvent)
        .where(RollbackEvent.project_id == project_id)
        .order_by(RollbackEvent.created_at.desc())
        .limit(min(limit, 200))
    )
    return [RollbackEventOut.model_validate(r) for r in result.scalars().all()]


# ── Alert config ──────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/devops/alert-config",
    response_model=AlertConfigOut,
)
async def get_alert_config(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AlertConfigOut:
    config = await _require_config(session, project_id)
    return AlertConfigOut.model_validate(config)


@router.put(
    "/projects/{project_id}/devops/alert-config",
    response_model=AlertConfigOut,
)
async def update_alert_config(
    project_id: UUID,
    body: AlertConfigUpdate,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AlertConfigOut:
    config = await _require_config(session, project_id)

    if body.discord_webhook_url is not None:
        config.discord_webhook_url = body.discord_webhook_url or None
    if body.slack_webhook_url is not None:
        config.slack_webhook_url = body.slack_webhook_url or None
    if body.health_check_path is not None:
        config.health_check_path = body.health_check_path or "/health"
    if body.alert_on_anomaly is not None:
        config.alert_on_anomaly = body.alert_on_anomaly
    if body.monitor_duration_minutes is not None:
        config.monitor_duration_minutes = body.monitor_duration_minutes

    await session.commit()
    await session.refresh(config)
    return AlertConfigOut.model_validate(config)


# ── Deployment-scoped: health checks ─────────────────────────────────────────

@router.get(
    "/deployments/{deployment_id}/health-checks",
    response_model=list[HealthCheckOut],
)
async def get_health_checks(
    deployment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> list[HealthCheckOut]:
    await _load_dep_and_check_member(deployment_id, current_user, session)
    result = await session.execute(
        select(DeploymentHealthCheck)
        .where(DeploymentHealthCheck.deployment_id == deployment_id)
        .order_by(DeploymentHealthCheck.checked_at.desc())
        .limit(min(limit, 500))
    )
    return [HealthCheckOut.model_validate(hc) for hc in result.scalars().all()]


# ── Manual rollback ────────────────────────────────────────────────────────────

@router.post(
    "/deployments/{deployment_id}/rollback",
    response_model=RollbackEventOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def manual_rollback(
    deployment_id: UUID,
    body: ManualRollbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollbackEventOut:
    """Trigger a manual rollback. Requires Leader or Owner role.

    Safety: never deletes data, never reverts DB migrations.
    """
    dep, member = await _load_dep_and_check_member(
        deployment_id, current_user, session, min_role=ProjectRole.LEADER
    )

    from app.services import rollback_service

    try:
        event = await rollback_service.trigger_rollback(
            session,
            deployment_id=deployment_id,
            project_id=dep.project_id,
            triggered_by="manual",
            reason=body.reason,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Fire notifications async (best-effort)
    config = await session.scalar(
        select(DeploymentConfig).where(
            DeploymentConfig.project_id == dep.project_id
        )
    )
    if config and (config.discord_webhook_url or config.slack_webhook_url):
        from app.services import rollback_service as rs
        asyncio.create_task(
            rs.send_rollback_notifications(
                event=event,
                project_name=config.project_name,
                discord_url=config.discord_webhook_url,
                slack_url=config.slack_webhook_url,
            )
        )

    return RollbackEventOut.model_validate(event)


# ── On-demand risk assessment ─────────────────────────────────────────────────

@router.get(
    "/deployments/{deployment_id}/risk-assessment",
    response_model=RiskAssessmentOut,
)
async def get_risk_assessment(
    deployment_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RiskAssessmentOut:
    dep, _ = await _load_dep_and_check_member(deployment_id, current_user, session)

    from app.agent.nodes.devops_node import assess_deployment_risk

    assessment = await assess_deployment_risk(
        files_changed=[],
        commit_message="",
        branch_name=dep.branch_name or "",
        step_results={},
        previous_risk_scores=[],
    )

    if dep.risk_score is None:
        dep.risk_score = assessment.risk_score
        await session.commit()

    return RiskAssessmentOut(
        risk_score=assessment.risk_score,
        risk_level=assessment.risk_level,
        reasoning=assessment.reasoning,
        risk_factors=assessment.risk_factors,
        blast_radius=assessment.blast_radius,
        safe_to_deploy=assessment.safe_to_deploy,
        via_llm=assessment.via_llm,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _require_config(session: AsyncSession, project_id: UUID) -> DeploymentConfig:
    config = await session.scalar(
        select(DeploymentConfig).where(DeploymentConfig.project_id == project_id)
    )
    if config is None:
        raise HTTPException(status_code=404, detail="No deployment config found for this project")
    return config


def _incident_out(obj: DeploymentIncident) -> IncidentOut:
    snap = None
    if obj.metric_snapshot:
        try:
            snap = json.loads(obj.metric_snapshot)
        except Exception:
            pass
    return IncidentOut(
        id=obj.id,
        deployment_id=obj.deployment_id,
        project_id=obj.project_id,
        incident_type=obj.incident_type,
        severity=obj.severity,
        title=obj.title,
        description=obj.description,
        ai_reasoning=obj.ai_reasoning,
        risk_score=obj.risk_score,
        metric_snapshot=snap,
        rollback_triggered=obj.rollback_triggered,
        resolved=obj.resolved,
        resolved_at=obj.resolved_at,
        created_at=obj.created_at,
    )
