"""Outbound webhook delivery pipeline (US7 / T094–T097)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_maker
from app.exceptions import NotFoundError
from app.models.webhook import WebhookConfig, WebhookDelivery, WebhookDeliveryStatus

logger = logging.getLogger(__name__)

WEBHOOK_QUEUE = "webhook_queue"
WEBHOOK_DEFER_PREFIX = "webhook:defer:"
RETRY_DELAYS = [0, 5, 30]
MAX_ATTEMPTS = len(RETRY_DELAYS)
FETCH_RETRIES = 5
FETCH_RETRY_DELAY_S = 0.5

_redis: redis.Redis | None = None


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _build_headers(
    event_type: str,
    payload_bytes: bytes,
    secret: str | None,
) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-NeoKanban-Event": event_type,
    }
    if secret:
        headers["X-NeoKanban-Signature"] = _sign_payload(payload_bytes, secret)
    return headers


async def _post_webhook(
    url: str,
    event_type: str,
    payload: dict[str, Any],
    secret: str | None,
) -> tuple[bool, int | None]:
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    headers = _build_headers(event_type, payload_bytes, secret)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, content=payload_bytes, headers=headers)
        return resp.status_code < 400, resp.status_code
    except httpx.RequestError:
        return False, None


async def _deliver_once(
    delivery_id: UUID,
    session: AsyncSession,
) -> tuple[bool, int | None]:
    delivery = await session.scalar(
        select(WebhookDelivery)
        .where(WebhookDelivery.id == delivery_id)
        .options(selectinload(WebhookDelivery.webhook_config))
    )
    if delivery is None or delivery.webhook_config is None:
        return False, None
    config = delivery.webhook_config
    if not config.enabled:
        return False, None
    return await _post_webhook(config.url, delivery.event_type, delivery.payload, config.secret)


async def _deliver_once_direct(
    config: WebhookConfig,
    payload: dict[str, Any],
    *,
    event_type: str = "webhook.test",
) -> tuple[bool, int | None]:
    return await _post_webhook(config.url, event_type, payload, config.secret)


async def enqueue_delivery(
    session: AsyncSession,
    project_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    configs = (
        await session.scalars(
            select(WebhookConfig).where(
                WebhookConfig.project_id == project_id,
                WebhookConfig.enabled.is_(True),
                WebhookConfig.events.contains([event_type]),
            )
        )
    ).all()
    if not configs:
        return

    redis_client = await _get_redis()
    for config in configs:
        delivery = WebhookDelivery(
            webhook_config_id=config.id,
            event_type=event_type,
            payload=payload,
            status=WebhookDeliveryStatus.PENDING,
        )
        session.add(delivery)
        await session.flush()
        await redis_client.rpush(WEBHOOK_QUEUE, str(delivery.id))


async def _fetch_delivery(
    session: AsyncSession,
    delivery_id: UUID,
) -> WebhookDelivery | None:
    for _ in range(FETCH_RETRIES):
        delivery = await session.scalar(
            select(WebhookDelivery)
            .where(WebhookDelivery.id == delivery_id)
            .options(selectinload(WebhookDelivery.webhook_config))
        )
        if delivery is not None:
            return delivery
        await asyncio.sleep(FETCH_RETRY_DELAY_S)
    return None


async def _defer_missing_delivery(delivery_id: UUID) -> None:
    """Re-queue once when the row is not visible yet (caller transaction not committed)."""
    redis_client = await _get_redis()
    defer_key = f"{WEBHOOK_DEFER_PREFIX}{delivery_id}"
    if await redis_client.set(defer_key, "1", nx=True, ex=60):
        await asyncio.sleep(1)
        await redis_client.rpush(WEBHOOK_QUEUE, str(delivery_id))
        logger.info("Deferred webhook delivery %s pending DB commit", delivery_id)
    else:
        logger.warning("Webhook delivery %s not found; giving up after deferral", delivery_id)


async def _process_one_delivery(delivery_id: UUID) -> None:
    async with async_session_maker() as session:
        delivery = await _fetch_delivery(session, delivery_id)
        if delivery is None:
            await _defer_missing_delivery(delivery_id)
            return
        if delivery.status == WebhookDeliveryStatus.SUCCESS:
            return
        if delivery.webhook_config is None or not delivery.webhook_config.enabled:
            delivery.status = WebhookDeliveryStatus.FAILED
            delivery.last_attempt_at = datetime.now(UTC)
            await session.commit()
            return

        success = False
        http_status: int | None = None
        for attempt in range(MAX_ATTEMPTS):
            await asyncio.sleep(RETRY_DELAYS[attempt])
            success, http_status = await _deliver_once(delivery_id, session)
            delivery.attempts = attempt + 1
            delivery.last_attempt_at = datetime.now(UTC)
            delivery.http_status = http_status
            if success:
                delivery.status = WebhookDeliveryStatus.SUCCESS
                break
            delivery.status = (
                WebhookDeliveryStatus.RETRYING
                if attempt < MAX_ATTEMPTS - 1
                else WebhookDeliveryStatus.FAILED
            )

        await session.commit()


async def process_deliveries() -> None:
    """Background worker: BLPOP from Redis, deliver with retry."""
    redis_client = await _get_redis()
    while True:
        try:
            result = await redis_client.blpop(WEBHOOK_QUEUE, timeout=30)
            if result is None:
                continue
            _, delivery_id_raw = result
            try:
                delivery_id = UUID(str(delivery_id_raw))
            except ValueError:
                logger.warning("Ignoring invalid webhook queue entry: %r", delivery_id_raw)
                continue
            await _process_one_delivery(delivery_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Webhook delivery worker error")
            continue


async def test_webhook(session: AsyncSession, webhook_id: UUID) -> dict[str, Any]:
    config = await session.get(WebhookConfig, webhook_id)
    if config is None:
        raise NotFoundError("Webhook not found.")
    if not config.enabled:
        raise NotFoundError("Webhook not found.")

    payload = {
        "event": "webhook.test",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    start = asyncio.get_running_loop().time()
    delivered, http_status = await _deliver_once_direct(config, payload)
    elapsed_ms = int((asyncio.get_running_loop().time() - start) * 1000)
    return {
        "delivered": delivered,
        "http_status": http_status,
        "response_time_ms": elapsed_ms,
    }
