#!/usr/bin/env python3
"""
Standalone publisher for generating test price tick messages.

Usage:
    # 96 messages (24h @ 15-min), spread over the next 24 hours
    python -m scripts.publish_prices --count 96 --window-hours 24

    # 20 messages, every 0.5s, all in the next hour
    python -m scripts.publish_prices --count 20 --interval 0.5 --window-hours 1

    # Scenario mode (4 dedup test messages)
    python -m scripts.publish_prices --scenario
"""

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone

from faststream.rabbit import RabbitBroker
from app.core.config import settings

PRODUCTS = [
    "DE-AT-2024",
    "DE-AT-2025",
    "DE-AT-2026",
    "DE-AT-2027",
    "DE-AT-2028",
]


def generate_tick(
    index: int | None = None,
    product: str | None = None,
    delivery_ts: datetime | None = None,
    event_time: datetime | None = None,
    buy: float | None = None,
    sell: float | None = None,
    volume: float | None = None,
    inject_errors: bool = False,
) -> dict:
    if product is None:
        product = random.choice(PRODUCTS)
    if inject_errors and random.random() < 0.1:
        product = "DE-ABT-2025"  # invalid pattern

    if delivery_ts is None:
        delivery_ts = datetime.now(timezone.utc)
    if event_time is None:
        event_time = datetime.now(timezone.utc)

    tick = {
        "product": product,
        "timestamp": delivery_ts.isoformat().replace("+00:00", "Z"),
        "buy_price_eur_mwh": buy
        if buy is not None
        else round(random.uniform(40.0, 150.0), 2),
        "sell_price_eur_mwh": sell
        if sell is not None
        else round(random.uniform(42.0, 155.0), 2),
        "volume_mw": volume
        if volume is not None
        else round(random.uniform(100.0, 1000.0), 2),
        "event_time": event_time.isoformat().replace("+00:00", "Z"),
    }
    if index is not None:
        tick["message_id"] = f"test-{index:04d}"
    return tick


async def run_scenario(broker: RabbitBroker) -> None:
    product = "DE-AT-2024"
    delivery = datetime(2024, 12, 15, 18, 0, tzinfo=timezone.utc)
    base_event = datetime(2024, 12, 15, 17, 0, tzinfo=timezone.utc)

    ticks = [
        ("1-First", 120.75, 122.50, 500.0, base_event),
        ("2-Update", 115.00, 118.00, 800.0, base_event + timedelta(minutes=5)),
        ("3-Duplicate", 115.00, 118.00, 800.0, base_event + timedelta(minutes=5)),
        ("4-Stale", 130.00, 132.00, 100.0, base_event - timedelta(minutes=5)),
    ]

    await broker.start()
    try:
        for i, (label, buy, sell, vol, evt) in enumerate(ticks):
            msg = generate_tick(
                index=i,
                product=product,
                delivery_ts=delivery,
                event_time=evt,
                buy=buy,
                sell=sell,
                volume=vol,
            )
            await broker.publish(
                msg, exchange=settings.main_exchange, routing_key="prices.tick"
            )
            print(
                f"Published {label}: event_time={msg['event_time']} buy={buy} msg_id={msg.get('message_id')}"
            )
            await asyncio.sleep(1)
    finally:
        await broker.stop()
    print("Scenario complete – check the prices table.")


async def publish_random(
    broker: RabbitBroker,
    count: int,
    interval: float,
    window_hours: float,
    inject_errors: bool,
) -> None:
    """
    Publish `count` messages, with delivery times evenly spaced over the next `window_hours` hours.
    The first delivery time is the next rounded 15-minute mark.
    """
    now = datetime.now(timezone.utc)
    # Start at the next 15-min boundary
    start_delivery = now + timedelta(minutes=(15 - now.minute % 15) % 15)
    start_delivery = start_delivery.replace(second=0, microsecond=0)

    interval_td = timedelta(hours=window_hours) / max(count - 1, 1)

    await broker.start()
    try:
        for i in range(count):
            delivery_ts = start_delivery + i * interval_td
            msg = generate_tick(
                index=i, delivery_ts=delivery_ts, inject_errors=inject_errors
            )
            await broker.publish(
                msg, exchange=settings.main_exchange, routing_key="prices.tick"
            )
            print(
                f"[{i + 1}/{count}] {msg['product']} delivery={msg['timestamp']} (msg_id={msg.get('message_id')})"
            )
            if interval > 0 and i < count - 1:
                await asyncio.sleep(interval)
    finally:
        await broker.stop()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Publish test price ticks to RabbitMQ")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.0)
    parser.add_argument("--errors", action="store_true")
    parser.add_argument("--scenario", action="store_true")
    parser.add_argument(
        "--window-hours",
        type=float,
        default=0.0,
        help="Spread delivery times over this many hours from now",
    )
    parser.add_argument(
        "--delivery-time",
        type=str,
        default=None,
        help="ISO 8601 UTC delivery timestamp (e.g., '2024-12-15T18:00:00Z') – overrides window",
    )
    args = parser.parse_args()

    broker = RabbitBroker(url=settings.rabbitmq_url)

    if args.scenario:
        await run_scenario(broker)
    else:
        if args.delivery_time:
            # Fixed delivery time for all messages (original behavior)
            delivery_ts = datetime.fromisoformat(
                args.delivery_time.replace("Z", "+00:00")
            )
            # Use a single-delivery window of 0 hours to pass to publish_random, but we'll handle differently
            # Simpler: keep old logic
            await broker.start()
            try:
                for i in range(args.count):
                    msg = generate_tick(
                        index=i, delivery_ts=delivery_ts, inject_errors=args.errors
                    )
                    await broker.publish(
                        msg, exchange=settings.main_exchange, routing_key="prices.tick"
                    )
                    print(
                        f"[{i + 1}/{args.count}] {msg['product']} @ {msg['timestamp']}"
                    )
                    if args.interval > 0 and i < args.count - 1:
                        await asyncio.sleep(args.interval)
            finally:
                await broker.stop()
        else:
            await publish_random(
                broker, args.count, args.interval, args.window_hours, args.errors
            )


if __name__ == "__main__":
    asyncio.run(main())
