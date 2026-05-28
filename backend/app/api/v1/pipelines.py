"""Pipeline API — runs, steps, deployments, deployment configs, SSE stream."""

from __future__ import annotations

import json
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_any_member, require_leader_or_above
from app.models.deployment import Deployment
from app.models.pipeline_step import PipelineStep
from app.models.project_member import ProjectMember
from app.models.step_failure_analysis import StepFailureAnalysis
from app.pipeline import event_bus
from app.pipeline.pipeline_service import PipelineService
from app.schemas.pipeline import (
    DeploymentConfigCreate,
    DeploymentConfigOut,
    DeploymentConfigTestRequest,
    DeploymentConfigTestResponse,
    DeploymentOut,
    FailureAnalysisOut,
    PipelineRunOut,
)
from app.services import deployment_service
from app.services import failure_analysis_service

router = APIRouter(tags=["pipelines"])


# ── Pipeline runs ─────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/pipeline-runs", response_model=list[PipelineRunOut])
async def list_pipeline_runs(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PipelineRunOut]:
    runs = await PipelineService.list_runs_for_project(session, project_id)
    return [PipelineRunOut.model_validate(r) for r in runs]


@router.get("/projects/{project_id}/tasks/{task_id}/pipeline-runs", response_model=list[PipelineRunOut])
async def list_task_pipeline_runs(
    project_id: UUID,
    task_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[PipelineRunOut]:
    runs = await PipelineService.list_runs_for_task(session, task_id)
    return [PipelineRunOut.model_validate(r) for r in runs]


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunOut)
async def get_pipeline_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PipelineRunOut:
    run = await PipelineService.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return PipelineRunOut.model_validate(run)


# ── SSE live stream ───────────────────────────────────────────────────────────

@router.get("/pipeline-runs/{run_id}/stream")
async def stream_pipeline_run(
    run_id: UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Server-Sent Events: pipeline_started · step_started · step_completed ·
    pipeline_completed/failed · preview_url · ping (keep-alive)."""
    run = await PipelineService.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Already finished — send full snapshot immediately
        if run.status in ("success", "failure", "cancelled"):
            # Load associated deployment for preview_url
            dep = await session.scalar(select(Deployment).where(Deployment.run_id == run_id))
            snapshot = {
                "type": "pipeline_snapshot",
                "run_id": str(run_id),
                "status": run.status,
                "preview_url": dep.preview_url if dep else None,
                "steps": [
                    {
                        "step_key": s.step_key,
                        "status": s.status,
                        "duration_ms": s.duration_ms,
                        "ai_reasoning": s.ai_reasoning,
                        "logs": (s.logs or "")[:4096],
                    }
                    for s in (run.steps or [])
                ],
            }
            yield f"data: {json.dumps(snapshot)}\n\n"
            return

        async for chunk in event_bus.subscribe(str(run_id)):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Deployments ───────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/deployments", response_model=list[DeploymentOut])
async def list_deployments(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DeploymentOut]:
    deps = await PipelineService.list_deployments_for_project(session, project_id)
    return [DeploymentOut.model_validate(d) for d in deps]


@router.get("/projects/{project_id}/deployments/{deployment_id}", response_model=DeploymentOut)
async def get_deployment(
    project_id: UUID,
    deployment_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentOut:
    dep = await session.scalar(
        select(Deployment).where(
            Deployment.id == deployment_id,
            Deployment.project_id == project_id,
        )
    )
    if dep is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")
    return DeploymentOut.model_validate(dep)


# ── Deployment config CRUD ────────────────────────────────────────────────────

@router.get("/projects/{project_id}/deployment-config", response_model=DeploymentConfigOut | None)
async def get_deployment_config(
    project_id: UUID,
    _member: Annotated[ProjectMember, require_any_member],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentConfigOut | None:
    cfg = await deployment_service.get_config(session, project_id)
    return DeploymentConfigOut.model_validate(cfg) if cfg else None


@router.put("/projects/{project_id}/deployment-config", response_model=DeploymentConfigOut)
async def upsert_deployment_config(
    project_id: UUID,
    body: DeploymentConfigCreate,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentConfigOut:
    cfg = await deployment_service.upsert_config(
        session,
        project_id=project_id,
        provider=body.provider,
        token=body.token,
        project_name=body.project_name,
        team_id=body.team_id,
        base_url=body.base_url,
        enabled=body.enabled,
    )
    await session.commit()
    return DeploymentConfigOut.model_validate(cfg)


@router.post("/projects/{project_id}/deployment-config/test", response_model=DeploymentConfigTestResponse)
async def test_deployment_config(
    project_id: UUID,
    body: DeploymentConfigTestRequest,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeploymentConfigTestResponse:
    """Validate provider credentials without saving them."""
    ok, message = await deployment_service.test_config(
        provider=body.provider,
        token=body.token,
        project_name=body.project_name,
        team_id=body.team_id,
    )
    return DeploymentConfigTestResponse(ok=ok, message=message)


@router.delete("/projects/{project_id}/deployment-config", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_deployment_config(
    project_id: UUID,
    _leader: Annotated[ProjectMember, require_leader_or_above],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    cfg = await deployment_service.get_config(session, project_id)
    if cfg is not None:
        await session.delete(cfg)
        await session.commit()


# ── Failure analyses ──────────────────────────────────────────────────────────

@router.get(
    "/pipeline-runs/{run_id}/failure-analyses",
    response_model=list[FailureAnalysisOut],
)
async def list_failure_analyses(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[FailureAnalysisOut]:
    """Return all AI failure analyses for a pipeline run."""
    rows = await failure_analysis_service.get_analyses_for_run(session, run_id)
    return [FailureAnalysisOut.model_validate(r) for r in rows]


@router.get(
    "/pipeline-steps/{step_id}/failure-analysis",
    response_model=FailureAnalysisOut | None,
)
async def get_step_failure_analysis(
    step_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FailureAnalysisOut | None:
    """Return the most recent AI failure analysis for a pipeline step."""
    row = await failure_analysis_service.get_analysis_for_step(session, step_id)
    return FailureAnalysisOut.model_validate(row) if row else None
