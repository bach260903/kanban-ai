"""Integration test: coding_backend CRUD and /backends/available endpoint (T023)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project_with_default_backend(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    name = f"itest_backend_{uuid.uuid4().hex[:10]}"
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": name, "primary_language": "python"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["coding_backend"] == "groq"


@pytest.mark.asyncio
async def test_create_project_with_explicit_backend(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    name = f"itest_backend_{uuid.uuid4().hex[:10]}"
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": name, "primary_language": "python", "coding_backend": "openai"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["coding_backend"] == "openai"


@pytest.mark.asyncio
async def test_update_project_backend(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    name = f"itest_backend_{uuid.uuid4().hex[:10]}"
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": name, "primary_language": "python"},
        headers=auth_headers,
    )
    pid = r.json()["id"]

    r = await test_client.put(
        f"/api/v1/projects/{pid}",
        json={"coding_backend": "openai"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["coding_backend"] == "openai"

    r = await test_client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert r.json()["coding_backend"] == "openai"


@pytest.mark.asyncio
async def test_backend_change_does_not_affect_tasks(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    name = f"itest_backend_{uuid.uuid4().hex[:10]}"
    r = await test_client.post(
        "/api/v1/projects",
        json={"name": name, "primary_language": "python"},
        headers=auth_headers,
    )
    pid = r.json()["id"]

    r = await test_client.post(
        f"/api/v1/projects/{pid}/tasks",
        json={"title": "Test task", "priority": 1},
        headers=auth_headers,
    )
    assert r.status_code == 201
    tid = r.json()["id"]

    # Switch backend
    await test_client.put(
        f"/api/v1/projects/{pid}",
        json={"coding_backend": "claude_code"},
        headers=auth_headers,
    )

    # Task must be unaffected
    r = await test_client.get(f"/api/v1/projects/{pid}/tasks/{tid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == tid


@pytest.mark.asyncio
async def test_backends_available_endpoint(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    r = await test_client.get("/api/v1/backends/available", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert "available" in data
    assert "unavailable" in data
    all_backends = set(data["available"]) | {u["backend"] for u in data["unavailable"]}
    assert all_backends == {"groq", "claude_code", "openai", "gemini"}
