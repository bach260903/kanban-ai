from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import User
from app.services.ws_manager import manager

router = APIRouter(tags=["ws"])

log = logging.getLogger(__name__)


async def _authenticate(token: str) -> User | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if not sub:
            return None
        uid = uuid.UUID(sub)
    except (JWTError, ValueError):
        return None
    async with AsyncSessionLocal() as db:
        return await db.get(User, uid)


@router.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket, token: str = Query("")) -> None:
    user = await _authenticate(token) if token else None
    if user is None:
        await websocket.close(code=4401)
        return

    conn = await manager.connect(websocket, str(user.id))

    async def _writer() -> None:
        try:
            while True:
                msg = await conn.queue.get()
                await websocket.send_text(json.dumps(msg, default=str))
        except Exception:
            pass

    writer_task = asyncio.create_task(_writer())
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
            except json.JSONDecodeError:
                continue
            t = msg.get("type")
            data = msg.get("data") or {}
            if t == "subscribe":
                topics = [str(x) for x in data.get("topics", []) if isinstance(x, str)]
                manager.subscribe(conn, topics)
                await websocket.send_text(json.dumps({"type": "subscribed", "topics": topics}))
            elif t == "unsubscribe":
                topics = [str(x) for x in data.get("topics", []) if isinstance(x, str)]
                manager.unsubscribe(conn, topics)
                await websocket.send_text(json.dumps({"type": "unsubscribed", "topics": topics}))
            elif t == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            else:
                await websocket.send_text(json.dumps({"type": "error", "error": f"unknown type {t}"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:  # pragma: no cover
        log.warning("WS error: %s", e)
    finally:
        writer_task.cancel()
        manager.disconnect(conn)
