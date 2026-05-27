"""Integration tests: webhooks API (US7 / T099)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.integration.helpers import create_project


@pytest.mark.asyncio
async def test_webhooks_crud_and_test(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)

    r = await test_client.get(f"/api/v1/projects/{pid}/webhooks", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []

    r = await test_client.post(
        f"/api/v1/projects/{pid}/webhooks",
        headers=auth_headers,
        json={
            "url": "https://example.com/hook",
            "secret": "s3cr3t",
            "events": ["task.done", "task.needs_review"],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    webhook_id = body["id"]
    assert body["url"] == "https://example.com/hook"
    assert body["enabled"] is True
    assert "secret" not in body

    r = await test_client.get(f"/api/v1/projects/{pid}/webhooks", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await test_client.patch(
        f"/api/v1/projects/{pid}/webhooks/{webhook_id}",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = await test_client.post(
        f"/api/v1/projects/{pid}/webhooks/{webhook_id}/test",
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"].lower()

    r = await test_client.patch(
        f"/api/v1/projects/{pid}/webhooks/{webhook_id}",
        headers=auth_headers,
        json={"enabled": True},
    )
    assert r.status_code == 200

    with patch(
        "app.api.v1.webhooks.webhook_service.test_webhook",
        AsyncMock(return_value={"delivered": True, "http_status": 200, "response_time_ms": 42}),
    ):
        r = await test_client.post(
            f"/api/v1/projects/{pid}/webhooks/{webhook_id}/test",
            headers=auth_headers,
        )
    assert r.status_code == 200, r.text
    assert r.json()["delivered"] is True
    assert r.json()["http_status"] == 200

    r = await test_client.delete(
        f"/api/v1/projects/{pid}/webhooks/{webhook_id}",
        headers=auth_headers,
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_create_webhook_rejects_invalid_event(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.post(
        f"/api/v1/projects/{pid}/webhooks",
        headers=auth_headers,
        json={
            "url": "https://example.com/hook",
            "events": ["not.a.real.event"],
        },
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_webhook_rejects_empty_events(
    test_client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    pid = await create_project(test_client, auth_headers)
    r = await test_client.post(
        f"/api/v1/projects/{pid}/webhooks",
        headers=auth_headers,
        json={
            "url": "https://example.com/hook",
            "events": ["task.done"],
        },
    )
    assert r.status_code == 201
    webhook_id = r.json()["id"]

    r = await test_client.patch(
        f"/api/v1/projects/{pid}/webhooks/{webhook_id}",
        headers=auth_headers,
        json={"events": []},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhooks_require_auth(test_client: AsyncClient) -> None:
    fake = UUID("00000000-0000-0000-0000-000000000001")
    r = await test_client.get(f"/api/v1/projects/{fake}/webhooks")
    assert r.status_code == 401
