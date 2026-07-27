import asyncio
import random
from datetime import datetime, timedelta, timezone

from app.celery_app import celery_app
from app.consumers.broker import broker
from app.core.config import settings

PRODUCTS = ["DE-AT-2024", "DE-AT-2025", "DE-AT-2026", "DE-AT-2027", "DE-AT-2028"]


def generate_tick(index: int, delivery_ts: datetime) -> dict:
    product = random.choice(PRODUCTS)
    return {
        "product": product,
        "timestamp": delivery_ts.isoformat().replace("+00:00", "Z"),
        "buy_price_eur_mwh": round(random.uniform(40.0, 150.0), 2),
        "sell_price_eur_mwh": round(random.uniform(42.0, 155.0), 2),
        "volume_mw": round(random.uniform(100.0, 1000.0), 2),
        "event_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "message_id": f"auto-{index:06d}",
    }


@celery_app.task(name="app.tasks.publish_test_prices")
def publish_test_prices():
    """Publish 96 price ticks spanning the next 24 hours (one per 15‑min slot)"""
    count = 96  # 24 h * 4 quarters
    window_hours = 24.0
    now = datetime.now(timezone.utc)
    start = now + timedelta(minutes=(15 - now.minute % 15) % 15)
    start = start.replace(second=0, microsecond=0)
    interval = timedelta(hours=window_hours) / count

    async def _publish():
        await broker.start()
        try:
            for i in range(count):
                delivery_ts = start + i * interval
                msg = generate_tick(i, delivery_ts)
                await broker.publish(
                    msg,
                    exchange=settings.main_exchange,
                    routing_key="prices.tick",
                )
            print(f"Published {count} future prices from {start.isoformat()}")
        finally:
            await broker.stop()

    asyncio.run(_publish())
