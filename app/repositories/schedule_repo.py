from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.base import upsert, upsert_many
from app.models.schedule import Schedule
from app.core.config import settings


async def upsert_schedule_slot(
    session: AsyncSession,
    asset_id: int,
    start_time,
    power_mw: float,
    state_of_charge_kwh: float | None = None,
    is_manual_override: bool = False,
) -> bool:
    return await upsert(
        session,
        model=Schedule,
        values={
            "asset_id": asset_id,
            "start_time": start_time,
            "power_mw": power_mw,
            "state_of_charge_kwh": state_of_charge_kwh,
            "is_manual_override": is_manual_override,
        },
        conflict_columns=["asset_id", "start_time"],
    )


async def batch_upsert_schedule_slots(
    session: AsyncSession,
    slots: Sequence[dict],
) -> None:
    """
    Insert or update a batch of schedule slots.

    Each dict must contain:
        asset_id, start_time, power_mw, state_of_charge_kwh, is_manual_override
    """
    if not slots:
        return

    return await upsert_many(
        session,
        model=Schedule,
        values_list=slots,
        conflict_columns=["asset_id", "start_time"],
        batch_size=settings.upsert_batch_size,
    )


async def get_schedule_by_asset(session: AsyncSession, asset_id: int) -> list[Schedule]:
    result = await session.execute(
        select(Schedule)
        .where(Schedule.asset_id == asset_id)
        .order_by(Schedule.start_time.asc())
    )
    return result.scalars().all()


async def get_schedule_slot(
    session: AsyncSession, asset_id: int, start_time
) -> Schedule | None:
    result = await session.execute(
        select(Schedule).where(
            Schedule.asset_id == asset_id,
            Schedule.start_time == start_time,
        )
    )
    return result.scalar_one_or_none()
