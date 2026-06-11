from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    Float,
    String,
    UniqueConstraint,
)
from app.models.base import Base
from datetime import datetime


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True)
    product = Column(String(20), index=True, nullable=False)  # e.g: 'DE-AT-1700'
    timestamp = Column(
        DateTime(timezone=True), index=True, nullable=False
    )  # delivery time
    buy_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    source = Column(String(50), default="rabbitmq")
    processed_at = Column(DateTime(timezone=True), default=datetime.now)

    __table_args__ = (
        UniqueConstraint("product", "timestamp", name="uq_price_product_timestamp"),
    )
