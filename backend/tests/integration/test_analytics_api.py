"""Integration tests: analytics API (US6 / T085)."""

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
from tests.integration.helpers import create_project, insert_tasks


async def _viewer_headers_for_project(project_id: UUID) -> dict[str, str]:
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
        {
            "sub": str(viewer_id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


async def _developer_headers_for_project(project_id: UUID) -> dict[str, str]:
    developer_id = uuid.uuid4()
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
                "id": developer_id,
                "email": f"developer-{developer_id.hex[:8]}@example.com",
                "hashed_password": "pytest-hash",
                "display_name": "Developer User",
            },
        )
        developer_id = res.scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO project_members (project_id, user_id, role)
                VALUES (:pid, :uid, 'developer')
                """
            ),
            {"pid": project_id, "uid": developer_id},
        )
    token = jwt.encode(
        {
            "sub": str(developer_id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_dashboard_requires_auth(test_client: AsyncClient) -> None:
    r = await test_client.get("/api/v1/dashboard")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_dashboard_excludes_archived_projects(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(
        test_client,
        auth_headers,
        name=f"Archive Me Dashboard {uuid.uuid4().hex[:8]}",
    )
    r = await test_client.get("/api/v1/dashboard", headers=auth_headers)
    assert r.status_code == 200
    assert any(p["id"] == str(pid) for p in r.json()["projects"])

    r = await test_client.delete(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert r.status_code == 204

    r = await test_client.get("/api/v1/dashboard", headers=auth_headers)
    assert r.status_code == 200
    assert not any(p["id"] == str(pid) for p in r.json()["projects"])


@pytest.mark.asyncio
async def test_get_project_analytics_custom_range_inverted(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    from_dt = datetime.now(timezone.utc).isoformat()
    to_dt = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=auth_headers,
        params={"range": "custom", "from_date": from_dt, "to_date": to_dt},
    )
    assert r.status_code == 400
    assert "from_date" in r.json()["detail"]


@pytest.mark.asyncio
async def test_developer_cannot_access_project_analytics(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    developer_headers = await _developer_headers_for_project(pid)
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=developer_headers,
        params={"range": "7d"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_dashboard_returns_member_projects(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(
        test_client,
        auth_headers,
        name=f"Dashboard Project {uuid.uuid4().hex[:8]}",
    )
    await insert_tasks(pid, [("Todo one", "todo"), ("Done one", "done")])

    r = await test_client.get("/api/v1/dashboard", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "projects" in body
    match = next((p for p in body["projects"] if p["id"] == str(pid)), None)
    assert match is not None
    assert match["name"].startswith("Dashboard Project")
    assert match.get("primary_language") == "python"
    assert match["task_counts"]["todo"] == 1
    assert match["task_counts"]["done"] == 1
    assert match["member_count"] >= 1


@pytest.mark.asyncio
async def test_get_project_analytics_range_7d(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=auth_headers,
        params={"range": "7d"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "period" in body
    assert "by_backend" in body
    assert "by_member" in body
    assert "error_breakdown" in body


@pytest.mark.asyncio
async def test_get_project_analytics_custom_range(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    from_dt = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    to_dt = datetime.now(timezone.utc).isoformat()
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=auth_headers,
        params={"range": "custom", "from_date": from_dt, "to_date": to_dt},
    )
    assert r.status_code == 200, r.text
    assert ".." in r.json()["period"]


@pytest.mark.asyncio
async def test_get_project_analytics_invalid_range(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=auth_headers,
        params={"range": "90d"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_viewer_cannot_access_project_analytics(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    viewer_headers = await _viewer_headers_for_project(pid)
    r = await test_client.get(
        f"/api/v1/projects/{pid}/analytics",
        headers=viewer_headers,
        params={"range": "7d"},
    )
    assert r.status_code == 403
