from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleSlotOutput(BaseModel):
    start_time: datetime
    power_mw: float
    state_of_charge_kwh: float | None
    is_manual_override: bool

    class Config:
        from_attributes = True


class ScheduleSlotInput(BaseModel):
    start_time: datetime
    power_mw: float = Field(..., ge=-1000, le=1000)
    state_of_charge_kwh: float | None = None
