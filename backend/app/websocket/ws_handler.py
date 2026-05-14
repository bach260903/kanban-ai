"""Task thought-stream WebSocket (US10 / T076). See ``contracts/websocket-protocol.md``."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from app.config import settings
from app.database import async_session_maker
from app.models.agent_run import AgentRun, AgentRunStatus, AgentType
from app.models.stream_event import StreamEvent, StreamEventType
from app.models.task import Task, TaskStatus
from app.services.pause_service import PauseService
from app.websocket.event_consumer import EventConsumer

pause_service = PauseService

logger = logging.getLogger(__name__)

_WS_ERROR = "ERROR"
_WS_CONNECTED = "CONNECTED"
_WS_STREAM_END = "STREAM_END"


def _decode_jwt_sub(token: str | None) -> str:
    if not token or not str(token).strip():
        raise ValueError("missing_token")
    try:
        payload = jwt.decode(token.strip(), settings.jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise ValueError("invalid_token") from e
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise ValueError("missing_sub")
    return sub


def _ws_error(code: str, message: str) -> str:
    return json.dumps({"type": _WS_ERROR, "code": code, "message": message}, separators=(",", ":"))


def _event_row_to_wire(row: StreamEvent) -> dict[str, Any]:
    et = row.event_type.value if isinstance(row.event_type, StreamEventType) else str(row.event_type)
    return {
        "id": str(row.id),
        "task_id": str(row.task_id),
        "agent_run_id": str(row.agent_run_id) if row.agent_run_id else None,
        "event_type": et,
        "content": row.content,
        "sequence_number": row.sequence_number,
        "timestamp": row.timestamp.isoformat() if row.timestamp else None,
    }


async def _latest_sequence(session: AsyncSession, task_id: UUID) -> int:
    n = await session.scalar(
        select(func.coalesce(func.max(StreamEvent.sequence_number), 0)).where(StreamEvent.task_id == task_id)
    )
    return int(n or 0)


async def _latest_coder_run(session: AsyncSession, task_id: UUID) -> AgentRun | None:
    result = await session.execute(
        select(AgentRun)
        .where(AgentRun.task_id == task_id, AgentRun.agent_type == AgentType.CODER)
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_coder_run_id(session: AsyncSession, task_id: UUID) -> UUID | None:
    r = await _latest_coder_run(session, task_id)
    return r.id if r else None


async def _replay_catch_up(
    session: AsyncSession,
    send: Any,
    task_id: UUID,
    last_sequence: int,
) -> None:
    last = int(last_sequence)
    result = await session.execute(
        select(StreamEvent)
        .where(StreamEvent.task_id == task_id, StreamEvent.sequence_number > last)
        .order_by(StreamEvent.sequence_number.asc())
    )
    for row in result.scalars().all():
        await send(json.dumps(_event_row_to_wire(row), separators=(",", ":")))


async def _event_counts(session: AsyncSession, task_id: UUID) -> dict[str, int]:
    base = {t.value: 0 for t in StreamEventType}
    rows = await session.execute(
        select(StreamEvent.event_type, func.count(StreamEvent.id)).where(StreamEvent.task_id == task_id).group_by(StreamEvent.event_type)
    )
    for et, cnt in rows.all():
        key = et.value if isinstance(et, StreamEventType) else str(et)
        if key in base:
            base[key] = int(cnt)
    return base


def _final_status(task: Task, run: AgentRun | None) -> str:
    if run is not None and run.status == AgentRunStatus.FAILURE:
        return "failure"
    if task.status == TaskStatus.REVIEW:
        return "awaiting_hil"
    return "success"


def _should_end_stream(task: Task, run: AgentRun | None) -> bool:
    if run is not None and run.status == AgentRunStatus.FAILURE:
        return True
    return task.status != TaskStatus.IN_PROGRESS


async def _pump_redis(task_id: UUID, send: Any, stop: asyncio.Event) -> None:
    try:
        async for evt in EventConsumer.consume(task_id):
            if stop.is_set():
                break
            await send(json.dumps(evt, separators=(",", ":")))
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Redis relay failed task_id=%s", task_id)
        raise


async def handle(websocket: WebSocket, task_id: UUID) -> None:
    """WebSocket entry for ``/ws/tasks/{task_id}/stream`` (registered in T077)."""
    token = websocket.query_params.get("token")
    try:
        _decode_jwt_sub(token)
    except ValueError:
        if websocket.client_state == WebSocketState.CONNECTING:
            await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()

    send_lock = asyncio.Lock()

    async def send_text(msg: str) -> None:
        async with send_lock:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(msg)

    async with async_session_maker() as session:
        task = await session.get(Task, task_id)
        if task is None:
            await send_text(_ws_error("TASK_NOT_FOUND", "Task not found."))
            await websocket.close()
            return
        if task.status != TaskStatus.IN_PROGRESS:
            await send_text(_ws_error("TASK_NOT_ACTIVE", "Task must be in progress to open the stream."))
            await websocket.close()
            return

        latest = await _latest_sequence(session, task_id)
        run = await _latest_coder_run(session, task_id)
        agent_run_id = str(run.id) if run else None

        await send_text(
            json.dumps(
                {
                    "type": _WS_CONNECTED,
                    "task_id": str(task_id),
                    "agent_run_id": agent_run_id,
                    "latest_sequence": latest,
                },
                separators=(",", ":"),
            )
        )

    stop = asyncio.Event()
    stream_ended = asyncio.Lock()
    ended = False

    async def try_claim_stream_end() -> bool:
        nonlocal ended
        async with stream_ended:
            if ended:
                return False
            ended = True
            return True

    async def send_stream_end() -> None:
        if not await try_claim_stream_end():
            return
        async with async_session_maker() as s2:
            t2 = await s2.get(Task, task_id)
            r2 = await _latest_coder_run(s2, task_id)
            if t2 is None:
                return
            counts = await _event_counts(s2, task_id)
            fs = _final_status(t2, r2)
            await send_text(
                json.dumps(
                    {
                        "type": _WS_STREAM_END,
                        "task_id": str(task_id),
                        "final_status": fs,
                        "event_count": counts,
                    },
                    separators=(",", ":"),
                )
            )
        stop.set()

    async def poll_stream_end() -> None:
        try:
            while not stop.is_set():
                await asyncio.sleep(1.5)
                async with async_session_maker() as s3:
                    t3 = await s3.get(Task, task_id)
                    if t3 is None:
                        await send_stream_end()
                        return
                    r3 = await _latest_coder_run(s3, task_id)
                    if _should_end_stream(t3, r3):
                        await send_stream_end()
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("poll_stream_end failed task_id=%s", task_id)

    relay_task = asyncio.create_task(_pump_redis(task_id, send_text, stop))
    poll_task = asyncio.create_task(poll_stream_end())

    try:
        while not stop.is_set():
            recv_task = asyncio.create_task(websocket.receive_text())
            stop_task = asyncio.create_task(stop.wait())
            done, pending = await asyncio.wait(
                {recv_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for p in pending:
                p.cancel()
                try:
                    await p
                except asyncio.CancelledError:
                    pass
            if stop_task in done:
                break
            try:
                raw = recv_task.result()
            except WebSocketDisconnect:
                break

            try:
                msg: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                continue

            mtype = msg.get("type")
            if mtype == "CATCH_UP":
                last_seq = int(msg.get("last_sequence", 0))
                async with async_session_maker() as sc:
                    await _replay_catch_up(sc, send_text, task_id, last_seq)
            elif mtype == "PAUSE":
                try:
                    async with async_session_maker() as sp:
                        await pause_service.pause(sp, task_id)
                        await sp.commit()
                except Exception:
                    logger.exception("WS PAUSE failed task_id=%s", task_id)
                    await send_text(_ws_error("PAUSE_FAILED", "Could not pause task."))
                    continue
                await send_text(
                    json.dumps(
                        {
                            "event_type": "STATUS_CHANGE",
                            "content": {"from": "CODING", "to": "PAUSED", "reason": "pause_requested"},
                            "sequence_number": None,
                        },
                        separators=(",", ":"),
                    )
                )
            elif mtype == "RESUME":
                steer = msg.get("steering_instructions")
                steer_s = str(steer).strip() if steer is not None else None
                if steer_s == "":
                    steer_s = None
                try:
                    async with async_session_maker() as sr:
                        await pause_service.resume(sr, task_id, steer_s)
                        await sr.commit()
                except Exception:
                    logger.exception("WS RESUME failed task_id=%s", task_id)
                    await send_text(_ws_error("RESUME_FAILED", "Could not resume task."))
                    continue
                await send_text(
                    json.dumps(
                        {
                            "event_type": "STATUS_CHANGE",
                            "content": {"from": "PAUSED", "to": "CODING", "reason": "resume_requested"},
                            "sequence_number": None,
                        },
                        separators=(",", ":"),
                    )
                )
    finally:
        stop.set()
        poll_task.cancel()
        relay_task.cancel()
        for t in (poll_task, relay_task):
            try:
                await t
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("background task join failed")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
