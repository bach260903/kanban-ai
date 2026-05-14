"""Async Redis subscriber for per-task event streams (US10 / T075)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from app.websocket.event_publisher import _get_redis, _redis_channel

logger = logging.getLogger(__name__)


class EventConsumer:
    """Subscribe to ``task:{task_id}:events`` and yield JSON payloads as dicts."""

    @staticmethod
    async def consume(task_id: UUID) -> AsyncIterator[dict[str, Any]]:
        channel = _redis_channel(task_id)
        client = await _get_redis()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for raw in pubsub.listen():
                if raw.get("type") != "message":
                    continue
                data = raw.get("data")
                if data is None:
                    continue
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8")
                try:
                    parsed: dict[str, Any] = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Skipping non-JSON message on %s", channel)
                    continue
                yield parsed
        finally:
            try:
                await pubsub.unsubscribe(channel)
            except Exception:
                logger.exception("pubsub unsubscribe failed channel=%s", channel)
            try:
                await pubsub.close()
            except Exception:
                logger.exception("pubsub close failed channel=%s", channel)
