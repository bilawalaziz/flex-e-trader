import datetime
import logging

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
from app.schemas.events import PriceTick
from app.models.price import Price
from app.core.database import async_session
from app.core.config import settings
from app.consumers.broker import broker
from app.repositories.price import upsert_price

logger = logging.getLogger(__name__)

router = RabbitRouter()

prices_exchange = RabbitExchange(
    name=settings.main_exchange,
    type=ExchangeType.TOPIC,
    durable=True,
)

# price_delay_exchange = RabbitExchange(
#     name=settings.delay_exchange,
#     type=ExchangeType.TOPIC,
#     durable=True,
# )

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

# price_delay_queue = RabbitQueue(
#     name=settings.delay_queue,
#     durable=True,
#     queue_type=QueueType.QUORUM,
#     routing_key="prices.#",
#     arguments={
#         "x-dead-letter-exchange": settings.dlx_exchange,  # "prices.dlx",
#         "x-message-ttl": settings.queue_msg_ttl,
#     },
# )

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


@router.subscriber(
    queue=price_dlq,
    exchange=dlx_exchange,
    ack_policy=AckPolicy.ACK,
)
async def handle_failed(msg: PriceTick):
    logger.error(
        "DLQ | product=%s | timestamp=%s | all retries exhausted",
        msg.product,
        msg.timestamp,
    )


@router.subscriber(
    queue=price_queue,
    exchange=prices_exchange,
    ack_policy=AckPolicy.MANUAL,
)
async def handle_price(msg: PriceTick, raw_msg: RabbitMessage):
    retry_count = int(raw_msg.headers.get(RETRY_HEADER, 0))
    routing_key = _get_routing_key(raw_msg)

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
                "queue-  DEDUP_SKIP | product=%s | already exists", msg.product
            )

        await raw_msg.ack()
    except ValidationError as e:
        logger.info(
            "VALIDATION_FAIL | product=%s | attempt=%s | errors=%s",
            getattr(raw_msg, "product", "unknown"),
            retry_count + 1,
            e,
        )
        # Bad data — don't retry, go straight to DLQ or just ack and drop
        await broker.publish(
            msg,
            exchange=dlx_exchange.name,
            routing_key="prices.failed",
            headers={**msg.headers, "x-fail-reason": "validation_error"},
        )
        logger.error(
            "queue- DLQ_ROUTED | product=%s | total_attempts=%s",
            msg.product,
            retry_count + 1,
        )
        await raw_msg.ack()

    except Exception as e:
        logger.exception("FAIL | product=%s | attempt=%s", msg.product, retry_count + 1)

        new_headers = dict(raw_msg.headers)
        new_headers[RETRY_HEADER] = retry_count + 1

        if retry_count >= MAX_RETRIES:
            await broker.publish(
                message=msg,
                exchange=settings.delay_exchange,
                routing_key=routing_key,
                headers=new_headers,
            )
            logger.warning(
                "queue- RETRY_QUEUED | product=%s | delay=%sms | attempt=%s/%s",
                msg.product,
                settings.retry_ttl_ms,
                retry_count + 1,
                MAX_RETRIES,
            )
            await raw_msg.ack()
        else:
            await broker.publish(
                msg,
                exchange=dlx_exchange.name,
                routing_key="prices.failed",
                headers=new_headers,
            )
            logger.error(
                "queue- DLQ_ROUTED | product=%s | total_attempts=%s",
                msg.product,
                retry_count + 1,
            )
            await raw_msg.ack()
