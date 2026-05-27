"""Integration tests: notifications API (US7 / T093)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import text

from app.config import settings
from app.database import engine


async def _other_user_headers() -> dict[str, str]:
    other_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, display_name)
                VALUES (:id, :email, :hashed_password, :display_name)
                """
            ),
            {
                "id": other_id,
                "email": f"other-{other_id.hex[:8]}@example.com",
                "hashed_password": "pytest-hash",
                "display_name": "Other User",
            },
        )
    token = jwt.encode(
        {
            "sub": str(other_id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def _insert_notification(user_id: UUID, content: str, *, is_read: bool = False) -> UUID:
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO notifications (user_id, type, content, is_read)
                VALUES (:uid, 'task_assigned', :content, :is_read)
                RETURNING id
                """
            ),
            {"uid": user_id, "content": content, "is_read": is_read},
        )
        return res.scalar_one()


@pytest.mark.asyncio
async def test_list_notifications_requires_auth(test_client: AsyncClient) -> None:
    r = await test_client.get("/api/v1/notifications")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_mark_and_read_all_notifications(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    token = auth_headers["Authorization"].split(" ", 1)[1]
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    user_id = UUID(payload["sub"])

    r = await test_client.get("/api/v1/notifications", headers=auth_headers)
    assert r.status_code == 200, r.text
    baseline_unread = r.json()["total_unread"]

    unread_content = f"Unread-{uuid.uuid4().hex[:8]}"
    read_content = f"Already read-{uuid.uuid4().hex[:8]}"
    nid_unread = await _insert_notification(user_id, unread_content)
    await _insert_notification(user_id, read_content, is_read=True)

    r = await test_client.get("/api/v1/notifications", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_unread"] == baseline_unread + 1
    assert any(item["content"] == unread_content for item in body["items"])

    r = await test_client.get(
        "/api/v1/notifications",
        headers=auth_headers,
        params={"unread_only": "true"},
    )
    assert r.status_code == 200
    assert all(not item["is_read"] for item in r.json()["items"])

    r = await test_client.patch(
        f"/api/v1/notifications/{nid_unread}/read",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    other_headers = await _other_user_headers()
    r = await test_client.patch(
        f"/api/v1/notifications/{nid_unread}/read",
        headers=other_headers,
    )
    assert r.status_code == 404

    another_content = f"Another unread-{uuid.uuid4().hex[:8]}"
    await _insert_notification(user_id, another_content)
    r = await test_client.get(
        "/api/v1/notifications",
        headers=auth_headers,
        params={"unread_only": "true"},
    )
    assert r.status_code == 200
    expected_marked = r.json()["total_unread"]
    assert expected_marked == baseline_unread + 1

    r = await test_client.post("/api/v1/notifications/read-all", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["marked"] == expected_marked

    r = await test_client.get(
        "/api/v1/notifications",
        headers=auth_headers,
        params={"unread_only": "true"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_notifications_includes_project_id_for_task_refs(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    token = auth_headers["Authorization"].split(" ", 1)[1]
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    user_id = UUID(payload["sub"])

    async with engine.begin() as conn:
        project_res = await conn.execute(
            text(
                """
                INSERT INTO projects (name, description, primary_language, constitution, status)
                VALUES ('Notif project', 'test', 'python', '', 'active')
                RETURNING id
                """
            )
        )
        project_id = project_res.scalar_one()
        task_res = await conn.execute(
            text(
                """
                INSERT INTO tasks (project_id, title, description, status, priority)
                VALUES (:pid, 'Task ref', NULL, 'todo', 0)
                RETURNING id
                """
            ),
            {"pid": project_id},
        )
        task_id = task_res.scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO notifications (user_id, type, content, reference_type, reference_id, is_read)
                VALUES (:uid, 'task_assigned', 'Assigned', 'task', :tid, false)
                """
            ),
            {"uid": user_id, "tid": task_id},
        )

    r = await test_client.get("/api/v1/notifications", headers=auth_headers)
    assert r.status_code == 200, r.text
    matched = next(
        (item for item in r.json()["items"] if item.get("reference_id") == str(task_id)),
        None,
    )
    assert matched is not None
    assert matched["project_id"] == str(project_id)
