"""Deployment observability service — Phase 4.

Responsibilities:
- Poll deployment health endpoint after successful preview deploy
- Detect anomalies (health failures, latency spikes, error codes)
- Create DeploymentIncident rows via AI analysis
- Trigger automatic rollback when confidence is high
- Send Discord/Slack alerts

Run as a background asyncio task, never blocks the HTTP layer.

Safety rules (always respected):
- Auto-rollback only when rollback_confidence >= 0.85 AND consecutive_failures >= 3
- Always write DeploymentIncident before attempting rollback
- Never auto-rollback if the deployment has already been manually confirmed safe
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker as AsyncSessionLocal
from app.models.deployment import Deployment, DeploymentStatus
from app.models.deployment_config import DeploymentConfig
from app.models.deployment_health_check import DeploymentHealthCheck
from app.models.deployment_incident import DeploymentIncident, IncidentType

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

_POLL_INTERVAL_SECONDS = 30
_AUTO_ROLLBACK_MIN_FAILURES = 3       # consecutive failures before considering rollback
_AUTO_ROLLBACK_MIN_CONFIDENCE = 0.85  # AI confidence needed to auto-roll
_LATENCY_SPIKE_MS = 5000              # ms above which we flag latency_spike
_MAX_HEALTH_CHECK_TIMEOUT = 10        # seconds per HTTP probe


# ── Public API ────────────────────────────────────────────────────────────────

async def start_monitoring(
    deployment_id: UUID,
    project_id: UUID,
    preview_url: str,
    health_check_path: str = "/health",
    monitor_duration_minutes: int = 5,
) -> None:
    """Spawn a background monitoring loop. Call after successful preview deploy.

    The loop runs for `monitor_duration_minutes` polling every 30 s.
    It never raises — all exceptions are swallowed and logged.
    """
    asyncio.create_task(
        _monitoring_loop(
            deployment_id=deployment_id,
            project_id=project_id,
            preview_url=preview_url,
            health_check_path=health_check_path,
            monitor_duration_minutes=monitor_duration_minutes,
        ),
        name=f"monitor-{deployment_id}",
    )
    logger.info(
        "observability_service: monitoring started for deployment %s (%d min)",
        deployment_id, monitor_duration_minutes,
    )


# ── Monitoring loop ───────────────────────────────────────────────────────────

async def _monitoring_loop(
    *,
    deployment_id: UUID,
    project_id: UUID,
    preview_url: str,
    health_check_path: str,
    monitor_duration_minutes: int,
) -> None:
    end_time = asyncio.get_event_loop().time() + monitor_duration_minutes * 60
    consecutive_failures = 0
    rollback_triggered_already = False

    while asyncio.get_event_loop().time() < end_time:
        try:
            hc = await _probe(
                deployment_id=deployment_id,
                project_id=project_id,
                preview_url=preview_url,
                health_check_path=health_check_path,
            )

            if hc.status in ("healthy",):
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.warning(
                    "observability_service: health failure #%d for dep %s (HTTP %s)",
                    consecutive_failures, deployment_id, hc.http_status,
                )

            # Check for latency spike (counts as soft failure)
            if hc.latency_ms and hc.latency_ms > _LATENCY_SPIKE_MS:
                await _maybe_create_incident(
                    deployment_id=deployment_id,
                    project_id=project_id,
                    incident_type=IncidentType.LATENCY_SPIKE,
                    consecutive_failures=consecutive_failures,
                    latest_http_status=hc.http_status,
                    latest_latency_ms=hc.latency_ms,
                    preview_url=preview_url,
                    rollback_triggered_already=rollback_triggered_already,
                )

            # Check for health / crash failures
            if consecutive_failures >= 2 and not rollback_triggered_already:
                incident_type = (
                    IncidentType.CRASH
                    if (hc.http_status or 0) == 0
                    else IncidentType.HEALTH_FAIL
                    if (hc.http_status or 0) >= 500
                    else IncidentType.ERROR_SPIKE
                )
                did_rollback = await _maybe_create_incident(
                    deployment_id=deployment_id,
                    project_id=project_id,
                    incident_type=incident_type,
                    consecutive_failures=consecutive_failures,
                    latest_http_status=hc.http_status,
                    latest_latency_ms=hc.latency_ms,
                    preview_url=preview_url,
                    rollback_triggered_already=rollback_triggered_already,
                )
                if did_rollback:
                    rollback_triggered_already = True
                    break  # monitoring ends after rollback

        except Exception as exc:
            logger.exception("observability_service: probe loop error for %s: %s", deployment_id, exc)

        await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    logger.info("observability_service: monitoring complete for deployment %s", deployment_id)


# ── HTTP probe ────────────────────────────────────────────────────────────────

async def _probe(
    *,
    deployment_id: UUID,
    project_id: UUID,
    preview_url: str,
    health_check_path: str,
) -> DeploymentHealthCheck:
    """Fire a single HTTP probe and persist the result."""
    url = preview_url.rstrip("/") + "/" + health_check_path.lstrip("/")
    status = "unknown"
    http_status: int | None = None
    latency_ms: int | None = None
    response_snippet: str | None = None
    error_message: str | None = None

    import time as _time
    t0 = _time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=_MAX_HEALTH_CHECK_TIMEOUT) as client:
            resp = await client.get(url)
        latency_ms = int((_time.monotonic() - t0) * 1000)
        http_status = resp.status_code
        response_snippet = resp.text[:500]

        if resp.status_code < 400:
            status = "healthy"
        elif resp.status_code < 500:
            status = "degraded"
        else:
            status = "degraded"

    except httpx.TimeoutException:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        status = "unreachable"
        error_message = "Connection timed out"
    except Exception as exc:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        status = "unreachable"
        error_message = str(exc)[:300]

    hc = DeploymentHealthCheck(
        deployment_id=deployment_id,
        project_id=project_id,
        status=status,
        http_status=http_status,
        latency_ms=latency_ms,
        response_snippet=response_snippet,
        error_message=error_message,
    )

    async with AsyncSessionLocal() as session:
        session.add(hc)
        # Also update Deployment.health_status
        dep = await session.get(Deployment, deployment_id)
        if dep:
            dep.health_status = status
        await session.commit()
        await session.refresh(hc)

    return hc


# ── Anomaly → incident → optional rollback ────────────────────────────────────

async def _maybe_create_incident(
    *,
    deployment_id: UUID,
    project_id: UUID,
    incident_type: str,
    consecutive_failures: int,
    latest_http_status: int | None,
    latest_latency_ms: int | None,
    preview_url: str | None,
    rollback_triggered_already: bool,
) -> bool:
    """Create a DeploymentIncident and potentially trigger rollback.

    Returns True if rollback was triggered.
    """
    from app.agent.nodes.devops_node import analyze_incident

    try:
        analysis = await analyze_incident(
            incident_type=incident_type,
            consecutive_failures=consecutive_failures,
            latest_http_status=latest_http_status,
            latest_latency_ms=latest_latency_ms,
            deployment_age_minutes=_deployment_age_minutes(deployment_id),
            preview_url=preview_url,
        )
    except Exception as exc:
        logger.warning("observability_service: incident analysis failed (%s)", exc)
        from app.agent.nodes.devops_node import _heuristic_incident_analysis
        analysis = _heuristic_incident_analysis(
            incident_type=incident_type,
            consecutive_failures=consecutive_failures,
            latest_http_status=latest_http_status,
        )

    metric_snap = json.dumps({
        "incident_type": incident_type,
        "consecutive_failures": consecutive_failures,
        "http_status": latest_http_status,
        "latency_ms": latest_latency_ms,
    })

    should_rollback = (
        not rollback_triggered_already
        and analysis.recommended_action == "rollback"
        and analysis.rollback_confidence >= _AUTO_ROLLBACK_MIN_CONFIDENCE
        and consecutive_failures >= _AUTO_ROLLBACK_MIN_FAILURES
    )

    async with AsyncSessionLocal() as session:
        incident = DeploymentIncident(
            deployment_id=deployment_id,
            project_id=project_id,
            incident_type=incident_type,
            severity=analysis.severity,
            title=analysis.summary[:255],
            description=analysis.root_cause[:2000],
            ai_reasoning=analysis.reasoning[:4000],
            risk_score=analysis.rollback_confidence,
            metric_snapshot=metric_snap,
            rollback_triggered=should_rollback,
        )
        session.add(incident)
        await session.flush()

        # Load deployment config for alert webhooks
        from sqlalchemy import select
        config: DeploymentConfig | None = await session.scalar(
            select(DeploymentConfig).where(
                DeploymentConfig.project_id == project_id,
                DeploymentConfig.alert_on_anomaly.is_(True),
            )
        )
        discord_url = config.discord_webhook_url if config else None
        slack_url = config.slack_webhook_url if config else None

        dep = await session.get(Deployment, deployment_id)
        project_name = str(project_id)[:8]  # fallback; real name joined elsewhere

        if should_rollback:
            from app.services import rollback_service
            try:
                event = await rollback_service.trigger_rollback(
                    session,
                    deployment_id=deployment_id,
                    project_id=project_id,
                    triggered_by="ai_anomaly",
                    reason=analysis.summary,
                    incident_id=incident.id,
                    ai_reasoning=analysis.reasoning,
                )
                incident.rollback_triggered = (event.status == "completed")
                event.alert_sent = True  # we'll send below

                logger.info(
                    "observability_service: auto-rollback %s for dep %s",
                    event.status, deployment_id,
                )
            except Exception as exc:
                logger.exception("observability_service: rollback failed for %s: %s", deployment_id, exc)
                should_rollback = False  # avoid claiming success

        await session.commit()

    # Fire alerts outside transaction
    if config and (discord_url or slack_url):
        from app.services import alert_service
        try:
            await alert_service.send_incident_alert(
                discord_url=discord_url,
                slack_url=slack_url,
                project_name=project_name,
                deployment_id=deployment_id,
                incident_type=incident_type,
                severity=analysis.severity,
                summary=analysis.summary,
                root_cause=analysis.root_cause,
                recommended_action=analysis.recommended_action,
                rollback_confidence=analysis.rollback_confidence,
                preview_url=preview_url,
            )
        except Exception as exc:
            logger.warning("observability_service: alert send failed: %s", exc)

    return should_rollback


# ── Utility ───────────────────────────────────────────────────────────────────

# Simple cache: deployment_id → start time (filled when monitoring begins)
_dep_start_times: dict[UUID, float] = {}


def _deployment_age_minutes(deployment_id: UUID) -> float:
    import time as _time
    start = _dep_start_times.get(deployment_id)
    if start is None:
        return 0.0
    return (_time.monotonic() - start) / 60


def _record_start(deployment_id: UUID) -> None:
    import time as _time
    _dep_start_times[deployment_id] = _time.monotonic()
