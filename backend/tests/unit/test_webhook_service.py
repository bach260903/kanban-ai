"""Unit tests for webhook service (US7 / T094–T097)."""

from __future__ import annotations

import hmac
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundError
from app.models.webhook import WebhookConfig, WebhookDelivery, WebhookDeliveryStatus
from app.services import webhook_service


@pytest_asyncio.fixture
async def webhook_project(async_db_session: AsyncSession) -> dict:
    project_res = await async_db_session.execute(
        text(
            """
            INSERT INTO projects (name, description, primary_language, constitution, status)
            VALUES (:name, 'test', 'python', '', 'active')
            RETURNING id
            """
        ),
        {"name": f"Webhook Project {uuid.uuid4().hex[:8]}"},
    )
    project_id = project_res.scalar_one()
    config = WebhookConfig(
        project_id=project_id,
        url="https://example.com/hook",
        secret="mysecret",
        events=["task.done", "task.needs_review"],
        enabled=True,
    )
    async_db_session.add(config)
    await async_db_session.flush()
    return {"project_id": project_id, "config": config}


def test_hmac_signature() -> None:
    payload = b'{"event":"task.done"}'
    sig = webhook_service._sign_payload(payload, "mysecret")
    assert sig.startswith("sha256=")
    assert hmac.compare_digest(sig, webhook_service._sign_payload(payload, "mysecret"))
    assert not hmac.compare_digest(sig, webhook_service._sign_payload(payload, "wrongsecret"))


@pytest.mark.asyncio
async def test_enqueue_delivery_creates_pending_and_queues(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    mock_redis = AsyncMock()
    mock_redis.rpush = AsyncMock()

    with patch.object(webhook_service, "_get_redis", AsyncMock(return_value=mock_redis)):
        await webhook_service.enqueue_delivery(
            async_db_session,
            webhook_project["project_id"],
            "task.done",
            {"event": "task.done", "task_id": str(uuid.uuid4())},
        )

    rows = (
        await async_db_session.scalars(
            select(WebhookDelivery).where(
                WebhookDelivery.webhook_config_id == webhook_project["config"].id
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == WebhookDeliveryStatus.PENDING
    assert rows[0].event_type == "task.done"
    mock_redis.rpush.assert_awaited_once_with(
        webhook_service.WEBHOOK_QUEUE,
        str(rows[0].id),
    )


@pytest.mark.asyncio
async def test_enqueue_delivery_skips_disabled_or_unsubscribed(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    webhook_project["config"].enabled = False
    await async_db_session.flush()
    mock_redis = AsyncMock()
    with patch.object(webhook_service, "_get_redis", AsyncMock(return_value=mock_redis)):
        await webhook_service.enqueue_delivery(
            async_db_session,
            webhook_project["project_id"],
            "task.done",
            {"event": "task.done"},
        )
    mock_redis.rpush.assert_not_awaited()

    webhook_project["config"].enabled = True
    webhook_project["config"].events = ["task.needs_review"]
    await async_db_session.flush()
    with patch.object(webhook_service, "_get_redis", AsyncMock(return_value=mock_redis)):
        await webhook_service.enqueue_delivery(
            async_db_session,
            webhook_project["project_id"],
            "task.done",
            {"event": "task.done"},
        )
    mock_redis.rpush.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_one_delivery_success(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    delivery = WebhookDelivery(
        webhook_config_id=webhook_project["config"].id,
        event_type="task.done",
        payload={"event": "task.done"},
        status=WebhookDeliveryStatus.PENDING,
    )
    async_db_session.add(delivery)
    await async_db_session.flush()

    @asynccontextmanager
    async def _session_ctx():
        yield async_db_session

    with (
        patch.object(webhook_service, "async_session_maker", _session_ctx),
        patch.object(
            webhook_service,
            "_deliver_once",
            AsyncMock(return_value=(True, 200, None)),
        ),
    ):
        await webhook_service._process_one_delivery(delivery.id)

    updated = await async_db_session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
    )
    assert updated is not None
    assert updated.status == WebhookDeliveryStatus.SUCCESS
    assert updated.attempts == 1
    assert updated.http_status == 200


@pytest.mark.asyncio
async def test_process_one_delivery_retry_then_fail(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    delivery = WebhookDelivery(
        webhook_config_id=webhook_project["config"].id,
        event_type="task.done",
        payload={"event": "task.done"},
        status=WebhookDeliveryStatus.PENDING,
    )
    async_db_session.add(delivery)
    await async_db_session.flush()

    @asynccontextmanager
    async def _session_ctx():
        yield async_db_session

    with (
        patch.object(webhook_service, "async_session_maker", _session_ctx),
        patch.object(
            webhook_service,
            "_deliver_once",
            AsyncMock(side_effect=[(False, 500, None), (False, 500, None), (False, 500, None)]),
        ),
        patch("app.services.webhook_service.asyncio.sleep", AsyncMock()),
    ):
        await webhook_service._process_one_delivery(delivery.id)

    updated = await async_db_session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
    )
    assert updated is not None
    assert updated.status == WebhookDeliveryStatus.FAILED
    assert updated.attempts == 3
    assert updated.http_status == 500


@pytest.mark.asyncio
async def test_process_one_delivery_retry_then_succeed(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    delivery = WebhookDelivery(
        webhook_config_id=webhook_project["config"].id,
        event_type="task.done",
        payload={"event": "task.done"},
        status=WebhookDeliveryStatus.PENDING,
    )
    async_db_session.add(delivery)
    await async_db_session.flush()

    @asynccontextmanager
    async def _session_ctx():
        yield async_db_session

    with (
        patch.object(webhook_service, "async_session_maker", _session_ctx),
        patch.object(
            webhook_service,
            "_deliver_once",
            AsyncMock(side_effect=[(False, 503, None), (True, 200, None)]),
        ),
        patch("app.services.webhook_service.asyncio.sleep", AsyncMock()),
    ):
        await webhook_service._process_one_delivery(delivery.id)

    updated = await async_db_session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
    )
    assert updated is not None
    assert updated.status == WebhookDeliveryStatus.SUCCESS
    assert updated.attempts == 2
    assert updated.http_status == 200


@pytest.mark.asyncio
async def test_process_one_delivery_skips_disabled_config(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    webhook_project["config"].enabled = False
    await async_db_session.flush()
    delivery = WebhookDelivery(
        webhook_config_id=webhook_project["config"].id,
        event_type="task.done",
        payload={"event": "task.done"},
        status=WebhookDeliveryStatus.PENDING,
    )
    async_db_session.add(delivery)
    await async_db_session.flush()

    @asynccontextmanager
    async def _session_ctx():
        yield async_db_session

    with (
        patch.object(webhook_service, "async_session_maker", _session_ctx),
        patch.object(webhook_service, "_deliver_once", AsyncMock()) as deliver_mock,
    ):
        await webhook_service._process_one_delivery(delivery.id)

    deliver_mock.assert_not_awaited()
    updated = await async_db_session.scalar(
        select(WebhookDelivery).where(WebhookDelivery.id == delivery.id)
    )
    assert updated is not None
    assert updated.status == WebhookDeliveryStatus.FAILED
    assert updated.attempts == 0


@pytest.mark.asyncio
async def test_process_one_delivery_defers_when_row_missing() -> None:
    delivery_id = uuid.uuid4()
    with (
        patch.object(webhook_service, "_fetch_delivery", AsyncMock(return_value=None)),
        patch.object(webhook_service, "_defer_missing_delivery", AsyncMock()) as defer_mock,
    ):
        await webhook_service._process_one_delivery(delivery_id)
    defer_mock.assert_awaited_once_with(delivery_id)


@pytest.mark.asyncio
async def test_test_webhook_disabled_raises_not_found(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    webhook_project["config"].enabled = False
    await async_db_session.flush()
    with pytest.raises(NotFoundError, match="Webhook not found"):
        await webhook_service.test_webhook(async_db_session, webhook_project["config"].id)


@pytest.mark.asyncio
async def test_test_webhook_returns_metrics(
    async_db_session: AsyncSession,
    webhook_project: dict,
) -> None:
    with patch.object(
        webhook_service,
        "_deliver_once_direct",
        AsyncMock(return_value=(True, 204, None)),
    ):
        result = await webhook_service.test_webhook(
            async_db_session,
            webhook_project["config"].id,
        )

    assert result["delivered"] is True
    assert result["http_status"] == 204
    assert result["response_time_ms"] >= 0


@pytest.mark.asyncio
async def test_test_webhook_not_found(
    async_db_session: AsyncSession,
) -> None:
    with pytest.raises(NotFoundError, match="Webhook not found"):
        await webhook_service.test_webhook(async_db_session, uuid.uuid4())
