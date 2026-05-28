"""Pydantic schemas for Phase 4 DevOps endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Health checks ─────────────────────────────────────────────────────────────

class HealthCheckOut(BaseModel):
    id: UUID
    deployment_id: UUID
    project_id: UUID
    status: str          # healthy | degraded | unreachable | unknown
    http_status: int | None = None
    latency_ms: int | None = None
    response_snippet: str | None = None
    error_message: str | None = None
    checked_at: datetime

    model_config = {"from_attributes": True}


# ── Incidents ─────────────────────────────────────────────────────────────────

class IncidentOut(BaseModel):
    id: UUID
    deployment_id: UUID
    project_id: UUID
    incident_type: str
    severity: str       # low | medium | high | critical
    title: str
    description: str
    ai_reasoning: str | None = None
    risk_score: float | None = None
    metric_snapshot: dict[str, Any] | None = None
    rollback_triggered: bool
    resolved: bool
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_snapshot(cls, obj: Any) -> "IncidentOut":
        import json
        data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
        if data.get("metric_snapshot"):
            try:
                data["metric_snapshot"] = json.loads(data["metric_snapshot"])
            except Exception:
                data["metric_snapshot"] = None
        return cls(**data)


# ── Rollback events ───────────────────────────────────────────────────────────

class RollbackEventOut(BaseModel):
    id: UUID
    deployment_id: UUID
    project_id: UUID
    triggered_by: str   # manual | ai_anomaly | health_fail
    previous_deployment_id: UUID | None = None
    status: str         # pending | rolling_back | completed | failed | skipped
    reason: str
    ai_reasoning: str | None = None
    alert_sent: bool
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Risk assessment (returned from pre-deploy check) ─────────────────────────

class RiskAssessmentOut(BaseModel):
    risk_score: float
    risk_level: str        # low | medium | high | critical
    reasoning: str
    risk_factors: list[str] = []
    blast_radius: str = ""
    safe_to_deploy: bool
    via_llm: bool


# ── Deployment health summary (dashboard) ────────────────────────────────────

class DeploymentHealthSummary(BaseModel):
    deployment_id: UUID
    project_id: UUID
    health_status: str | None = None  # unknown | healthy | degraded | critical
    last_checked_at: datetime | None = None
    latest_http_status: int | None = None
    latest_latency_ms: int | None = None
    consecutive_failures: int = 0
    open_incidents: int = 0
    last_rollback_at: datetime | None = None


# ── Alert config update ───────────────────────────────────────────────────────

class AlertConfigUpdate(BaseModel):
    discord_webhook_url: str | None = Field(None, max_length=500)
    slack_webhook_url: str | None = Field(None, max_length=500)
    health_check_path: str | None = Field(None, max_length=255)
    alert_on_anomaly: bool | None = None
    monitor_duration_minutes: int | None = Field(None, ge=1, le=60)


class AlertConfigOut(BaseModel):
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    health_check_path: str | None = None
    alert_on_anomaly: bool
    monitor_duration_minutes: int

    model_config = {"from_attributes": True}


# ── Manual rollback request ───────────────────────────────────────────────────

class ManualRollbackRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000)
