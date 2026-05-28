"""In-process SSE event bus for live pipeline execution updates.

Design: a simple dict of run_id → list of queues.
Any number of SSE consumers can subscribe to a run.
The executor emits events; each queue receives a copy.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# run_id (str) → list of asyncio.Queue
_subscribers: dict[str, list[asyncio.Queue[str | None]]] = defaultdict(list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def emit(run_id: str, event_type: str, data: dict) -> None:
    """Broadcast a pipeline event to all SSE subscribers of *run_id*."""
    payload = json.dumps({"type": event_type, "ts": _now_iso(), **data})
    for q in list(_subscribers.get(run_id, [])):
        try:
            await q.put(payload)
        except Exception:
            logger.debug("Failed to put event into subscriber queue", exc_info=True)


async def emit_sync(run_id: str, event_type: str, data: dict) -> None:
    """Thread-safe variant that can be called from asyncio tasks."""
    await emit(run_id, event_type, data)


async def subscribe(run_id: str) -> AsyncGenerator[str, None]:
    """Yield SSE data lines for all events on *run_id*.

    Yields ``"data: <json>\\n\\n"`` strings (standard SSE format).
    Terminates when the sentinel ``None`` is received (run finished).
    """
    q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=256)
    _subscribers[run_id].append(q)
    logger.debug("SSE subscriber added for run_id=%s total=%d", run_id, len(_subscribers[run_id]))
    try:
        while True:
            message = await asyncio.wait_for(q.get(), timeout=30.0)
            if message is None:
                # Sentinel: run is done
                break
            yield f"data: {message}\n\n"
    except asyncio.TimeoutError:
        # Keep-alive ping so the connection doesn't drop
        yield "data: {\"type\":\"ping\"}\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        try:
            _subscribers[run_id].remove(q)
        except ValueError:
            pass
        if not _subscribers[run_id]:
            _subscribers.pop(run_id, None)
        logger.debug("SSE subscriber removed for run_id=%s", run_id)


async def close_run(run_id: str) -> None:
    """Send sentinel to all subscribers so they cleanly disconnect."""
    for q in list(_subscribers.get(run_id, [])):
        try:
            await q.put(None)
        except Exception:
            pass
