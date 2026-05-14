"""Integration tests: task moves + WIP limit via HTTP API (T070)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, insert_tasks


@pytest.mark.asyncio
async def test_wip_limit_second_move_to_in_progress_conflict(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    tid_a, tid_b = await insert_tasks(pid, [("A", "todo"), ("B", "todo")])

    with patch("app.services.kanban_service._schedule_coder_agent"):
        r1 = await test_client.post(
            f"/api/v1/projects/{pid}/tasks/{tid_a}/move",
            headers=auth_headers,
            json={"to": "in_progress"},
        )
        assert r1.status_code == 200
        assert r1.json()["to_status"] == "in_progress"

        r2 = await test_client.post(
            f"/api/v1/projects/{pid}/tasks/{tid_b}/move",
            headers=auth_headers,
            json={"to": "in_progress"},
        )
    assert r2.status_code == 409
    assert "WIP" in r2.json()["detail"] or "wip" in r2.json()["detail"].lower()
