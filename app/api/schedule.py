from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_session
from app.models.schedule import Schedule
from app.repositories.schedule_repo import upsert_schedule_slot
from app.schemas.schedules import ScheduleSlotOutput, ScheduleSlotInput

router = APIRouter(prefix="/schedules")


@router.get("/{asset_id}", response_model=List[ScheduleSlotOutput])
async def get_schedule(
    asset_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return the latest schedule for a given asset, ordered by time."""
    result = await session.execute(
        select(Schedule)
        .where(Schedule.asset_id == asset_id)
        .order_by(Schedule.start_time.asc())
    )
    slots = result.scalars().all()
    if not slots:
        raise HTTPException(status_code=404, detail="No schedule found for this asset.")
    return slots


@router.post("/{asset_id}", response_model=ScheduleSlotOutput)
async def override_schedule_slot(
    asset_id: int,
    slot: ScheduleSlotInput,
    session: AsyncSession = Depends(get_session),
):
    """Manually set a single schedule slot (trader override)."""
    success = await upsert_schedule_slot(
        session=session,
        asset_id=asset_id,
        start_time=slot.start_time,
        power_mw=slot.power_mw,
        state_of_charge_kwh=slot.state_of_charge_kwh,
        is_manual_override=True,
    )
    await session.commit()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update schedule.")
    # Fetch the created/updated row to return
    result = await session.execute(
        select(Schedule).where(
            Schedule.asset_id == asset_id, Schedule.start_time == slot.start_time
        )
    )
    updated = result.scalar_one()
    return updated
