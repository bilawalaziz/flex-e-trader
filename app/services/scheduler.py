import asyncio
import logging
import json
import time
from datetime import datetime, timezone

import pandas as pd
from redis.asyncio import Redis
from app.core.config import settings
from app.core.metrics import (
    optimisation_cycles_total,
    optimisation_duration_seconds,
    record_optimisation_result,
    schedule_slots_written_total,
)
from app.core.database import async_session
from app.repositories.price_repo import get_latest_prices
from app.repositories.asset_repo import get_battery_assets
from app.repositories.schedule_repo import batch_upsert_schedule_slots
from app.services.optimisation import compute_battery_schedule

logger = logging.getLogger(__name__)


async def run_optimisation():
    """Background loop: recalculate schedules for all batteries."""
    redis = Redis.from_url(settings.redis_url)
    interval_mins: int = max(int(settings.interval_mins), 1)
    while True:
        cycle_start = time.perf_counter()
        try:
            logger.info("optimisation cycle starting | interval=%s min", interval_mins)

            # fetch battery price data
            async with async_session() as session:
                prices = await get_latest_prices(session)
                batteries = await get_battery_assets(session)

            prices_df = pd.DataFrame(
                prices, columns=["timestamp", "buy_price", "sell_price"]
            )

            if prices_df.empty:
                logger.warning(
                    "no prices available, skipping cycle | sleeping=%s min",
                    interval_mins,
                )
                optimisation_cycles_total.labels(outcome="no_prices").inc()
                optimisation_duration_seconds.observe(time.perf_counter() - cycle_start)
                await sleep_for_minutes(interval_mins)
                continue
            else:
                prices_df = prices_df.sort_values("timestamp").reset_index(drop=True)

            for bat in batteries:
                spec = {
                    "max_charge_mw": bat.max_charge_mw,
                    "max_discharge_mw": bat.max_discharge_mw,
                    "capacity_kwh": bat.capacity_kwh,
                    "charge_eff": bat.charge_efficiency,
                    "discharge_eff": bat.discharge_efficiency,
                    "min_soc": bat.min_soc,
                    "max_soc": bat.max_soc,
                }
                schedule = compute_battery_schedule(prices_df, spec)
                diagnostics = schedule.attrs.get("diagnostics", {})
                record_optimisation_result(bat.name, diagnostics)
                if diagnostics.get("repaired_intervals"):
                    # Worth a log line as well as a metric: this is the one
                    # condition under which the published schedule is not the
                    # optimum the LP reported.
                    logger.warning(
                        "exclusivity repair applied | asset=%s | intervals=%s/%s "
                        "| profit_given_up=%.2f EUR",
                        bat.name,
                        diagnostics["repaired_intervals"],
                        diagnostics.get("intervals", 0),
                        diagnostics.get("lp_profit_eur", 0.0)
                        - diagnostics.get("realised_profit_eur", 0.0),
                    )

                # store power schedules for battries
                slots = []
                seen_times = set()
                for _, row in schedule.iterrows():
                    ts = row["timestamp"]
                    if ts in seen_times:
                        continue
                    seen_times.add(ts)
                    slots.append(
                        {
                            "asset_id": bat.id,
                            "start_time": row["timestamp"],
                            "power_mw": row["power_mw"],
                            "state_of_charge_kwh": row["soc_kwh"],
                            "is_manual_override": False,
                        }
                    )

                async with async_session() as session:
                    await batch_upsert_schedule_slots(session, slots)
                    await session.commit()

                schedule_slots_written_total.labels(asset=bat.name).inc(len(slots))
                logger.info(
                    "schedule saved | asset=%s | slots=%s", bat.name, len(slots)
                )

                # publish notification for clients
                await redis.publish(
                    "schedule_updates",
                    json.dumps(
                        {
                            "asset_id": bat.id,
                            "asset_name": bat.name,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                )

            optimisation_cycles_total.labels(outcome="success").inc()

        except Exception:
            logger.exception("optimisation cycle failed")
            optimisation_cycles_total.labels(outcome="failed").inc()

        optimisation_duration_seconds.observe(time.perf_counter() - cycle_start)
        logger.debug("cycle complete | sleeping=%s min", interval_mins)
        await sleep_for_minutes(interval_mins)


async def sleep_for_minutes(interval: int = 1):
    await asyncio.sleep(interval * 60)
