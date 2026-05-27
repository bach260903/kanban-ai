"""Integration tests: manual task create API (Phase 7 / T080)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import text

from app.config import settings
from app.database import engine
from tests.integration.helpers import create_project


async def _viewer_headers_for_project(project_id) -> dict[str, str]:
    viewer_id = uuid.uuid4()
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, display_name)
                VALUES (:id, :email, :hashed_password, :display_name)
                RETURNING id
                """
            ),
            {
                "id": viewer_id,
                "email": f"viewer-{viewer_id.hex[:8]}@example.com",
                "hashed_password": "pytest-hash",
                "display_name": "Viewer User",
            },
        )
        viewer_id = res.scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO project_members (project_id, user_id, role)
                VALUES (:pid, :uid, 'viewer')
                """
            ),
            {"pid": project_id, "uid": viewer_id},
        )
    token = jwt.encode(
        {"sub": str(viewer_id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_task_in_todo_column(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.post(
        f"/api/v1/projects/{pid}/tasks",
        headers=auth_headers,
        json={"title": "Manual task", "description": "From template flow", "priority": 0},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["title"] == "Manual task"
    assert body["status"] == "todo"

    r_list = await test_client.get(f"/api/v1/projects/{pid}/tasks", headers=auth_headers)
    assert r_list.status_code == 200
    titles = [t["title"] for t in r_list.json()["todo"]]
    assert "Manual task" in titles


@pytest.mark.asyncio
async def test_viewer_cannot_create_task(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    viewer_headers = await _viewer_headers_for_project(pid)
    r = await test_client.post(
        f"/api/v1/projects/{pid}/tasks",
        headers=viewer_headers,
        json={"title": "Blocked", "description": ""},
    )
    assert r.status_code == 403
