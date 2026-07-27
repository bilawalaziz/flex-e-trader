import time
from typing import Any, Awaitable, Callable, override

from faststream import BaseMiddleware, Logger, StreamMessage
from faststream.rabbit import RabbitBroker
from app.core.config import settings


class LoggingMiddleware(BaseMiddleware):
    """Logs duration and outcome of every message. Non-blocking."""

    @override
    async def consume_scope(
        self,
        call_next: Callable[[StreamMessage[Any]], Awaitable[Any]],
        msg: StreamMessage[Any],
    ) -> Any:
        logger: Logger = self.context.get_local("logger")
        start = time.monotonic()
        queue = getattr(msg, "destination", "unknown")
        msg_id = getattr(msg, "message_id", "unknown")

        try:
            result = await call_next(msg)
            logger.info(
                "queue- msg_processed | queue=%s | id=%s | duration_ms=%.2f",
                queue,
                msg_id,
                (time.monotonic() - start) * 1000,
            )
            return result
        except Exception:
            logger.exception(
                "queue- msg_failed | queue=%s | id=%s | duration_ms=%.2f",
                queue,
                msg_id,
                (time.monotonic() - start) * 1000,
            )
            raise


broker = RabbitBroker(
    url=settings.rabbitmq_url,
    fail_fast=False,
    reconnect_interval=5,
    middlewares=[LoggingMiddleware],
)
