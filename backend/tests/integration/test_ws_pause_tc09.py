"""TC-09 (T113): WebSocket PAUSE → at most one server-originated frame before the handler waits again.

The stream loop blocks on the next server ``receive_text`` after handling PAUSE, so the client must
not expect another server frame without sending traffic. Here ``_pump_redis`` is replaced with a
no-op so relayed stream events do not interleave; ``PauseService.pause`` is mocked to avoid a live
Redis dependency while still exercising the WS PAUSE branch. Exactly one ``STATUS_CHANGE``
(CODING → PAUSED) is asserted after ``PAUSE``. Requires PostgreSQL; skips if the DB is down.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from jose import jwt
from sqlalchemy import text
from starlette.testclient import TestClient

from app.config import settings
from app.database import engine
from app.main import app
from app.services.pause_service import PauseService


def _ws_token() -> str:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "test-user", "exp": now + timedelta(hours=24)},
        settings.jwt_secret,
        algorithm="HS256",
    )


async def _seed_in_progress_task() -> tuple[UUID, UUID]:
    name = f"ws_tc09_{uuid.uuid4().hex[:12]}"
    async with engine.begin() as conn:
        pid = (
            await conn.execute(
                text(
                    """
                    INSERT INTO projects (name, description, primary_language, constitution, status)
                    VALUES (:name, 't113', 'python', '', 'active')
                    RETURNING id
                    """
                ),
                {"name": name},
            )
        ).scalar_one()
        tid = (
            await conn.execute(
                text(
                    """
                    INSERT INTO tasks (project_id, title, description, status, priority)
                    VALUES (:pid, 'TC-09 pause', NULL, 'in_progress', 0)
                    RETURNING id
                    """
                ),
                {"pid": pid},
            )
        ).scalar_one()
    return pid, tid


async def _delete_project(pid: UUID) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tasks WHERE project_id = :pid"), {"pid": pid})
        await conn.execute(text("DELETE FROM projects WHERE id = :pid"), {"pid": pid})


async def _noop_pump_redis(_task_id: UUID, _send: object, _stop: asyncio.Event) -> None:
    """Skip Redis relay so only explicit ``send_text`` from the PAUSE branch is observed (T113)."""
    return


def test_tc09_pause_at_most_one_server_event_after_pause() -> None:
    pid: UUID | None = None
    try:
        try:
            pid, tid = asyncio.run(_seed_in_progress_task())
        except ConnectionRefusedError as e:
            pytest.skip(f"PostgreSQL not reachable (integration TC-09): {e}")
        token = _ws_token()
        with (
            patch.object(PauseService, "pause", new=AsyncMock()),
            patch("app.websocket.ws_handler._pump_redis", _noop_pump_redis),
        ):
            client = TestClient(app)
            path = f"/ws/tasks/{tid}/stream?token={token}"
            with client.websocket_connect(path) as ws:
                raw_connected = ws.receive_text()
                connected = json.loads(raw_connected)
                assert connected.get("type") == "CONNECTED"

                ws.send_text(json.dumps({"type": "PAUSE"}))
                raw_after = ws.receive_text()
                after = json.loads(raw_after)

                assert after.get("event_type") == "STATUS_CHANGE"
                assert after.get("content", {}).get("to") == "PAUSED"
                assert after.get("content", {}).get("from") == "CODING"
    finally:
        if pid is not None:
            asyncio.run(_delete_project(pid))
