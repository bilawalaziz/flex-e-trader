import aio_pika
from faststream.rabbit import (
    ExchangeType,
    QueueType,
    RabbitBroker,
    RabbitQueue,
    RabbitExchange,
)
from app.core.config import settings


async def declare_delay_queue(broker: RabbitBroker):

    price_delay_exchange = RabbitExchange(
        name=settings.delay_exchange,
        type=ExchangeType.TOPIC,
        durable=True,
    )

    price_delay_queue = RabbitQueue(
        name=settings.delay_queue,
        durable=True,
        queue_type=QueueType.QUORUM,
        routing_key="prices.#",
        arguments={
            "x-dead-letter-exchange": settings.dlx_exchange,  # "prices.dlx",
            "x-message-ttl": settings.queue_msg_ttl,
        },
    )

    queue: aio_pika.RobustQueue = await broker.declare_queue(price_delay_queue)

    exchange: aio_pika.RobustExchange = await broker.declare_exchange(
        price_delay_exchange
    )

    await queue.bind(exchange=exchange, routing_key="prices.#")
