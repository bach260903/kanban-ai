"""Integration tests: projects CRUD + duplicate name (T070)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project


@pytest.mark.asyncio
async def test_projects_crud_and_duplicate_name(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    base = f"itest_proj_{uuid.uuid4().hex[:10]}"
    a_name, b_name = f"{base}_a", f"{base}_b"

    r = await test_client.post(
        "/api/v1/projects",
        json={"name": a_name, "description": "d0", "primary_language": "python"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    pa = r.json()
    pid_a = pa["id"]
    assert pa["name"] == a_name
    assert pa["status"] == "active"

    r = await test_client.get("/api/v1/projects", headers=auth_headers)
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert pid_a in ids

    r = await test_client.get(f"/api/v1/projects/{pid_a}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == a_name

    r = await test_client.post(
        "/api/v1/projects",
        json={"name": b_name, "description": "d1", "primary_language": "python"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    pid_b = r.json()["id"]

    r = await test_client.post(
        "/api/v1/projects",
        json={"name": a_name, "description": "dup", "primary_language": "python"},
        headers=auth_headers,
    )
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"].lower()

    r = await test_client.put(
        f"/api/v1/projects/{pid_a}",
        json={"name": b_name},
        headers=auth_headers,
    )
    assert r.status_code == 409

    r = await test_client.put(
        f"/api/v1/projects/{pid_a}",
        json={"description": "updated"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["description"] == "updated"

    r = await test_client.delete(f"/api/v1/projects/{pid_a}", headers=auth_headers)
    assert r.status_code == 204

    r = await test_client.get(f"/api/v1/projects/{pid_a}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"

    # cleanup second project (optional; rolled back if outer test txn — commits are real)
    await test_client.delete(f"/api/v1/projects/{pid_b}", headers=auth_headers)


@pytest.mark.asyncio
async def test_projects_require_auth(test_client: AsyncClient) -> None:
    r = await test_client.get("/api/v1/projects")
    assert r.status_code == 401
