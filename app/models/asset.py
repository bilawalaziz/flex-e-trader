from sqlalchemy import Column, Integer, Float, String, Text
from app.models.base import Base


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(50), nullable=False)  # 'battery', 'solar', 'wind', 'biogas'
    # Battery-specific parameters (nullable for other types)
    max_charge_mw = Column(Float, nullable=True)
    max_discharge_mw = Column(Float, nullable=True)
    capacity_kwh = Column(Float, nullable=True)
    charge_efficiency = Column(Float, nullable=True)  # 0..1
    discharge_efficiency = Column(Float, nullable=True)  # 0..1
    min_soc = Column(Float, nullable=True)  # minimum state of charge (fraction 0..1)
    max_soc = Column(Float, nullable=True)
    ramp_rate_mw_per_min = Column(Float, nullable=True)
    # Any extra configuration (JSON string or separate table)
    extra_params = Column(Text, nullable=True)  # JSON blob for future flexibility
