"""Integration tests: document gates for PLAN generation (T070)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project, insert_spec_document


@pytest.mark.asyncio
async def test_generate_plan_blocked_without_spec(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.post(f"/api/v1/projects/{pid}/generate-plan", headers=auth_headers)
    assert r.status_code == 400
    assert "SPEC" in r.json()["detail"]


@pytest.mark.asyncio
async def test_generate_plan_blocked_when_spec_not_approved(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    await insert_spec_document(pid, status="draft")
    r = await test_client.post(f"/api/v1/projects/{pid}/generate-plan", headers=auth_headers)
    assert r.status_code == 400
    assert "approved" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_plan_accepted_when_spec_approved(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    await insert_spec_document(pid, status="approved")
    with patch("app.api.v1.documents.asyncio.create_task"):
        r = await test_client.post(f"/api/v1/projects/{pid}/generate-plan", headers=auth_headers)
    assert r.status_code == 202
    body = r.json()
    assert "agent_run_id" in body


@pytest.mark.asyncio
async def test_approve_spec_auto_starts_plan_generation(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    spec_id = await insert_spec_document(pid, status="draft")
    with patch("app.api.v1.documents.asyncio.create_task"):
        r = await test_client.post(
            f"/api/v1/projects/{pid}/documents/{spec_id}/approve",
            headers=auth_headers,
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["plan_generation_started"] is True
    assert body["plan_agent_run_id"] is not None
