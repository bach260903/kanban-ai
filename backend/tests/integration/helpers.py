"""Shared helpers for HTTP + DB integration tests (real PostgreSQL)."""

from __future__ import annotations

import uuid
from typing import Literal
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import text

from app.database import engine


async def create_project(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str | None = None,
) -> UUID:
    if name is None:
        name = f"itest_{uuid.uuid4().hex[:12]}"
    r = await client.post(
        "/api/v1/projects",
        json={"name": name, "description": "integration", "primary_language": "python"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["id"])


async def insert_spec_document(
    project_id: UUID,
    *,
    status: Literal["draft", "approved"] = "draft",
) -> UUID:
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO documents (project_id, "type", content, status, version)
                VALUES (:pid, 'SPEC', 'integration seed', :st, 1)
                RETURNING id
                """
            ),
            {"pid": project_id, "st": status},
        )
        return res.scalar_one()


async def insert_tasks(
    project_id: UUID,
    rows: list[tuple[str, str]],
) -> list[UUID]:
    """Insert tasks as ``(title, status)`` where ``status`` is DB enum string (e.g. ``todo``)."""
    ids: list[UUID] = []
    async with engine.begin() as conn:
        for title, status in rows:
            res = await conn.execute(
                text(
                    """
                    INSERT INTO tasks (project_id, title, description, status, priority)
                    VALUES (:pid, :title, NULL, :status, 0)
                    RETURNING id
                    """
                ),
                {"pid": project_id, "title": title, "status": status},
            )
            ids.append(res.scalar_one())
    return ids
