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
        },
        conflict_columns=["product", "timestamp"],
    )
