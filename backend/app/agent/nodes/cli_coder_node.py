"""CLI Coder node: invokes Claude Code or Gemini CLI as a subprocess (Feature 002)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.agent.context_builder import ContextBuilder
from app.config import settings
from app.database import async_session_maker
from app.exceptions import SandboxEscapeError
from app.git.git_service import GitService
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.audit_log import AuditLogResult
from app.models.diff import Diff, DiffReviewStatus
from app.models.project import Project
from app.models.stream_event import StreamEventType
from app.models.task import Task, TaskStatus
from app.services.audit_service import CODER_AGENT_ID, finalise_log, write_audit, write_pending_log
from app.services.task_service import TaskService
from app.websocket.event_publisher import EventPublisher

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover
    def interrupt(_value: Any = None) -> None:  # type: ignore[override]
        return None

logger = logging.getLogger(__name__)

StateDict = dict[str, Any]

_CLI_TIMEOUT_SEC = 600.0


def _as_uuid(value: Any, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError(f"cli_coder_node requires UUID-compatible `{field}` in state.")


def _sandbox_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


async def _publish_event(
    task_id: UUID,
    agent_run_id: UUID | None,
    event_type: StreamEventType,
    body: dict[str, Any],
) -> None:
    """Publish a single event using a short-lived session."""
    try:
        async with async_session_maker() as s:
            await EventPublisher.publish(task_id, event_type, json.dumps(body, separators=(",", ":")), s, agent_run_id)
            await s.commit()
    except Exception:
        logger.exception("cli_coder_node: failed to publish event type=%s task_id=%s", event_type, task_id)


async def _run_with_session(state: StateDict) -> StateDict:
    project_id = _as_uuid(state["project_id"], "project_id")
    task_id = _as_uuid(state["task_id"], "task_id")
    backend = str(state.get("coding_backend", "groq"))

    async with async_session_maker() as session:
        task = await TaskService.get(session, task_id, project_id=project_id)
        project = await session.get(Project, project_id)

        agent_run = AgentRun(
            project_id=project_id,
            task_id=task_id,
            agent_type=AgentType.CODER,
            agent_version="1.0.0",
            status=AgentRunStatus.RUNNING,
            input_artifacts=[str(task_id)],
            output_artifacts=[],
        )
        session.add(agent_run)
        await session.flush()
        agent_run_id = agent_run.id

        sandbox = _sandbox_root(project_id)
        await asyncio.to_thread(GitService.init_repo, sandbox)
        await asyncio.to_thread(GitService.configure_identity, sandbox)
        await asyncio.to_thread(GitService.ensure_baseline_commit, sandbox)

        prompts = await ContextBuilder.build_coder_context(
            project_id,
            task_id,
            session,
            task=task,
            project=project,
        )
        prompt = prompts["system"] + "\n\n" + prompts["human"]

        if backend == "claude_code":
            cmd = f"{settings.claude_code_path} --print -p {shlex.quote(prompt)}"
            env = {**os.environ, "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "")}
        else:
            cmd = f"{settings.gemini_cli_path} -p {shlex.quote(prompt)}"
            env = {**os.environ, "GOOGLE_AI_API_KEY": settings.google_ai_api_key or ""}

        # Principle V: audit log BEFORE subprocess invocation
        audit_log = await write_pending_log(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="cli_coder",
            action_description=f"CLI coder ({backend}): subprocess invocation",
            agent_id=CODER_AGENT_ID,
            input_refs=[backend],
        )
        await session.commit()

        stderr_lines: list[str] = []
        exit_code: int | None = None

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(sandbox),
                env=env,
            )

            async def drain_stdout() -> None:
                assert proc.stdout is not None
                async for raw in proc.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    if line:
                        await _publish_event(task_id, agent_run_id, StreamEventType.THOUGHT, {"reasoning": line})

            async def drain_stderr() -> None:
                assert proc.stderr is not None
                async for raw in proc.stderr:
                    line = raw.decode(errors="replace").rstrip()
                    stderr_lines.append(line)
                    if line:
                        await _publish_event(task_id, agent_run_id, StreamEventType.ACTION, {"message": line})

            stdout_task = asyncio.create_task(drain_stdout())
            stderr_task = asyncio.create_task(drain_stderr())

            try:
                await asyncio.wait_for(proc.wait(), timeout=_CLI_TIMEOUT_SEC)
            except asyncio.TimeoutError:
                proc.kill()
                stdout_task.cancel()
                stderr_task.cancel()
                await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

                async with async_session_maker() as s:
                    t = await s.get(Task, task_id)
                    if t is not None:
                        t.status = TaskStatus.REJECTED
                        t.updated_at = datetime.now(timezone.utc)
                    run = await s.get(AgentRun, agent_run_id)
                    if run is not None:
                        run.status = AgentRunStatus.TIMEOUT
                        run.completed_at = datetime.now(timezone.utc)
                    await write_audit(
                        s,
                        project_id=project_id,
                        task_id=task_id,
                        action_type="cli_coder",
                        action_description=f"CLI_TIMEOUT: {backend} exceeded {int(_CLI_TIMEOUT_SEC)}s limit",
                        result=AuditLogResult.FAILURE,
                        agent_id=CODER_AGENT_ID,
                        output_refs=[str(agent_run_id)],
                    )
                    await s.commit()

                await _publish_event(
                    task_id,
                    agent_run_id,
                    StreamEventType.ERROR,
                    {
                        "code": "CLI_TIMEOUT",
                        "message": f"{backend} process exceeded {int(_CLI_TIMEOUT_SEC / 60)}-minute limit.",
                        "backend": backend,
                    },
                )

                async with async_session_maker() as s2:
                    await finalise_log(s2, audit_log.id, AuditLogResult.FAILURE, output_refs=["CLI_TIMEOUT"])
                    await s2.commit()

                return state

            await asyncio.gather(stdout_task, stderr_task)
            exit_code = proc.returncode

        except Exception as exc:
            logger.exception("cli_coder_node subprocess setup failed backend=%s", backend)
            async with async_session_maker() as s:
                await finalise_log(s, audit_log.id, AuditLogResult.FAILURE, output_refs=[str(exc)])
                await s.commit()
            await _publish_event(task_id, agent_run_id, StreamEventType.ERROR, {"code": "CLI_NOT_FOUND", "message": str(exc), "backend": backend})
            return {**state, "error": str(exc)}

        # --- Handle non-zero exit code ---
        if exit_code != 0:
            stderr_text = "\n".join(stderr_lines).lower()
            if exit_code == 127:
                error_code = "CLI_NOT_FOUND"
                error_msg = f"'{backend}' binary not found (PATH or configured path)."
            elif "auth" in stderr_text or "unauthorized" in stderr_text or "api key" in stderr_text:
                error_code = "CLI_AUTH_ERROR"
                error_msg = f"Authentication failed for {backend}. Check API key configuration."
            else:
                error_code = "CLI_NOT_FOUND"
                error_msg = f"{backend} exited with code {exit_code}."

            async with async_session_maker() as s:
                t = await s.get(Task, task_id)
                if t is not None:
                    t.status = TaskStatus.REJECTED
                    t.updated_at = datetime.now(timezone.utc)
                run = await s.get(AgentRun, agent_run_id)
                if run is not None:
                    run.status = AgentRunStatus.FAILURE
                    run.completed_at = datetime.now(timezone.utc)
                await finalise_log(s, audit_log.id, AuditLogResult.FAILURE, output_refs=[error_code])
                if t is not None:
                    from app.services.kanban_service import KanbanService

                    await KanbanService.on_agent_error(s, t)
                await s.commit()

            await _publish_event(
                task_id,
                agent_run_id,
                StreamEventType.ERROR,
                {"code": error_code, "message": error_msg, "backend": backend},
            )
            return {**state, "error": error_msg}

        # --- Success: generate diff, save, interrupt ---
        async with async_session_maker() as s:
            snap = await asyncio.to_thread(GitService.diff_staged, sandbox)
            diff_row = Diff(
                task_id=task_id,
                agent_run_id=agent_run_id,
                content=snap.unified or "(no staged diff)",
                original_content=snap.original_content,
                modified_content=snap.modified_content,
                files_affected=snap.files or [],
                review_status=DiffReviewStatus.PENDING,
            )
            s.add(diff_row)
            await s.flush()

            t = await s.get(Task, task_id)
            if t is not None:
                t.status = TaskStatus.REVIEW
                t.updated_at = datetime.now(timezone.utc)
                from app.services.kanban_service import KanbanService

                await KanbanService.on_task_needs_review(s, t)
            run = await s.get(AgentRun, agent_run_id)
            if run is not None:
                run.status = AgentRunStatus.AWAITING_HIL
                run.completed_at = datetime.now(timezone.utc)

            await finalise_log(s, audit_log.id, AuditLogResult.SUCCESS, output_refs=[str(diff_row.id)])
            await write_audit(
                s,
                project_id=project_id,
                task_id=task_id,
                action_type="cli_coder",
                action_description=f"CLI coder ({backend}): diff stored, awaiting HIL review.",
                result=AuditLogResult.SUCCESS,
                agent_id=CODER_AGENT_ID,
                output_refs=[str(diff_row.id)],
            )
            await s.commit()

        await _publish_event(
            task_id,
            agent_run_id,
            StreamEventType.STATUS_CHANGE,
            {"from": "CODING", "to": "REVIEWING", "reason": f"{backend} CLI completed; diff stored."},
        )

        try:
            interrupt(None)
        except (TypeError, RuntimeError):
            pass

    return state


async def run(state: StateDict) -> StateDict:
    """Entry point for LangGraph / background task (KanbanService)."""
    try:
        return await asyncio.wait_for(_run_with_session(state), timeout=float(_CLI_TIMEOUT_SEC) + 30)
    except asyncio.TimeoutError:
        logger.exception("cli_coder_node outer timeout")
        return {**state, "error": "cli_coder_node outer timeout"}
    except Exception as exc:
        logger.exception("cli_coder_node failed")
        return {**state, "error": str(exc)}
