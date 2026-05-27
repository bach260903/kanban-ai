"""Integration tests: task dependency API (US4 / T067)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, insert_tasks


@pytest.mark.asyncio
async def test_add_dependency_blocks_move_and_sets_flag(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("Dep A", "todo"), ("Dep B", "todo")])

    r_add = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json={"depends_on_task_id": str(tid_a)},
    )
    assert r_add.status_code == 201, r_add.text

    r_tasks = await test_client.get(f"/api/v1/projects/{pid}/tasks", headers=auth_headers)
    assert r_tasks.status_code == 200
    todo = r_tasks.json()["todo"]
    row_b = next(t for t in todo if t["id"] == str(tid_b))
    assert row_b["is_blocked"] is True

    with patch("app.services.kanban_service._schedule_coder_agent"):
        r_move = await test_client.post(
            f"/api/v1/projects/{pid}/tasks/{tid_b}/move",
            headers=auth_headers,
            json={"to": "in_progress"},
        )
    assert r_move.status_code == 409
    assert "blocked" in r_move.json()["detail"].lower()


@pytest.mark.asyncio
async def test_circular_dependency_returns_409(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("Cycle A", "todo"), ("Cycle B", "todo")])

    r1 = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json={"depends_on_task_id": str(tid_a)},
    )
    assert r1.status_code == 201

    r2 = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_a}/dependencies",
        headers=auth_headers,
        json={"depends_on_task_id": str(tid_b)},
    )
    assert r2.status_code == 409
    assert "circular" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_duplicate_dependency_returns_200(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("Dup A", "todo"), ("Dup B", "todo")])

    body = {"depends_on_task_id": str(tid_a)}
    r1 = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json=body,
    )
    assert r1.status_code == 201

    r2 = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json=body,
    )
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_done_prerequisite_unlocks_dependent_on_get_tasks(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("Done A", "done"), ("Wait B", "todo")])

    r_add = await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json={"depends_on_task_id": str(tid_a)},
    )
    assert r_add.status_code == 201

    r_tasks = await test_client.get(f"/api/v1/projects/{pid}/tasks", headers=auth_headers)
    row_b = next(t for t in r_tasks.json()["todo"] if t["id"] == str(tid_b))
    assert row_b["is_blocked"] is False


@pytest.mark.asyncio
async def test_dependency_graph_lists_edges(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("Graph A", "todo"), ("Graph B", "todo")])

    await test_client.post(
        f"/api/v1/projects/{pid}/tasks/{tid_b}/dependencies",
        headers=auth_headers,
        json={"depends_on_task_id": str(tid_a)},
    )

    r = await test_client.get(f"/api/v1/projects/{pid}/dependency-graph", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 2
    assert any(e["from"] == str(tid_b) and e["to"] == str(tid_a) for e in data["edges"])
