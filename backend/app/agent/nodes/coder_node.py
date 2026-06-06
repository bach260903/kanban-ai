"""Coder agent: sandbox tools + Groq tool-calling + git diff + Diff row + HIL (US8 / T058)."""

from __future__ import annotations

import asyncio
import json
import logging
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context_builder import ContextBuilder
from app.config import settings
from app.llm.factory import coder_llm_configured, create_coder_llm
from app.llm.invoke_helpers import ainvoke_llm
from app.database import async_session_maker
from app.exceptions import PauseSignal, SandboxEscapeError
from app.git.git_service import GitService
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.audit_log import AuditLogResult
from app.models.diff import Diff, DiffReviewStatus
from app.models.project import Project
from app.models.stream_event import StreamEventType
from app.models.task import Task, TaskStatus
from app.services.audit_service import CODER_AGENT_ID, finalise_log, write_audit, write_pending_log
from app.services.pause_service import PauseService
from app.services.task_service import TaskService
from app.websocket.event_publisher import EventPublisher

pause_service = PauseService

try:
    from langgraph.types import interrupt
except Exception:  # pragma: no cover
    def interrupt(_value: Any = None) -> None:  # type: ignore[override]
        return None


logger = logging.getLogger(__name__)

StateDict = dict[str, Any]


async def _publish_event(
    session: AsyncSession,
    task_id: UUID,
    agent_run_id: UUID | None,
    event_type: StreamEventType,
    body: dict[str, Any],
) -> None:
    await EventPublisher.publish(
        task_id,
        event_type,
        json.dumps(body, separators=(",", ":")),
        session,
        agent_run_id,
    )


def _tool_result_body(tool_name: str, call_id: str, result: str) -> dict[str, Any]:
    success = not result.startswith("ERROR:")
    lim = 2000
    truncated = len(result) > lim
    preview = result[:lim] if truncated else result
    return {
        "tool_name": tool_name,
        "call_id": call_id,
        "success": success,
        "result": preview,
        "result_truncated": truncated,
    }


def _error_body(exc: BaseException, *, recoverable: bool = False) -> dict[str, Any]:
    return {
        "error_type": type(exc).__name__,
        "message": str(exc),
        "recoverable": recoverable,
        "step": "CODING",
    }


def _is_rate_limit(exc: BaseException) -> bool:
    """Return True if *exc* is a provider rate-limit / quota error."""
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return (
        "ratelimit" in name
        or "rate_limit" in name
        or "429" in msg
        or "rate limit" in msg
        or "quota" in msg
        or "tokens per day" in msg
        or "tokens per minute" in msg
    )


def _rate_limit_message(exc: BaseException) -> str:
    """Extract a human-friendly wait message from a rate-limit error."""
    import re
    raw = str(exc)
    # Extract "try again in Xm Ys" from Groq error body
    m = re.search(r"try again in ([\d\w. ]+?)(?:\.|'|\"|$)", raw, re.IGNORECASE)
    wait = m.group(1).strip() if m else None
    # Extract limit info
    lim = re.search(r"Limit (\d+)", raw)
    used = re.search(r"Used (\d+)", raw)
    limit_info = ""
    if lim and used:
        limit_info = f" (quota: {int(used.group(1)):,}/{int(lim.group(1)):,} tokens used)"
    if wait:
        return f"API rate limit reached{limit_info}. Please wait {wait} then move the task back to In Progress to retry."
    return f"API rate limit reached{limit_info}. Please wait a few minutes then retry."

_MAX_READ = 400_000
_MAX_WRITE = 500_000
_MAX_TOOL_ROUNDS = 12  # room for the write → run tests → fix → re-run self-verify loop

_WARN_LINES = 200    # soft warning returned to agent
_HARD_LINES = 500    # hard reject — force agent to split

# Auto-generated files that are exempt from line limits
_GENERATED_FILENAMES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", ".agent_baseline", "MEMORY.md",
})
_CODER_TASK_TIMEOUT_SEC = 600


def _request_hil_interrupt() -> None:
    try:
        interrupt(None)
    except TypeError:
        interrupt()
    except RuntimeError:
        pass


def _as_uuid(value: Any, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        return UUID(value)
    raise ValueError(f"coder_node requires UUID-compatible `{field}` in state.")


def _sandbox_root(project_id: UUID) -> Path:
    root = Path(settings.sandbox_root).expanduser().resolve()
    proj = (root / str(project_id)).resolve()
    try:
        proj.relative_to(root)
    except ValueError as exc:
        raise SandboxEscapeError("Resolved sandbox path escapes SANDBOX_ROOT.") from exc
    return proj


def _safe_path(sandbox: Path, relative_path: str) -> Path:
    rel = relative_path.replace("\\", "/").lstrip("/")
    target = (sandbox / rel).resolve()
    try:
        target.relative_to(sandbox)
    except ValueError as exc:
        raise SandboxEscapeError("Path escapes sandbox.") from exc
    return target


def _fs_read(sandbox: Path, relative_path: str) -> str:
    path = _safe_path(sandbox, relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {relative_path}")
    data = path.read_text(encoding="utf-8", errors="replace")
    if len(data) > _MAX_READ:
        return data[:_MAX_READ] + "\n…(truncated)"
    return data


def _fs_write(sandbox: Path, relative_path: str, content: str) -> str:
    if len(content) > _MAX_WRITE:
        raise ValueError("Content exceeds maximum size (500 KB).")

    filename = relative_path.rsplit("/", 1)[-1]
    is_generated = filename in _GENERATED_FILENAMES or filename.endswith(".lock")

    if not is_generated:
        line_count = content.count("\n") + 1
        if line_count > _HARD_LINES:
            raise ValueError(
                f"File '{relative_path}' has {line_count} lines — maximum is {_HARD_LINES}. "
                "Split it into smaller focused modules (e.g. separate the logic, models, "
                "and utils into distinct files) then write each one separately."
            )

    path = _safe_path(sandbox, relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    result = f"Wrote {len(content)} bytes to {relative_path}"

    if not is_generated:
        line_count = content.count("\n") + 1
        if line_count > _WARN_LINES:
            result += (
                f"\nWARNING: {relative_path} has {line_count} lines (limit: {_WARN_LINES}). "
                "You MUST split this into smaller modules before finishing — "
                "do not call any more tools until you have refactored it."
            )
    return result


# Executables the coder may run to verify its own work (no shell; args tokenised).
# git + test/compile/lint runners so the agent can catch broken cross-file
# references (e.g. calling a method the model never defines) before finishing.
_ALLOWED_TERMINAL_CMDS = {
    "git", "python", "python3", "pytest", "ruff", "node", "npx", "npm",
}


def _run_terminal_command(sandbox: Path, command: str) -> str:
    """Run a whitelisted verification command (git + test/compile/lint) in the sandbox.

    No shell is used (arguments are tokenised), only whitelisted executables may run,
    and each command is capped at 60s per the security constitution.
    """
    raw = command.strip()
    if not raw:
        raise ValueError("Empty command.")
    if len(raw) > 500:
        raise ValueError("Command too long.")
    parts = shlex.split(raw)
    if not parts:
        raise ValueError("Empty command.")
    if parts[0] not in _ALLOWED_TERMINAL_CMDS:
        raise ValueError(
            f"Command '{parts[0]}' is not allowed. "
            f"Allowed: {', '.join(sorted(_ALLOWED_TERMINAL_CMDS))}."
        )
    proc = subprocess.run(
        parts,
        cwd=sandbox,
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = ((proc.stdout or "") + (proc.stderr or ""))[:8000]
    if proc.returncode != 0:
        return f"(exit {proc.returncode})\n{out}"
    return out or "(no output)"


@tool
def read_file(relative_path: str) -> str:
    """Read a UTF-8 text file from the project sandbox (relative path, forward slashes)."""
    return relative_path


@tool
def write_file(relative_path: str, content: str) -> str:
    """Create or overwrite a UTF-8 text file under the sandbox."""
    return relative_path


@tool
def run_terminal(command: str) -> str:
    """Run ONE verification command in the sandbox to check your own work.

    Allowed: git, python, pytest, ruff, node, npx, npm. Use it to run your tests and
    compile/lint checks before finishing, e.g. `python -m pytest -q`,
    `python -m py_compile models/user.py`, `ruff check .`, `node --check app.js`.
    No shell metacharacters; one command per call; 60s timeout."""
    return command


_CODER_TOOLS = [read_file, write_file, run_terminal]


async def _finalize_agent_run(
    session: AsyncSession,
    agent_run_id: UUID,
    status: AgentRunStatus,
) -> None:
    run = await session.get(AgentRun, agent_run_id)
    if run is None:
        return
    run.status = status
    if status in (
        AgentRunStatus.SUCCESS,
        AgentRunStatus.FAILURE,
        AgentRunStatus.TIMEOUT,
        AgentRunStatus.AWAITING_HIL,
    ):
        run.completed_at = datetime.now(timezone.utc)
    await session.flush()


async def _pause_checkpoint(
    session: AsyncSession,
    *,
    project_id: UUID,
    task_id: UUID,
    agent_run_id: UUID,
) -> None:
    """If task is paused (Redis), finalize run as ``paused``, publish ``STATUS_CHANGE``, commit, stop (T086)."""
    if not await pause_service.is_paused(task_id):
        return
    await _finalize_agent_run(session, agent_run_id, AgentRunStatus.PAUSED)
    await _publish_event(
        session,
        task_id,
        agent_run_id,
        StreamEventType.STATUS_CHANGE,
        {
            "from": "CODING",
            "to": "PAUSED",
            "reason": "pause_requested",
        },
    )
    await write_audit(
        session,
        project_id=project_id,
        task_id=task_id,
        action_type="coder_paused",
        action_description="Coder stopped: Redis pause flag set for task.",
        result=AuditLogResult.SUCCESS,
        agent_id=CODER_AGENT_ID,
        input_refs=[],
        output_refs=[str(agent_run_id)],
    )
    await session.commit()
    raise PauseSignal()


class _TaskCancelledError(Exception):
    """Raised when the task is no longer in_progress (cancelled / reset by user)."""


async def _check_task_cancelled(
    session: AsyncSession,
    *,
    task_id: UUID,
    agent_run_id: UUID,
) -> None:
    """Re-fetch task from DB; raise _TaskCancelledError if it is no longer in_progress.

    Forces a fresh DB read: the coder's session has the task cached as IN_PROGRESS
    from the start of the run, so a plain ``session.get`` would return that stale
    copy and never observe a cancel committed by another session.
    """
    fresh = await session.get(Task, task_id)
    if fresh is not None:
        await session.refresh(fresh, attribute_names=["status"])
    if fresh is None or fresh.status != TaskStatus.IN_PROGRESS:
        status_str = str(fresh.status) if fresh else "deleted"
        logger.warning(
            "coder_node: task %s is no longer in_progress (status=%s) — aborting cleanly",
            task_id,
            status_str,
        )
        await _finalize_agent_run(session, agent_run_id, AgentRunStatus.FAILURE)
        raise _TaskCancelledError(
            f"Task was cancelled while agent was running (status={status_str})."
        )


async def _execute_tool(
    *,
    session: AsyncSession,
    sandbox: Path,
    project_id: UUID,
    task_id: UUID,
    agent_run_id: UUID,
    name: str,
    args: dict[str, Any],
) -> str:
    if name == "read_file":
        rel = str(args.get("relative_path", "")).strip()
        log = await write_pending_log(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="coder_read_file",
            action_description=f"read_file `{rel}`",
            agent_id=CODER_AGENT_ID,
            input_refs=[rel],
        )
        try:
            body = await asyncio.to_thread(_fs_read, sandbox, rel)
            await finalise_log(session, log.id, AuditLogResult.SUCCESS, output_refs=[rel])
            return body
        except Exception as exc:
            await finalise_log(
                session,
                log.id,
                AuditLogResult.FAILURE,
                output_refs=[str(exc)],
            )
            return f"ERROR: {exc}"

    if name == "write_file":
        rel = str(args.get("relative_path", "")).strip()
        content = str(args.get("content", ""))
        log = await write_pending_log(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="coder_write_file",
            action_description=f"write_file `{rel}` ({len(content)} chars)",
            agent_id=CODER_AGENT_ID,
            input_refs=[rel],
        )
        try:
            await _publish_event(
                session,
                task_id,
                agent_run_id,
                StreamEventType.ACTION,
                {
                    "action_type": "write_file",
                    "description": f"Writing `{rel}` ({len(content)} chars)",
                    "target": rel,
                    "audit_log_id": str(log.id),
                },
            )
            msg = await asyncio.to_thread(_fs_write, sandbox, rel, content)
            await finalise_log(session, log.id, AuditLogResult.SUCCESS, output_refs=[rel])
            return msg
        except Exception as exc:
            await finalise_log(
                session,
                log.id,
                AuditLogResult.FAILURE,
                output_refs=[str(exc)],
            )
            return f"ERROR: {exc}"

    if name == "run_terminal":
        cmd = str(args.get("command", "")).strip()
        log = await write_pending_log(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="coder_run_terminal",
            action_description=f"run_terminal `{cmd}`",
            agent_id=CODER_AGENT_ID,
            input_refs=[cmd],
        )
        try:
            await _publish_event(
                session,
                task_id,
                agent_run_id,
                StreamEventType.ACTION,
                {
                    "action_type": "run_command",
                    "description": f"Running sandbox git command ({len(cmd)} chars)",
                    "target": cmd[:500],
                    "audit_log_id": str(log.id),
                },
            )
            out = await asyncio.to_thread(_run_terminal_command, sandbox, cmd)
            await finalise_log(session, log.id, AuditLogResult.SUCCESS, output_refs=[cmd])
            return out
        except Exception as exc:
            await finalise_log(
                session,
                log.id,
                AuditLogResult.FAILURE,
                output_refs=[str(exc)],
            )
            return f"ERROR: {exc}"

    return f"ERROR: unknown tool {name}"


async def _run_with_session(state: StateDict) -> StateDict:
    project_id = _as_uuid(state["project_id"], "project_id")
    task_id = _as_uuid(state["task_id"], "task_id")

    async with async_session_maker() as session:
        task = await TaskService.get(session, task_id, project_id=project_id)
        project = await session.get(Project, project_id)
        if project is None:
            raise ValueError("Project not found.")

        existing_raw = state.get("agent_run_id")
        if existing_raw is not None:
            pre_id = _as_uuid(existing_raw, "agent_run_id")
            agent_run = await session.get(AgentRun, pre_id)
            if agent_run is None or agent_run.task_id != task_id or agent_run.project_id != project_id:
                raise ValueError("agent_run_id does not match this task/project.")
        else:
            agent_run = AgentRun(
                project_id=project_id,
                task_id=task_id,
                agent_type=AgentType.CODER,
                agent_version="1.0.0",
                status=AgentRunStatus.RUNNING,
                input_artifacts=[str(task.id)],
                output_artifacts=[],
            )
            session.add(agent_run)
            await session.flush()
        agent_run_id = agent_run.id

        await _pause_checkpoint(session, project_id=project_id, task_id=task_id, agent_run_id=agent_run_id)

        sandbox = _sandbox_root(project_id)
        await asyncio.to_thread(GitService.init_repo, sandbox)
        await asyncio.to_thread(GitService.configure_identity, sandbox)
        await asyncio.to_thread(GitService.ensure_baseline_commit, sandbox)

        await _pause_checkpoint(session, project_id=project_id, task_id=task_id, agent_run_id=agent_run_id)

        po = state.get("po_feedback")
        po_kw = po.strip()[:20_000] if isinstance(po, str) and po.strip() else None
        ic_raw = state.get("inline_comments")
        ic_kw: list[dict[str, str | int]] | None = None
        if isinstance(ic_raw, list) and ic_raw:
            parsed: list[dict[str, str | int]] = []
            for item in ic_raw:
                if not isinstance(item, dict):
                    continue
                fp = item.get("file_path")
                ln = item.get("line_number")
                ct = item.get("comment_text")
                if not isinstance(fp, str) or not isinstance(ct, str):
                    continue
                if isinstance(ln, bool):
                    continue
                if isinstance(ln, int):
                    ln_int = ln
                else:
                    try:
                        ln_int = int(ln)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        continue
                parsed.append({"file_path": fp, "line_number": ln_int, "comment_text": ct})
            if parsed:
                ic_kw = parsed
        ci_report = state.get("ci_failure_report") or None
        prompts = await ContextBuilder.build_coder_context(
            project_id,
            task_id,
            session,
            task=task,
            project=project,
            po_feedback=po_kw,
            inline_comments=ic_kw,
            ci_failure_report=ci_report,
        )
        system = prompts["system"]
        human = prompts["human"]
        messages: list[Any] = [
            SystemMessage(content=system),
            HumanMessage(content=human),
        ]

        if not coder_llm_configured():
            await _publish_event(
                session,
                task_id,
                agent_run_id,
                StreamEventType.THOUGHT,
                {
                    "reasoning": (
                        f"Coder LLM not configured (CODER_LLM_PROVIDER={settings.coder_llm_provider}); "
                        "writing stub notes and exiting without LLM."
                    ),
                },
            )
            await asyncio.to_thread(
                _fs_write,
                sandbox,
                "agent_notes.md",
                f"# Coder stub\n\nNo LLM key configured. Task: {task.title}\n",
            )
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
            session.add(diff_row)
            await session.flush()
            await write_audit(
                session,
                project_id=project_id,
                task_id=task_id,
                action_type="coder_node",
                action_description="LLM API key missing — placeholder diff recorded.",
                result=AuditLogResult.FAILURE,
                agent_id=CODER_AGENT_ID,
                output_refs=[str(diff_row.id)],
            )
            task.status = TaskStatus.REVIEW
            task.updated_at = datetime.now(timezone.utc)
            from app.services.kanban_service import KanbanService

            await KanbanService.on_task_needs_review(session, task)
            await _publish_event(
                session,
                task_id,
                agent_run_id,
                StreamEventType.STATUS_CHANGE,
                {
                    "from": "CODING",
                    "to": "REVIEWING",
                    "reason": "LLM API key missing — placeholder diff recorded.",
                },
            )
            await _finalize_agent_run(session, agent_run_id, AgentRunStatus.AWAITING_HIL)
            await session.commit()
            _request_hil_interrupt()
            return state

        llm = create_coder_llm(temperature=0.1).bind_tools(_CODER_TOOLS)

        rounds = 0
        while rounds < _MAX_TOOL_ROUNDS:
            await _pause_checkpoint(session, project_id=project_id, task_id=task_id, agent_run_id=agent_run_id)
            await _check_task_cancelled(session, task_id=task_id, agent_run_id=agent_run_id)
            rounds += 1
            llm_log = await write_pending_log(
                session,
                project_id=project_id,
                task_id=task_id,
                action_type="coder_llm",
                action_description=f"Coder LLM invoke (round {rounds})",
                agent_id=CODER_AGENT_ID,
                input_refs=[],
            )
            try:
                await _publish_event(
                    session,
                    task_id,
                    agent_run_id,
                    StreamEventType.THOUGHT,
                    {
                        "reasoning": f"Coder LLM round {rounds}: invoking model to decide the next sandbox actions.",
                    },
                )
                ai = cast(AIMessage, await ainvoke_llm(llm, messages))
                await finalise_log(session, llm_log.id, AuditLogResult.SUCCESS)
            except Exception as exc:
                await finalise_log(session, llm_log.id, AuditLogResult.FAILURE, output_refs=[str(exc)])
                if _is_rate_limit(exc):
                    # Graceful rate-limit handling: revert task to TODO with clear message
                    friendly = _rate_limit_message(exc)
                    await _publish_event(
                        session, task_id, agent_run_id, StreamEventType.ERROR,
                        {
                            "error_type": "RateLimitError",
                            "message": friendly,
                            "recoverable": True,
                            "step": "CODING",
                        },
                    )
                    await _publish_event(
                        session, task_id, agent_run_id, StreamEventType.STATUS_CHANGE,
                        {"from": "CODING", "to": "TODO", "reason": friendly},
                    )
                    task.status = TaskStatus.TODO
                    task.updated_at = datetime.now(timezone.utc)
                    await _finalize_agent_run(session, agent_run_id, AgentRunStatus.FAILURE)
                    run = await session.get(AgentRun, agent_run_id)
                    if run is not None:
                        run.result = {"error": friendly, "code": "RATE_LIMIT"}
                    await session.commit()
                    return state
                await _publish_event(session, task_id, agent_run_id, StreamEventType.ERROR, _error_body(exc))
                raise

            messages.append(ai)
            tool_calls = getattr(ai, "tool_calls", None) or []
            if not tool_calls:
                break

            for tc in tool_calls:
                await _pause_checkpoint(session, project_id=project_id, task_id=task_id, agent_run_id=agent_run_id)
                name = tc.get("name", "")
                args = cast(dict[str, Any], tc.get("args", {}))
                tid = tc.get("id", "") or f"tool-{name}-{rounds}"
                call_id = str(tid)
                tc_args: dict[str, Any] = {}
                if name == "read_file":
                    tc_args = {"path": str(args.get("relative_path", "")).strip()}
                elif name == "write_file":
                    tc_args = {"path": str(args.get("relative_path", "")).strip()}
                elif name == "run_terminal":
                    tc_args = {"path": str(args.get("command", "")).strip()[:500]}
                await _publish_event(
                    session,
                    task_id,
                    agent_run_id,
                    StreamEventType.TOOL_CALL,
                    {
                        "tool_name": name,
                        "call_id": call_id,
                        "arguments": tc_args,
                    },
                )
                out = await _execute_tool(
                    session=session,
                    sandbox=sandbox,
                    project_id=project_id,
                    task_id=task_id,
                    agent_run_id=agent_run_id,
                    name=name,
                    args=args,
                )
                await _publish_event(
                    session,
                    task_id,
                    agent_run_id,
                    StreamEventType.TOOL_RESULT,
                    _tool_result_body(name, call_id, out),
                )
                messages.append(ToolMessage(content=out, tool_call_id=str(tid)))

        await _pause_checkpoint(session, project_id=project_id, task_id=task_id, agent_run_id=agent_run_id)
        # Final guard: abort if task was cancelled while coding was in progress
        await _check_task_cancelled(session, task_id=task_id, agent_run_id=agent_run_id)

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
        session.add(diff_row)
        await session.flush()
        task.status = TaskStatus.REVIEW
        task.updated_at = datetime.now(timezone.utc)
        from app.services.kanban_service import KanbanService

        await KanbanService.on_task_needs_review(session, task)
        await _publish_event(
            session,
            task_id,
            agent_run_id,
            StreamEventType.STATUS_CHANGE,
            {
                "from": "CODING",
                "to": "REVIEWING",
                "reason": "Agent completed implementation; diff stored.",
            },
        )
        await _finalize_agent_run(session, agent_run_id, AgentRunStatus.AWAITING_HIL)
        await write_audit(
            session,
            project_id=project_id,
            task_id=task_id,
            action_type="coder_node",
            action_description="Coder produced diff; awaiting PO review (HIL).",
            result=AuditLogResult.SUCCESS,
            agent_id=CODER_AGENT_ID,
            output_refs=[str(diff_row.id)],
        )
        await session.commit()
        _request_hil_interrupt()
    return state


async def run(state: StateDict) -> StateDict:
    """Entry point for LangGraph / background task (``KanbanService``)."""
    try:
        return await asyncio.wait_for(_run_with_session(state), timeout=float(_CODER_TASK_TIMEOUT_SEC))
    except PauseSignal:
        return state
    except _TaskCancelledError as exc:
        # Task was cancelled by user while agent was running — exit silently (not an error)
        logger.info("coder_node: aborted cleanly — %s", exc)
        return {**state, "cancelled": True}
    except asyncio.TimeoutError:
        logger.exception("coder_node timed out")
        err_msg = f"Coder exceeded the {_CODER_TASK_TIMEOUT_SEC}s task budget (timeout)."
        try:
            async with async_session_maker() as session:
                task_id = state.get("task_id")
                project_id = state.get("project_id")
                if isinstance(task_id, UUID) and isinstance(project_id, UUID):
                    task = await session.get(Task, task_id)
                    if task is not None:
                        task.status = TaskStatus.TODO
                        task.updated_at = datetime.now(timezone.utc)
                    run_result = await session.execute(
                        select(AgentRun)
                        .where(
                            AgentRun.task_id == task_id,
                            AgentRun.status == AgentRunStatus.RUNNING,
                        )
                        .order_by(AgentRun.started_at.desc())
                        .limit(1)
                    )
                    open_run = run_result.scalar_one_or_none()
                    if open_run is not None:
                        open_run.status = AgentRunStatus.TIMEOUT
                        open_run.completed_at = datetime.now(timezone.utc)
                        open_run.result = {
                            "error": err_msg,
                            "detail": "Task moved to rejected.",
                        }
                    rid = open_run.id if open_run else None
                    await EventPublisher.publish(
                        task_id,
                        StreamEventType.ERROR,
                        json.dumps(
                            {
                                "error_type": "TimeoutError",
                                "message": err_msg,
                                "recoverable": False,
                                "step": "CODING",
                            },
                            separators=(",", ":"),
                        ),
                        session,
                        rid,
                    )
                    if task is not None:
                        await EventPublisher.publish(
                            task_id,
                            StreamEventType.STATUS_CHANGE,
                            json.dumps(
                                {
                                    "from": "CODING",
                                    "to": "TODO",
                                    "reason": err_msg,
                                },
                                separators=(",", ":"),
                            ),
                            session,
                            rid,
                        )
                    await write_audit(
                        session,
                        project_id=project_id,
                        task_id=task_id if isinstance(task_id, UUID) else None,
                        action_type="coder_node",
                        action_description=f"ERROR: {err_msg}",
                        result=AuditLogResult.FAILURE,
                        agent_id=CODER_AGENT_ID,
                        output_refs=[str(open_run.id)] if open_run else [],
                    )
                    if task is not None:
                        from app.services.kanban_service import KanbanService

                        await KanbanService.on_agent_error(session, task)
                    await session.commit()
        except Exception:
            logger.exception("coder_node timeout cleanup failed")
        return {**state, "error": err_msg}
    except Exception as exc:
        logger.exception("coder_node failed")
        try:
            async with async_session_maker() as session:
                task_id = state.get("task_id")
                project_id = state.get("project_id")
                if isinstance(task_id, UUID) and isinstance(project_id, UUID):
                    run_q = await session.execute(
                        select(AgentRun)
                        .where(
                            AgentRun.task_id == task_id,
                            AgentRun.agent_type == AgentType.CODER,
                        )
                        .order_by(AgentRun.started_at.desc())
                        .limit(1)
                    )
                    last_run = run_q.scalar_one_or_none()
                    rid = last_run.id if last_run else None
                    # Finalize the open run as FAILURE so the UI stops polling and
                    # the run isn't left stuck in RUNNING forever.
                    if last_run is not None and last_run.status == AgentRunStatus.RUNNING:
                        last_run.status = AgentRunStatus.FAILURE
                        last_run.completed_at = datetime.now(timezone.utc)
                        last_run.result = {"error": str(exc), "error_type": type(exc).__name__}
                    await EventPublisher.publish(
                        task_id,
                        StreamEventType.ERROR,
                        json.dumps(_error_body(exc), separators=(",", ":")),
                        session,
                        rid,
                    )
                    await write_audit(
                        session,
                        project_id=project_id,
                        task_id=task_id,
                        action_type="coder_node",
                        action_description=str(exc),
                        result=AuditLogResult.FAILURE,
                        agent_id=CODER_AGENT_ID,
                    )
                    task = await session.get(Task, task_id)
                    if task is not None:
                        from app.services.kanban_service import KanbanService

                        # Return the task to To do so it stays visible and retryable
                        # (board has no rejected/failed column — failures go to TODO).
                        if task.status == TaskStatus.IN_PROGRESS:
                            task.status = TaskStatus.TODO
                            task.updated_at = datetime.now(timezone.utc)
                            await EventPublisher.publish(
                                task_id,
                                StreamEventType.STATUS_CHANGE,
                                json.dumps(
                                    {"from": "CODING", "to": "TODO", "reason": str(exc)[:500]},
                                    separators=(",", ":"),
                                ),
                                session,
                                rid,
                            )
                        await KanbanService.on_agent_error(session, task)
                    await session.commit()
        except Exception:
            logger.exception("coder_node failure audit failed")
        return {**state, "error": str(exc)}
