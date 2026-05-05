"""Lightweight in-process pub/sub for WebSocket fan-out.

Frontend subscribes to topics like ``agent.run.<run_id>`` or ``board.<board_id>``;
the agent runner publishes events to these topics. A bounded queue per
connection prevents a slow client from blocking the runner.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Optional

from fastapi import WebSocket

log = logging.getLogger(__name__)


class WSConnection:
    def __init__(self, ws: WebSocket, user_id: str):
        self.ws = ws
        self.user_id = user_id
        self.topics: set[str] = set()
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1024)


class WSManager:
    def __init__(self) -> None:
        self._connections: set[WSConnection] = set()
        self._by_topic: dict[str, set[WSConnection]] = defaultdict(set)

    async def connect(self, ws: WebSocket, user_id: str) -> WSConnection:
        await ws.accept()
        conn = WSConnection(ws, user_id)
        self._connections.add(conn)
        return conn

    def disconnect(self, conn: WSConnection) -> None:
        self._connections.discard(conn)
        for topic in list(conn.topics):
            self._by_topic.get(topic, set()).discard(conn)
        conn.topics.clear()

    def subscribe(self, conn: WSConnection, topics: list[str]) -> None:
        for topic in topics:
            self._by_topic[topic].add(conn)
            conn.topics.add(topic)

    def unsubscribe(self, conn: WSConnection, topics: list[str]) -> None:
        for topic in topics:
            self._by_topic.get(topic, set()).discard(conn)
            conn.topics.discard(topic)

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        message = {"topic": topic, **event}
        recipients = list(self._by_topic.get(topic, set()))
        for conn in recipients:
            try:
                conn.queue.put_nowait(message)
            except asyncio.QueueFull:
                log.debug("WS queue full for user %s; dropping event", conn.user_id)

    async def broadcast(self, topic: str, event: dict[str, Any]) -> None:
        await self.publish(topic, event)


manager = WSManager()


async def push_event(topic: str, event: dict[str, Any]) -> None:
    await manager.publish(topic, event)


def topic_run(run_id: str) -> str:
    return f"agent.run.{run_id}"


def topic_board(board_id: str) -> str:
    return f"board.{board_id}"
