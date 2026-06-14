import json
import logging
from typing import Any

from faststream import AckPolicy
from faststream.rabbit import (
    ExchangeType,
    QueueType,
    RabbitExchange,
    RabbitMessage,
    RabbitQueue,
    RabbitRouter,
)
from pydantic import ValidationError
from app.repositories.events_repo import add_failed_event
from app.schemas import FailedEventCreate, PriceTick
from app.core.database import async_session
from app.core.config import settings
from app.consumers.broker import broker
from app.repositories.price_repo import upsert_price

logger = logging.getLogger(__name__)

router = RabbitRouter()

prices_exchange = RabbitExchange(
    name=settings.main_exchange,
    type=ExchangeType.TOPIC,
    durable=True,
)

dlx_exchange = RabbitExchange(
    name=settings.dlx_exchange,
    type=ExchangeType.FANOUT,
    durable=True,
)

price_queue = RabbitQueue(
    name=settings.main_queue,
    durable=True,
    queue_type=QueueType.QUORUM,
    routing_key="prices.#",
)


price_dlq = RabbitQueue(
    name="prices.dlq",
    durable=True,
    queue_type=QueueType.QUORUM,
    routing_key="prices.failed",
)

RETRY_HEADER = "x-retry-count"
MAX_RETRIES = settings.max_retries


def _get_routing_key(raw_msg: RabbitMessage) -> str:
    try:
        return raw_msg.raw_message.routing_key
    except AttributeError:
        return raw_msg.headers.get("x-routing-key", "prices.unknown")


def _build_headers(raw_msg: RabbitMessage, retry_count: int, **extra: Any) -> dict:
    """Immutable header builder for republishing."""
    return {**raw_msg.headers, RETRY_HEADER: retry_count, **extra}


async def _publish_to_delay(
    raw_msg: RabbitMessage,
    body: dict,
    retry_count: int,
    routing_key: str,
) -> None:
    await broker.publish(
        body,
        exchange=settings.delay_exchange,
        routing_key=routing_key,
        headers=_build_headers(raw_msg, retry_count),
    )
    logger.warning(
        "queue- RETRY_QUEUED | delay=%sms | attempt=%s/%s",
        settings.queue_msg_ttl,
        retry_count,
        MAX_RETRIES + 1,
    )
    await raw_msg.ack()


async def _publish_to_dlq(
    raw_msg: RabbitMessage,
    body: dict,
    retry_count: int,
    reason: str,
) -> None:
    await broker.publish(
        body,
        exchange=settings.dlx_exchange,
        routing_key="prices.failed",
        headers=_build_headers(raw_msg, retry_count, x_fail_reason=reason),
    )
    logger.error(
        "queue- DLQ_ROUTED | total_attempts=%s | reason=%s",
        retry_count + 1,
        reason,
    )
    await raw_msg.ack()


@router.subscriber(
    queue=price_dlq,
    exchange=dlx_exchange,
    ack_policy=AckPolicy.MANUAL,
)
async def handle_dlq(raw_msg: RabbitMessage):
    """
    Final dead-letter handler.
    Just logs/alerting. No retry from here.
    """
    body = raw_msg.body
    try:
        body_dict = json.loads(body) if isinstance(body, bytes) else body
    except (json.JSONDecodeError, TypeError):
        body_dict = {"raw_body": str(body)}

    fail_reason = raw_msg.headers.get("x_fail_reason", "unknown")
    retry_count = raw_msg.headers.get(RETRY_HEADER, 0)

    async with async_session() as session:
        await add_failed_event(
            session=session,
            event=FailedEventCreate(
                body=body_dict,
                headers=dict(raw_msg.headers),
                fail_reason=raw_msg.headers.get("x_fail_reason"),
            ),
        )
        await session.commit()

    await raw_msg.ack()
    logger.error(
        "DLQ_RECEIVED | reason=%s | retries=%s | body=%s",
        fail_reason,
        retry_count,
        body_dict,
    )


@router.subscriber(
    queue=price_queue,
    exchange=prices_exchange,
    ack_policy=AckPolicy.MANUAL,
)
async def handle_price(raw_msg: RabbitMessage):
    retry_count = int(raw_msg.headers.get(RETRY_HEADER, 0))
    routing_key = _get_routing_key(raw_msg)
    body = raw_msg.body

    # ── Parse JSON safely ──
    try:
        body_dict = json.loads(body) if isinstance(body, bytes) else body
    except (json.JSONDecodeError, TypeError):
        logger.error("queue- MALFORMED_JSON | body=%s", body)
        # Use empty dict or raw body string for DLQ payload
        dlq_payload = {"malformed_raw": str(body)}
        await _publish_to_dlq(raw_msg, dlq_payload, retry_count, "malformed_json")
        return

    # ── Validate Pydantic ──
    try:
        msg = PriceTick.model_validate(body_dict)
    except ValidationError as e:
        logger.warning("queue- VALIDATION_FAIL | errors=%s | body=%s", e, body_dict)
        await _publish_to_dlq(raw_msg, body_dict, retry_count, "validation_error")
        return

    # ── Business Logic ──
    logger.info(
        "queue- START | product=%s | attempt=%s/%s | rk=%s",
        msg.product,
        retry_count + 1,
        MAX_RETRIES + 1,
        routing_key,
    )

    try:
        async with async_session() as session:
            inserted = await upsert_price(session=session, tick=msg)
            await session.commit()

        if inserted:
            logger.info("queue- INSERT_OK | product=%s", msg.product)
        else:
            logger.warning(
                "queue- DEDUP_SKIP | product=%s | already exists", msg.product
            )

        await raw_msg.ack()

    except Exception:
        logger.exception(
            "queue- FAIL | product=%s | attempt=%s",
            msg.product,
            retry_count + 1,
        )

        if retry_count < MAX_RETRIES:
            await _publish_to_delay(raw_msg, body_dict, retry_count + 1, routing_key)
        else:
            await _publish_to_dlq(
                raw_msg, body_dict, retry_count + 1, "max_retries_exceeded"
            )
