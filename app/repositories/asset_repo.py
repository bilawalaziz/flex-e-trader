from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.asset import Asset


async def get_battery_assets(session: AsyncSession) -> list[Asset]:
    # get battery assets
    result = await session.execute(select(Asset).where(Asset.type == "battery"))
    return result.scalars().all()
