"""End-to-end smoke test for spec 003 / T120 — auth, members, kanban, notifications, analytics."""

from __future__ import annotations

import re
import uuid
from unittest.mock import patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.database import engine

_PASSWORD = "SmokePass123!"


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@smoke.example.com"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register(
    client: AsyncClient,
    *,
    email: str,
    display_name: str,
) -> tuple[str, dict]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": _PASSWORD, "display_name": display_name},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body.get("access_token")
    assert body.get("user", {}).get("email") == email
    return body["access_token"], body["user"]


async def _insert_pending_diff(task_id: UUID) -> UUID:
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO diffs (
                    task_id, content, original_content, modified_content,
                    files_affected, review_status
                )
                VALUES (
                    :tid, '--- a/file.py\n+++ b/file.py\n', 'old', 'new',
                    ARRAY['file.py']::text[], 'pending'
                )
                RETURNING id
                """
            ),
            {"tid": task_id},
        )
        return res.scalar_one()


async def _insert_review_report(task_id: UUID) -> UUID:
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                """
                INSERT INTO review_reports (task_id, score, suggestion, status)
                VALUES (:tid, 85, 'approve', 'complete')
                RETURNING id
                """
            ),
            {"tid": task_id},
        )
        return res.scalar_one()


def _invite_token(invite_url: str) -> str:
    match = re.search(r"/invitations/([a-f0-9]+)$", invite_url)
    assert match is not None, invite_url
    return match.group(1)


@pytest.mark.asyncio
async def test_smoke_platform_flow(test_client: AsyncClient) -> None:
    """Single sequential smoke covering auth → members → kanban → notifications → analytics."""

    # --- Auth ---
    owner_email = _unique_email("owner")
    owner_token, owner_user = await _register(
        test_client,
        email=owner_email,
        display_name="Smoke Owner",
    )
    owner_headers = _bearer(owner_token)

    r = await test_client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": _PASSWORD},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("access_token")

    r = await test_client.get("/api/v1/auth/me", headers=owner_headers)
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["id"] == owner_user["id"]
    assert me["email"] == owner_email

    # --- Projects (owner auto-added as member) ---
    project_name = f"smoke_{uuid.uuid4().hex[:10]}"
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": project_name, "description": "T120 smoke", "primary_language": "python"},
        headers=owner_headers,
    )
    assert r.status_code == 201, r.text
    project_id = r.json()["id"]

    r = await test_client.get("/api/v1/projects", headers=owner_headers)
    assert r.status_code == 200, r.text
    owner_project_ids = {p["id"] for p in r.json()}
    assert project_id in owner_project_ids

    # Other user's project must not appear in owner's list
    other_email = _unique_email("other")
    other_token, _ = await _register(
        test_client,
        email=other_email,
        display_name="Smoke Other",
    )
    other_headers = _bearer(other_token)
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": f"other_{uuid.uuid4().hex[:8]}", "description": "d", "primary_language": "python"},
        headers=other_headers,
    )
    assert r.status_code == 201, r.text
    other_project_id = r.json()["id"]

    r = await test_client.get("/api/v1/projects", headers=owner_headers)
    assert other_project_id not in {p["id"] for p in r.json()}

    # --- Members / invitations ---
    r = await test_client.post(
        f"/api/v1/projects/{project_id}/members/invite",
        headers=owner_headers,
        json={"role": "developer", "invitee_email": None},
    )
    assert r.status_code == 201, r.text
    invite_body = r.json()
    assert "invite_url" in invite_body
    assert "invitation_id" in invite_body
    invite_token = _invite_token(invite_body["invite_url"])

    invitee_email = _unique_email("invitee")
    invitee_token, invitee_user = await _register(
        test_client,
        email=invitee_email,
        display_name="Smoke Invitee",
    )
    invitee_headers = _bearer(invitee_token)

    r = await test_client.post(
        f"/api/v1/invitations/{invite_token}/accept",
        headers=invitee_headers,
    )
    assert r.status_code == 200, r.text
    accept_body = r.json()
    assert accept_body["project_id"] == project_id
    assert accept_body["role"] == "developer"

    r = await test_client.get(f"/api/v1/projects/{project_id}/members", headers=owner_headers)
    assert r.status_code == 200, r.text
    member_ids = {m["user_id"] for m in r.json()}
    assert owner_user["id"] in member_ids
    assert invitee_user["id"] in member_ids
    assert len(member_ids) >= 2

    # --- Kanban flow ---
    r = await test_client.post(
        f"/api/v1/projects/{project_id}/tasks",
        headers=owner_headers,
        json={"title": "Smoke task", "description": "T120", "priority": 0},
    )
    assert r.status_code == 201, r.text
    task_id = r.json()["id"]

    r = await test_client.get(f"/api/v1/projects/{project_id}/tasks", headers=owner_headers)
    assert r.status_code == 200, r.text
    grouped = r.json()
    assert "todo" in grouped and "in_progress" in grouped and "review" in grouped and "done" in grouped
    assert any(t["id"] == task_id for t in grouped["todo"])

    with patch("app.services.kanban_service._schedule_coder_agent"), patch(
        "app.api.v1.tasks.KanbanService.start_coder_agent",
    ):
        r = await test_client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/move",
            headers=owner_headers,
            json={"to": "in_progress"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["to_status"] == "in_progress"

        r = await test_client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/move",
            headers=owner_headers,
            json={"to": "review"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["to_status"] == "review"

    await _insert_review_report(UUID(task_id))
    await _insert_pending_diff(UUID(task_id))

    r = await test_client.get(f"/api/v1/tasks/{task_id}/review", headers=owner_headers)
    assert r.status_code == 200, r.text
    review = r.json()
    assert review["task_id"] == task_id
    assert review["status"] == "complete"

    r = await test_client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/approve",
        headers=owner_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done"

    # --- Notifications ---
    r = await test_client.get("/api/v1/notifications", headers=owner_headers)
    assert r.status_code == 200, r.text
    notif_body = r.json()
    assert "items" in notif_body
    assert "total_unread" in notif_body
    assert isinstance(notif_body["items"], list)

    # --- Dashboard & analytics ---
    r = await test_client.get("/api/v1/dashboard", headers=owner_headers)
    assert r.status_code == 200, r.text
    dashboard = r.json()
    assert "projects" in dashboard
    match = next((p for p in dashboard["projects"] if p["id"] == project_id), None)
    assert match is not None
    assert "task_counts" in match
    assert match["member_count"] >= 2

    r = await test_client.get(
        f"/api/v1/projects/{project_id}/analytics",
        headers=owner_headers,
        params={"range": "7d"},
    )
    assert r.status_code == 200, r.text
    analytics = r.json()
    assert "period" in analytics
    assert "by_backend" in analytics
    assert "by_member" in analytics
