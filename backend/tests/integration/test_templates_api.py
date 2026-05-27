"""Integration tests: task template API (US5 / T077)."""

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
from tests.integration.helpers import create_project


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


@pytest.mark.asyncio
async def test_create_and_list_project_template(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)

    r_create = await test_client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "Bug fix",
            "title_template": "Fix: {summary}",
            "description_template": "Steps to reproduce…",
            "scope": "project",
            "project_id": str(pid),
        },
    )
    assert r_create.status_code == 201, r_create.text
    body = r_create.json()
    assert body["name"] == "Bug fix"
    assert body["scope"] == "project"
    assert body["project_id"] == str(pid)

    r_list = await test_client.get(
        f"/api/v1/templates?project_id={pid}&scope=project",
        headers=auth_headers,
    )
    assert r_list.status_code == 200
    names = [t["name"] for t in r_list.json()]
    assert "Bug fix" in names


@pytest.mark.asyncio
async def test_duplicate_template_name_returns_409(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    payload = {
        "name": "Duplicate",
        "title_template": "Title",
        "description_template": "",
        "scope": "project",
        "project_id": str(pid),
    }
    r1 = await test_client.post("/api/v1/templates", headers=auth_headers, json=payload)
    assert r1.status_code == 201

    r2 = await test_client.post("/api/v1/templates", headers=auth_headers, json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_delete_template_by_creator(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r_create = await test_client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": "To delete",
            "title_template": "T",
            "description_template": "",
            "scope": "project",
            "project_id": str(pid),
        },
    )
    template_id = r_create.json()["id"]

    r_del = await test_client.delete(
        f"/api/v1/templates/{template_id}",
        headers=auth_headers,
    )
    assert r_del.status_code == 204

    r_list = await test_client.get(
        f"/api/v1/templates?project_id={pid}&scope=project",
        headers=auth_headers,
    )
    assert all(t["id"] != template_id for t in r_list.json())


@pytest.mark.asyncio
async def test_list_global_templates_without_project_id(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    await create_project(test_client, auth_headers)
    name = f"Global spike {uuid.uuid4().hex[:8]}"
    r_create = await test_client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": name,
            "title_template": "Spike: {topic}",
            "description_template": "",
            "scope": "global",
        },
    )
    assert r_create.status_code == 201, r_create.text

    r_list = await test_client.get(
        "/api/v1/templates?scope=global",
        headers=auth_headers,
    )
    assert r_list.status_code == 200
    assert any(t["name"] == name for t in r_list.json())


@pytest.mark.asyncio
async def test_viewer_cannot_create_project_template(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    viewer_headers = await _viewer_headers_for_project(pid)

    r = await test_client.post(
        "/api/v1/templates",
        headers=viewer_headers,
        json={
            "name": "Viewer template",
            "title_template": "T",
            "description_template": "",
            "scope": "project",
            "project_id": str(pid),
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_name_after_whitespace_returns_409(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    payload = {
        "name": "Trimmed",
        "title_template": "Title",
        "description_template": "",
        "scope": "project",
        "project_id": str(pid),
    }
    assert (await test_client.post("/api/v1/templates", headers=auth_headers, json=payload)).status_code == 201

    payload["name"] = "  Trimmed  "
    r = await test_client.post("/api/v1/templates", headers=auth_headers, json=payload)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_non_member_cannot_list_project_templates(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    outsider_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, display_name)
                VALUES (:id, :email, :hashed_password, :display_name)
                """
            ),
            {
                "id": outsider_id,
                "email": f"outsider-{outsider_id.hex[:8]}@example.com",
                "hashed_password": "pytest-hash",
                "display_name": "Outsider",
            },
        )
    token = jwt.encode(
        {"sub": str(outsider_id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    outsider_headers = {"Authorization": f"Bearer {token}"}

    r = await test_client.get(
        f"/api/v1/templates?project_id={pid}",
        headers=outsider_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_combined_templates_for_project(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    project_name = f"ProjTpl {uuid.uuid4().hex[:6]}"
    global_name = f"GlobTpl {uuid.uuid4().hex[:6]}"

    r1 = await test_client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": project_name,
            "title_template": "P title",
            "description_template": "",
            "scope": "project",
            "project_id": str(pid),
        },
    )
    assert r1.status_code == 201

    r2 = await test_client.post(
        "/api/v1/templates",
        headers=auth_headers,
        json={
            "name": global_name,
            "title_template": "G title",
            "description_template": "",
            "scope": "global",
        },
    )
    assert r2.status_code == 201

    r_list = await test_client.get(f"/api/v1/templates?project_id={pid}", headers=auth_headers)
    assert r_list.status_code == 200
    names = {t["name"] for t in r_list.json()}
    assert project_name in names
    assert global_name in names
