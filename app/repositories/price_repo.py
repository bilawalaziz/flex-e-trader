from typing import Any, Sequence

import pandas as pd
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import upsert
from app.models.price import Price
from app.schemas.events import PriceTick


async def upsert_price(session: AsyncSession, tick: PriceTick) -> bool:
    return await upsert(
        session,
        model=Price,
        values={
            "product": tick.product,
            "timestamp": tick.timestamp,
            "buy_price": tick.buy_price_eur_mwh,
            "sell_price": tick.sell_price_eur_mwh,
            "volume": tick.volume_mw,
            "source": "rabbitmq",
            "event_time": tick.event_time,
        },
        conflict_columns=["product", "timestamp"],
        condition=lambda stmt: Price.event_time < stmt.excluded.event_time,
    )


async def get_latest_prices(session: AsyncSession) -> Sequence[Row[Any]]:
    # return recent price pers delivery slot for 24 hrs duration from now
    stmt = text("""
        SELECT DISTINCT ON (product, timestamp)
            timestamp, buy_price, sell_price
        FROM prices
        WHERE timestamp >= NOW()
          AND timestamp < NOW() + INTERVAL '24 hours'
        ORDER BY product, timestamp, event_time DESC
    """)
    result = await session.execute(stmt)
    rows = result.fetchall()
    if rows:
        return rows

    return None


async def get_latest_prices_df(session: AsyncSession) -> pd.DataFrame:

    rows = await get_latest_prices(session)
    df = pd.DataFrame(rows, columns=["timestamp", "buy_price", "sell_price"])
    if not df.empty:
        df = df.sort_values("timestamp").reset_index(drop=True)
    return df
