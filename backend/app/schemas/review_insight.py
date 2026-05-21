"""Reviewer agent output for PO (Phase C)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.agent_run import AgentRunStatus

ReviewerVerdict = Literal["approve_suggested", "needs_changes", "unclear"]


class ReviewFinding(BaseModel):
    severity: str = "info"
    message: str = ""


class ReviewInsightResponse(BaseModel):
    """Latest reviewer ``agent_run`` for a task in review."""

    available: bool
    agent_run_id: UUID | None = None
    status: AgentRunStatus | None = None
    verdict: ReviewerVerdict | None = None
    summary: str | None = None
    findings: list[ReviewFinding] = Field(default_factory=list)
    model: str | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_agent_result(cls, run_id: UUID, status: AgentRunStatus, result: dict[str, Any] | None) -> ReviewInsightResponse:
        if not result:
            return cls(available=False, agent_run_id=run_id, status=status)
        findings_raw = result.get("findings")
        findings: list[ReviewFinding] = []
        if isinstance(findings_raw, list):
            for item in findings_raw:
                if isinstance(item, dict):
                    findings.append(
                        ReviewFinding(
                            severity=str(item.get("severity", "info")),
                            message=str(item.get("message", "")),
                        )
                    )
        verdict = result.get("verdict")
        if verdict not in ("approve_suggested", "needs_changes", "unclear"):
            verdict = "unclear"
        model_id = result.get("model")
        return cls(
            available=True,
            agent_run_id=run_id,
            status=status,
            verdict=verdict,
            summary=str(result.get("summary", "")),
            findings=findings,
            model=str(model_id) if model_id else None,
        )
