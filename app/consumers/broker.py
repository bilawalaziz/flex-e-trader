import asyncio
import time
from typing import Any, Awaitable, Callable, Final, override

from faststream import BaseMiddleware, Logger, StreamMessage
from faststream.rabbit import RabbitBroker
from app.core.config import settings


# this middleware if used from faststream documentation
class RetryMiddleware(BaseMiddleware):
    MAX_RETRIES: Final[int] = settings.max_retries

    @override
    async def consume_scope(
        self,
        call_next: Callable[[StreamMessage[Any]], Awaitable[Any]],
        msg: StreamMessage[Any],
    ) -> Any:
        logger: Logger = self.context.get_local("logger")
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return await call_next(msg)
            except Exception:
                if attempt == self.MAX_RETRIES:
                    logger.exception("Failed after %s retries.", self.MAX_RETRIES)
                    raise

                logger.exception(
                    "Attempt %s failed, retrying... sleeping for %s seconds",
                    attempt + 1,
                    2**attempt,
                )
                await asyncio.sleep(2**attempt)  # Exponential backoff
        return None


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
    # middlewares=[LoggingMiddleware],
)
