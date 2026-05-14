"""Persist stream events and fan-out to Redis (US10 / T074)."""

from __future__ import annotations

import json
import logging
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import NotFoundError
from app.models.stream_event import StreamEvent, StreamEventType
from app.models.task import Task

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _redis_channel(task_id: UUID) -> str:
    return f"task:{task_id}:events"


def _coerce_event_type(event_type: StreamEventType | str) -> StreamEventType:
    if isinstance(event_type, StreamEventType):
        return event_type
    s = str(event_type).strip()
    try:
        return StreamEventType(s)
    except ValueError:
        u = s.upper()
        return StreamEventType(u)


class EventPublisher:
    """Assign monotonic ``sequence_number`` per task, persist, publish to Redis."""

    @staticmethod
    async def publish(
        task_id: UUID,
        event_type: StreamEventType | str,
        content: str,
        session: AsyncSession,
    ) -> StreamEvent:
        """Lock task row, allocate next sequence, insert ``stream_events``, ``PUBLISH`` JSON."""
        locked = await session.execute(select(Task.id).where(Task.id == task_id).with_for_update())
        if locked.scalar_one_or_none() is None:
            raise NotFoundError("Task not found.")

        max_seq = await session.scalar(
            select(func.coalesce(func.max(StreamEvent.sequence_number), 0)).where(StreamEvent.task_id == task_id)
        )
        next_seq = int(max_seq or 0) + 1
        et = _coerce_event_type(event_type)

        row = StreamEvent(
            task_id=task_id,
            agent_run_id=None,
            event_type=et,
            content=content,
            sequence_number=next_seq,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)

        payload = {
            "id": str(row.id),
            "task_id": str(task_id),
            "agent_run_id": str(row.agent_run_id) if row.agent_run_id else None,
            "event_type": et.value,
            "content": content,
            "sequence_number": next_seq,
            "timestamp": row.timestamp.isoformat() if row.timestamp else None,
        }
        message = json.dumps(payload, separators=(",", ":"))
        try:
            r = await _get_redis()
            await r.publish(_redis_channel(task_id), message)
        except Exception:
            logger.exception("Redis publish failed for task_id=%s seq=%s", task_id, next_seq)
            raise
        return row
