from sqlalchemy import (
    Column,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from app.models.base import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)  # start of interval
    power_mw = Column(Float, nullable=False)  # positive = export, negative = import
    state_of_charge_kwh = Column(Float, nullable=True)  # for batteries
    is_manual_override = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("asset_id", "start_time", name="uq_schedule_slot"),
    )
